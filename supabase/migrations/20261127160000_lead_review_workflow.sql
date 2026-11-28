-- Human-reviewed lead queue. No contact consent or email delivery is granted by approval.
-- Repository-only until separately reviewed and applied.
BEGIN;

CREATE TABLE IF NOT EXISTS public.lead_review_states (
  lead_id uuid PRIMARY KEY REFERENCES public.leads(id) ON DELETE CASCADE,
  review_status text NOT NULL DEFAULT 'pending'
    CHECK (review_status IN ('pending','approved','rejected')),
  rejection_note text,
  disposition text CHECK (disposition IN ('keep','recommend_alternative','wait')),
  alternative_saas text,
  updated_by uuid,
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (rejection_note IS NULL OR length(rejection_note) <= 2000),
  CHECK (alternative_saas IS NULL OR length(alternative_saas) <= 1200),
  CHECK (disposition <> 'recommend_alternative' OR length(btrim(COALESCE(alternative_saas,''))) > 0)
);

CREATE TABLE IF NOT EXISTS public.lead_review_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id uuid NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
  event_type text NOT NULL CHECK (event_type IN ('approved','rejected','discussion','disposition')),
  note text,
  ai_response text,
  disposition text CHECK (disposition IN ('keep','recommend_alternative','wait')),
  alternative_saas text,
  actor_id uuid NOT NULL DEFAULT auth.uid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (note IS NULL OR length(note) <= 2000),
  CHECK (ai_response IS NULL OR length(ai_response) <= 8000),
  CHECK (alternative_saas IS NULL OR length(alternative_saas) <= 1200)
);

CREATE INDEX IF NOT EXISTS lead_review_events_lead_created_idx
  ON public.lead_review_events (lead_id, created_at DESC, id DESC);

CREATE OR REPLACE FUNCTION public.reject_lead_review_event_mutation()
RETURNS trigger LANGUAGE plpgsql SET search_path = ''
AS $lead_review_immutable$
BEGIN
  RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'lead_review_events_are_append_only';
END;
$lead_review_immutable$;

DROP TRIGGER IF EXISTS lead_review_events_immutable_guard ON public.lead_review_events;
CREATE TRIGGER lead_review_events_immutable_guard
BEFORE UPDATE OR DELETE ON public.lead_review_events
FOR EACH ROW EXECUTE FUNCTION public.reject_lead_review_event_mutation();

CREATE OR REPLACE FUNCTION public.record_lead_review_event(
  p_lead_id uuid,
  p_event_type text,
  p_note text DEFAULT NULL,
  p_ai_response text DEFAULT NULL,
  p_disposition text DEFAULT NULL,
  p_alternative_saas text DEFAULT NULL
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $lead_review_record$
DECLARE
  v_role text;
  v_status text;
  v_note text := NULLIF(btrim(p_note), '');
  v_ai_response text := NULLIF(btrim(p_ai_response), '');
  v_alternative text := NULLIF(btrim(p_alternative_saas), '');
  v_event_id uuid;
BEGIN
  v_role := auth.jwt() -> 'app_metadata' ->> 'role';
  IF auth.uid() IS NULL OR COALESCE(v_role,'') NOT IN ('admin','operator') THEN
    RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'lead_review_requires_admin_or_operator';
  END IF;
  IF p_lead_id IS NULL OR NOT EXISTS (SELECT 1 FROM public.leads WHERE id = p_lead_id) THEN
    RAISE EXCEPTION USING ERRCODE = '23503', MESSAGE = 'lead_review_lead_not_found';
  END IF;
  IF p_event_type NOT IN ('approved','rejected','discussion','disposition') THEN
    RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'lead_review_event_type_invalid';
  END IF;
  IF v_note IS NOT NULL AND length(v_note) > 2000 THEN
    RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'lead_review_note_too_long';
  END IF;
  IF v_ai_response IS NOT NULL AND length(v_ai_response) > 8000 THEN
    RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'lead_review_ai_response_too_long';
  END IF;
  IF v_alternative IS NOT NULL AND length(v_alternative) > 1200 THEN
    RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'lead_review_alternative_too_long';
  END IF;

  IF p_event_type = 'approved' THEN
    v_status := 'approved';
  ELSIF p_event_type = 'rejected' THEN
    IF v_note IS NULL OR length(v_note) < 5 THEN
      RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'lead_review_rejection_note_required';
    END IF;
    v_status := 'rejected';
  ELSIF p_event_type = 'discussion' THEN
    IF v_note IS NULL OR length(v_note) < 5 OR v_ai_response IS NULL THEN
      RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'lead_review_discussion_requires_note_and_response';
    END IF;
    IF NOT EXISTS (
      SELECT 1 FROM public.lead_review_states
      WHERE lead_id = p_lead_id AND review_status = 'rejected'
    ) THEN
      RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'lead_review_discussion_requires_rejected_lead';
    END IF;
  ELSIF p_event_type = 'disposition' THEN
    IF p_disposition IS NULL OR p_disposition NOT IN ('keep','recommend_alternative','wait') THEN
      RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'lead_review_disposition_invalid';
    END IF;
    IF p_disposition = 'recommend_alternative' AND (v_alternative IS NULL OR length(v_alternative) < 2) THEN
      RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'lead_review_alternative_required';
    END IF;
    IF NOT EXISTS (
      SELECT 1 FROM public.lead_review_states
      WHERE lead_id = p_lead_id AND review_status = 'rejected'
    ) THEN
      RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'lead_review_disposition_requires_rejected_lead';
    END IF;
  END IF;

  INSERT INTO public.lead_review_events (
    lead_id,event_type,note,ai_response,disposition,alternative_saas,actor_id
  ) VALUES (
    p_lead_id,p_event_type,v_note,v_ai_response,p_disposition,v_alternative,auth.uid()
  ) RETURNING id INTO v_event_id;

  INSERT INTO public.lead_review_states (
    lead_id,review_status,rejection_note,disposition,alternative_saas,updated_by,updated_at
  ) VALUES (
    p_lead_id,
    COALESCE(v_status,'rejected'),
    CASE WHEN p_event_type = 'rejected' THEN v_note
         WHEN p_event_type = 'approved' THEN NULL
         ELSE NULL END,
    CASE WHEN p_event_type = 'disposition' THEN p_disposition
         WHEN p_event_type IN ('approved','rejected') THEN NULL
         ELSE NULL END,
    CASE WHEN p_event_type = 'disposition' THEN v_alternative ELSE NULL END,
    auth.uid(),now()
  )
  ON CONFLICT (lead_id) DO UPDATE SET
    review_status = CASE WHEN p_event_type IN ('approved','rejected') THEN EXCLUDED.review_status
                         ELSE public.lead_review_states.review_status END,
    rejection_note = CASE WHEN p_event_type IN ('approved','rejected') THEN EXCLUDED.rejection_note
                          ELSE public.lead_review_states.rejection_note END,
    disposition = CASE WHEN p_event_type IN ('approved','rejected','disposition') THEN EXCLUDED.disposition
                       ELSE public.lead_review_states.disposition END,
    alternative_saas = CASE WHEN p_event_type IN ('approved','rejected','disposition') THEN EXCLUDED.alternative_saas
                            ELSE public.lead_review_states.alternative_saas END,
    updated_by = auth.uid(),
    updated_at = now();

  RETURN v_event_id;
END;
$lead_review_record$;

ALTER TABLE public.lead_review_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lead_review_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.lead_review_states FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON TABLE public.lead_review_events FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT ON TABLE public.lead_review_states TO authenticated, service_role;
GRANT SELECT ON TABLE public.lead_review_events TO authenticated, service_role;

DROP POLICY IF EXISTS lead_review_states_shared_read ON public.lead_review_states;
CREATE POLICY lead_review_states_shared_read ON public.lead_review_states
  FOR SELECT TO authenticated
  USING ((SELECT auth.jwt() -> 'app_metadata' ->> 'role') IN ('admin','operator','reader'));
DROP POLICY IF EXISTS lead_review_events_shared_read ON public.lead_review_events;
CREATE POLICY lead_review_events_shared_read ON public.lead_review_events
  FOR SELECT TO authenticated
  USING ((SELECT auth.jwt() -> 'app_metadata' ->> 'role') IN ('admin','operator','reader'));

REVOKE ALL ON FUNCTION public.reject_lead_review_event_mutation() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.record_lead_review_event(uuid,text,text,text,text,text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.reject_lead_review_event_mutation() TO authenticated;
GRANT EXECUTE ON FUNCTION public.record_lead_review_event(uuid,text,text,text,text,text) TO authenticated;

COMMENT ON TABLE public.lead_review_states IS
  'Current human review state for a company lead; independent from contact consent and email permissions.';
COMMENT ON TABLE public.lead_review_events IS
  'Append-only audit history of lead approvals, rejections, AI discussions and follow-up dispositions.';

COMMIT;
