-- CRM lifecycle and interaction history for approved leads.
-- This workflow records human-entered activity only; it never sends email.
BEGIN;

CREATE TABLE IF NOT EXISTS public.lead_customer_lifecycle (
  lead_id uuid PRIMARY KEY REFERENCES public.leads(id) ON DELETE CASCADE,
  stage text NOT NULL DEFAULT 'approved_lead'
    CHECK (stage IN ('approved_lead','contacted','responded','qualified','proposal','pilot','customer','lost')),
  next_action text CHECK (next_action IS NULL OR length(btrim(next_action)) BETWEEN 1 AND 500),
  next_action_due date,
  last_interaction_at timestamptz,
  updated_by uuid NOT NULL DEFAULT auth.uid(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS lead_customer_lifecycle_stage_due_idx
  ON public.lead_customer_lifecycle (stage, next_action_due, updated_at DESC);

CREATE TABLE IF NOT EXISTS public.lead_customer_lifecycle_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id uuid NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
  event_type text NOT NULL CHECK (event_type IN ('stage_changed','interaction_logged','next_action_set')),
  from_stage text CHECK (from_stage IS NULL OR from_stage IN ('approved_lead','contacted','responded','qualified','proposal','pilot','customer','lost')),
  to_stage text CHECK (to_stage IS NULL OR to_stage IN ('approved_lead','contacted','responded','qualified','proposal','pilot','customer','lost')),
  channel text CHECK (channel IS NULL OR channel IN ('email','phone','meeting','note','other')),
  summary text NOT NULL CHECK (length(btrim(summary)) BETWEEN 5 AND 2000),
  next_action text CHECK (next_action IS NULL OR length(btrim(next_action)) BETWEEN 1 AND 500),
  next_action_due date,
  actor_id uuid NOT NULL DEFAULT auth.uid(),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS lead_customer_lifecycle_events_lead_created_idx
  ON public.lead_customer_lifecycle_events (lead_id, created_at DESC, id DESC);

ALTER TABLE public.lead_customer_lifecycle ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lead_customer_lifecycle_events ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.lead_customer_lifecycle FROM PUBLIC, anon, authenticated;
REVOKE ALL ON TABLE public.lead_customer_lifecycle_events FROM PUBLIC, anon, authenticated;
GRANT SELECT ON TABLE public.lead_customer_lifecycle TO authenticated;
GRANT SELECT ON TABLE public.lead_customer_lifecycle_events TO authenticated;
GRANT SELECT, INSERT, UPDATE ON TABLE public.lead_customer_lifecycle TO service_role;
GRANT SELECT, INSERT ON TABLE public.lead_customer_lifecycle_events TO service_role;

DROP POLICY IF EXISTS lead_customer_lifecycle_shared_read ON public.lead_customer_lifecycle;
CREATE POLICY lead_customer_lifecycle_shared_read
  ON public.lead_customer_lifecycle FOR SELECT TO authenticated
  USING ((SELECT auth.jwt() -> 'app_metadata' ->> 'role') IN ('admin','operator','reader'));

DROP POLICY IF EXISTS lead_customer_lifecycle_events_shared_read ON public.lead_customer_lifecycle_events;
CREATE POLICY lead_customer_lifecycle_events_shared_read
  ON public.lead_customer_lifecycle_events FOR SELECT TO authenticated
  USING ((SELECT auth.jwt() -> 'app_metadata' ->> 'role') IN ('admin','operator','reader'));

CREATE OR REPLACE FUNCTION public.reject_lead_customer_lifecycle_event_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = ''
AS $lead_customer_lifecycle_immutable$
BEGIN
  RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'lead_customer_lifecycle_events_are_append_only';
END;
$lead_customer_lifecycle_immutable$;

DROP TRIGGER IF EXISTS lead_customer_lifecycle_events_immutable ON public.lead_customer_lifecycle_events;
CREATE TRIGGER lead_customer_lifecycle_events_immutable
BEFORE UPDATE OR DELETE ON public.lead_customer_lifecycle_events
FOR EACH ROW EXECUTE FUNCTION public.reject_lead_customer_lifecycle_event_mutation();

CREATE OR REPLACE FUNCTION public.record_lead_customer_lifecycle_event(
  p_lead_id uuid,
  p_event_type text,
  p_stage text,
  p_channel text,
  p_summary text,
  p_next_action text,
  p_next_action_due date
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $lead_customer_lifecycle$
DECLARE
  v_role text;
  v_from_stage text;
  v_to_stage text;
  v_event_id uuid;
BEGIN
  v_role := auth.jwt() -> 'app_metadata' ->> 'role';
  IF auth.uid() IS NULL OR COALESCE(v_role,'') NOT IN ('admin','operator') THEN
    RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'lead_customer_lifecycle_requires_admin_or_operator';
  END IF;
  IF p_event_type IS NULL OR p_event_type NOT IN ('stage_changed','interaction_logged','next_action_set') THEN
    RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'lead_customer_lifecycle_event_type_invalid';
  END IF;
  IF p_summary IS NULL OR length(btrim(p_summary)) NOT BETWEEN 5 AND 2000 THEN
    RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'lead_customer_lifecycle_summary_required';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM public.lead_review_states
    WHERE lead_id = p_lead_id AND review_status = 'approved'
  ) THEN
    RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'lead_customer_lifecycle_requires_approved_lead';
  END IF;

  SELECT stage INTO v_from_stage
  FROM public.lead_customer_lifecycle
  WHERE lead_id = p_lead_id
  FOR UPDATE;
  v_from_stage := COALESCE(v_from_stage, 'approved_lead');
  v_to_stage := v_from_stage;

  IF p_event_type = 'stage_changed' THEN
    IF p_stage IS NULL OR p_stage NOT IN ('approved_lead','contacted','responded','qualified','proposal','pilot','customer','lost') THEN
      RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'lead_customer_lifecycle_stage_invalid';
    END IF;
    v_to_stage := p_stage;
  ELSIF p_event_type = 'interaction_logged' THEN
    IF p_channel IS NULL OR p_channel NOT IN ('email','phone','meeting','note','other') THEN
      RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'lead_customer_lifecycle_channel_invalid';
    END IF;
  ELSIF p_event_type = 'next_action_set' THEN
    IF p_next_action IS NULL OR length(btrim(p_next_action)) NOT BETWEEN 1 AND 500 THEN
      RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'lead_customer_lifecycle_next_action_required';
    END IF;
  END IF;

  INSERT INTO public.lead_customer_lifecycle_events (
    lead_id,event_type,from_stage,to_stage,channel,summary,next_action,next_action_due,actor_id
  ) VALUES (
    p_lead_id,p_event_type,v_from_stage,
    CASE WHEN p_event_type='stage_changed' THEN v_to_stage ELSE NULL END,
    CASE WHEN p_event_type='interaction_logged' THEN p_channel ELSE NULL END,
    btrim(p_summary),
    CASE WHEN p_event_type='next_action_set' THEN btrim(p_next_action) ELSE NULL END,
    CASE WHEN p_event_type='next_action_set' THEN p_next_action_due ELSE NULL END,
    auth.uid()
  ) RETURNING id INTO v_event_id;

  INSERT INTO public.lead_customer_lifecycle (
    lead_id,stage,next_action,next_action_due,last_interaction_at,updated_by,updated_at
  ) VALUES (
    p_lead_id,
    v_to_stage,
    CASE WHEN p_event_type='next_action_set' THEN btrim(p_next_action) ELSE NULL END,
    CASE WHEN p_event_type='next_action_set' THEN p_next_action_due ELSE NULL END,
    CASE WHEN p_event_type='interaction_logged' THEN now() ELSE NULL END,
    auth.uid(),now()
  )
  ON CONFLICT (lead_id) DO UPDATE SET
    stage = CASE WHEN p_event_type='stage_changed' THEN EXCLUDED.stage
                 ELSE public.lead_customer_lifecycle.stage END,
    next_action = CASE WHEN p_event_type='next_action_set' THEN EXCLUDED.next_action
                       ELSE public.lead_customer_lifecycle.next_action END,
    next_action_due = CASE WHEN p_event_type='next_action_set' THEN EXCLUDED.next_action_due
                           ELSE public.lead_customer_lifecycle.next_action_due END,
    last_interaction_at = CASE WHEN p_event_type='interaction_logged' THEN now()
                               ELSE public.lead_customer_lifecycle.last_interaction_at END,
    updated_by = auth.uid(),
    updated_at = now();

  RETURN v_event_id;
END;
$lead_customer_lifecycle$;

REVOKE ALL ON FUNCTION public.reject_lead_customer_lifecycle_event_mutation() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.reject_lead_customer_lifecycle_event_mutation() TO service_role;
REVOKE ALL ON FUNCTION public.record_lead_customer_lifecycle_event(uuid,text,text,text,text,text,date) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.record_lead_customer_lifecycle_event(uuid,text,text,text,text,text,date) TO authenticated;

COMMIT;
