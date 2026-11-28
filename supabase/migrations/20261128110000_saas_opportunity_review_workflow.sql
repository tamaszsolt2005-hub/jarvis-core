-- Human review lifecycle for automatically generated SaaS opportunity candidates.
-- Candidate generation remains automatic; shortlist/rejection requires an authenticated reviewer.
BEGIN;

CREATE TABLE IF NOT EXISTS public.saas_opportunity_review_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  opportunity_id uuid NOT NULL REFERENCES public.saas_opportunities(id) ON DELETE RESTRICT,
  decision text NOT NULL CHECK (decision IN ('under_review','shortlisted','rejected')),
  note text NOT NULL CHECK (length(btrim(note)) BETWEEN 5 AND 2000),
  reviewed_by uuid NOT NULL DEFAULT auth.uid(),
  reviewed_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS saas_opportunity_review_events_opportunity_idx
  ON public.saas_opportunity_review_events (opportunity_id, reviewed_at DESC);

ALTER TABLE public.saas_opportunity_review_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.saas_opportunity_review_events FROM PUBLIC, anon, authenticated;
GRANT SELECT ON TABLE public.saas_opportunity_review_events TO authenticated;
GRANT ALL ON TABLE public.saas_opportunity_review_events TO service_role;
DROP POLICY IF EXISTS saas_opportunity_review_events_shared_read
  ON public.saas_opportunity_review_events;
CREATE POLICY saas_opportunity_review_events_shared_read
  ON public.saas_opportunity_review_events
  FOR SELECT TO authenticated
  USING ((SELECT auth.jwt() -> 'app_metadata' ->> 'role') IN ('admin','operator','reader'));

CREATE OR REPLACE FUNCTION public.reject_saas_opportunity_review_event_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = ''
AS $saas_opportunity_review_immutable$
BEGIN
  RAISE EXCEPTION USING
    ERRCODE = '55000',
    MESSAGE = 'saas_opportunity_review_events_are_append_only';
END;
$saas_opportunity_review_immutable$;

DROP TRIGGER IF EXISTS saas_opportunity_review_events_immutable
  ON public.saas_opportunity_review_events;
CREATE TRIGGER saas_opportunity_review_events_immutable
BEFORE UPDATE OR DELETE ON public.saas_opportunity_review_events
FOR EACH ROW EXECUTE FUNCTION public.reject_saas_opportunity_review_event_mutation();

CREATE OR REPLACE FUNCTION public.review_saas_opportunity(
  p_opportunity_id uuid,
  p_decision text,
  p_note text
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $saas_opportunity_review$
DECLARE
  v_role text;
  v_current_status text;
  v_pattern_status text;
  v_company_count integer;
  v_event_id uuid;
BEGIN
  v_role := auth.jwt() -> 'app_metadata' ->> 'role';
  IF auth.uid() IS NULL OR COALESCE(v_role,'') NOT IN ('admin','operator') THEN
    RAISE EXCEPTION USING
      ERRCODE = '42501',
      MESSAGE = 'saas_opportunity_review_requires_admin_or_operator';
  END IF;
  IF p_decision IS NULL OR p_decision NOT IN ('under_review','shortlisted','rejected') THEN
    RAISE EXCEPTION USING
      ERRCODE = '22023',
      MESSAGE = 'unsupported_saas_opportunity_decision';
  END IF;
  IF p_note IS NULL OR length(btrim(p_note)) NOT BETWEEN 5 AND 2000 THEN
    RAISE EXCEPTION USING
      ERRCODE = '22023',
      MESSAGE = 'saas_opportunity_review_note_required';
  END IF;

  SELECT candidate.status, pattern.status
    INTO v_current_status, v_pattern_status
  FROM public.saas_opportunities AS candidate
  JOIN public.market_problem_patterns AS pattern
    ON pattern.id = candidate.market_pattern_id
  WHERE candidate.id = p_opportunity_id
  FOR UPDATE OF candidate, pattern;

  IF NOT FOUND THEN
    RAISE EXCEPTION USING
      ERRCODE = 'P0002',
      MESSAGE = 'saas_opportunity_not_found';
  END IF;
  IF v_current_status = 'rejected' THEN
    RAISE EXCEPTION USING
      ERRCODE = '23514',
      MESSAGE = 'rejected_saas_opportunity_is_terminal';
  END IF;
  IF p_decision = 'shortlisted' THEN
    IF v_pattern_status <> 'validated' THEN
      RAISE EXCEPTION USING
        ERRCODE = '23514',
        MESSAGE = 'shortlisted_opportunity_requires_validated_pattern';
    END IF;
    SELECT count(DISTINCT pain.lead_id) INTO v_company_count
    FROM public.market_pattern_pains AS link
    JOIN public.business_pain_hypotheses AS pain
      ON pain.id = link.company_pain_id
    WHERE link.market_pattern_id = (
      SELECT market_pattern_id
      FROM public.saas_opportunities
      WHERE id = p_opportunity_id
    )
      AND pain.status <> 'rejected'
      AND jsonb_typeof(pain.evidence) = 'array'
      AND jsonb_array_length(pain.evidence) > 0;
    IF v_company_count < 2 THEN
      RAISE EXCEPTION USING
        ERRCODE = '23514',
        MESSAGE = 'shortlisted_opportunity_requires_two_source_backed_companies';
    END IF;
  END IF;

  UPDATE public.saas_opportunities
  SET status = p_decision, updated_at = now()
  WHERE id = p_opportunity_id;

  INSERT INTO public.saas_opportunity_review_events
    (opportunity_id, decision, note, reviewed_by)
  VALUES (p_opportunity_id, p_decision, btrim(p_note), auth.uid())
  RETURNING id INTO v_event_id;

  RETURN v_event_id;
END;
$saas_opportunity_review$;

REVOKE ALL ON FUNCTION public.reject_saas_opportunity_review_event_mutation()
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.reject_saas_opportunity_review_event_mutation()
  TO service_role;
GRANT EXECUTE ON FUNCTION public.review_saas_opportunity(uuid,text,text)
  TO authenticated, service_role;
REVOKE ALL ON FUNCTION public.review_saas_opportunity(uuid,text,text)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.review_saas_opportunity(uuid,text,text)
  TO authenticated, service_role;

COMMIT;
