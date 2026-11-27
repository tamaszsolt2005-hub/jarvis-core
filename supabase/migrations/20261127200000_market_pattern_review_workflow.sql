-- Authenticated human review for automatically discovered market patterns.
-- Repository-only until separately reviewed and deployed.
BEGIN;

CREATE TABLE IF NOT EXISTS public.market_pattern_review_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  market_pattern_id uuid NOT NULL REFERENCES public.market_problem_patterns(id) ON DELETE RESTRICT,
  decision text NOT NULL CHECK (decision IN ('validated','rejected','under_review')),
  note text NOT NULL CHECK (length(btrim(note)) BETWEEN 5 AND 2000),
  reviewed_by uuid NOT NULL DEFAULT auth.uid(),
  reviewed_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS market_pattern_review_events_pattern_idx
  ON public.market_pattern_review_events (market_pattern_id, reviewed_at DESC);

ALTER TABLE public.market_pattern_review_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.market_pattern_review_events FROM PUBLIC, anon, authenticated;
GRANT SELECT ON TABLE public.market_pattern_review_events TO authenticated;
GRANT ALL ON TABLE public.market_pattern_review_events TO service_role;
CREATE POLICY market_pattern_review_events_shared_read
  ON public.market_pattern_review_events FOR SELECT TO authenticated
  USING ((SELECT auth.jwt() -> 'app_metadata' ->> 'role') IN ('admin','operator','reader'));

CREATE OR REPLACE FUNCTION public.reject_market_pattern_review_event_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = ''
AS $market_pattern_review_immutable$
BEGIN
  RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'market_pattern_review_events_are_append_only';
END;
$market_pattern_review_immutable$;

DROP TRIGGER IF EXISTS market_pattern_review_events_immutable ON public.market_pattern_review_events;
CREATE TRIGGER market_pattern_review_events_immutable
BEFORE UPDATE OR DELETE ON public.market_pattern_review_events
FOR EACH ROW EXECUTE FUNCTION public.reject_market_pattern_review_event_mutation();

CREATE OR REPLACE FUNCTION public.review_market_pattern(
  p_market_pattern_id uuid,
  p_decision text,
  p_note text
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $market_pattern_review$
DECLARE
  v_role text;
  v_company_count integer;
  v_event_id uuid;
BEGIN
  v_role := auth.jwt() -> 'app_metadata' ->> 'role';
  IF auth.uid() IS NULL OR COALESCE(v_role,'') NOT IN ('admin','operator') THEN
    RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'market_pattern_review_requires_admin_or_operator';
  END IF;
  IF p_decision NOT IN ('validated','rejected','under_review') THEN
    RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'unsupported_market_pattern_decision';
  END IF;
  IF p_note IS NULL OR length(btrim(p_note)) NOT BETWEEN 5 AND 2000 THEN
    RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'market_pattern_review_note_required';
  END IF;

  PERFORM 1 FROM public.market_problem_patterns
  WHERE id = p_market_pattern_id
  FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION USING ERRCODE = 'P0002', MESSAGE = 'market_pattern_not_found';
  END IF;

  IF p_decision = 'validated' THEN
    SELECT count(DISTINCT pain.lead_id) INTO v_company_count
    FROM public.market_pattern_pains link
    JOIN public.business_pain_hypotheses pain ON pain.id = link.company_pain_id
    WHERE link.market_pattern_id = p_market_pattern_id
      AND pain.status <> 'rejected'
      AND jsonb_typeof(pain.evidence) = 'array'
      AND jsonb_array_length(pain.evidence) > 0;
    IF v_company_count < 2 THEN
      RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'market_pattern_requires_two_source_backed_companies';
    END IF;
  END IF;

  UPDATE public.market_problem_patterns
  SET status = p_decision, updated_at = now()
  WHERE id = p_market_pattern_id;

  INSERT INTO public.market_pattern_review_events
    (market_pattern_id, decision, note, reviewed_by)
  VALUES (p_market_pattern_id, p_decision, btrim(p_note), auth.uid())
  RETURNING id INTO v_event_id;

  RETURN v_event_id;
END;
$market_pattern_review$;

REVOKE ALL ON FUNCTION public.reject_market_pattern_review_event_mutation() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.reject_market_pattern_review_event_mutation() TO service_role;
REVOKE ALL ON FUNCTION public.review_market_pattern(uuid,text,text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.review_market_pattern(uuid,text,text) TO authenticated, service_role;

COMMIT;
