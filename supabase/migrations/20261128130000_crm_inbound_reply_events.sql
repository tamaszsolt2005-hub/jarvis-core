-- Persist inbound email replies as idempotent, system-attributed CRM events.
BEGIN;

ALTER TABLE public.lead_customer_lifecycle_events
  ADD COLUMN IF NOT EXISTS source_message_id text
  CHECK (source_message_id IS NULL OR length(btrim(source_message_id)) BETWEEN 1 AND 250);

ALTER TABLE public.lead_customer_lifecycle_events
  DROP CONSTRAINT IF EXISTS lead_customer_lifecycle_events_event_type_check;
ALTER TABLE public.lead_customer_lifecycle_events
  ADD CONSTRAINT lead_customer_lifecycle_events_event_type_check
  CHECK (event_type IN (
    'stage_changed','interaction_logged','next_action_set',
    'owner_assigned','inbound_reply_recorded'
  ));

CREATE UNIQUE INDEX IF NOT EXISTS lead_customer_lifecycle_events_inbound_message_uidx
  ON public.lead_customer_lifecycle_events (source_message_id)
  WHERE event_type = 'inbound_reply_recorded' AND source_message_id IS NOT NULL;

COMMENT ON COLUMN public.lead_customer_lifecycle_events.source_message_id IS
  'Idempotency key for an inbound email event; populated only by the service-role inbox worker.';

CREATE OR REPLACE FUNCTION public.record_crm_inbound_reply(
  p_lead_id uuid,
  p_message_id text,
  p_category text,
  p_summary text
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $crm_inbound_reply$
DECLARE
  v_stage text;
  v_target_stage text;
  v_event_id uuid;
  v_system_actor constant uuid := '00000000-0000-0000-0000-000000000000';
BEGIN
  IF p_message_id IS NULL OR length(btrim(p_message_id)) NOT BETWEEN 1 AND 250 THEN
    RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'crm_inbound_message_id_invalid';
  END IF;
  IF p_category IS NULL OR p_category NOT IN ('interested','later','rejected','opt_out','unknown') THEN
    RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'crm_inbound_reply_category_invalid';
  END IF;
  IF p_summary IS NULL OR length(btrim(p_summary)) NOT BETWEEN 5 AND 2000 THEN
    RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'crm_inbound_reply_summary_required';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM public.lead_review_states
    WHERE lead_id = p_lead_id AND review_status = 'approved'
  ) THEN
    RETURN NULL;
  END IF;

  INSERT INTO public.lead_customer_lifecycle (lead_id,stage,updated_by)
  VALUES (p_lead_id,'approved_lead',v_system_actor)
  ON CONFLICT (lead_id) DO NOTHING;

  SELECT stage INTO v_stage
  FROM public.lead_customer_lifecycle
  WHERE lead_id = p_lead_id
  FOR UPDATE;
  v_target_stage := CASE
    WHEN v_stage IN ('approved_lead','contacted') THEN 'responded'
    ELSE v_stage
  END;

  INSERT INTO public.lead_customer_lifecycle_events (
    lead_id,event_type,from_stage,to_stage,channel,summary,actor_id,source_message_id
  ) VALUES (
    p_lead_id,'inbound_reply_recorded',v_stage,v_target_stage,'email',
    btrim(p_summary),v_system_actor,btrim(p_message_id)
  )
  ON CONFLICT (source_message_id)
    WHERE event_type = 'inbound_reply_recorded' AND source_message_id IS NOT NULL
    DO NOTHING
  RETURNING id INTO v_event_id;

  IF v_event_id IS NULL THEN
    SELECT id INTO v_event_id
    FROM public.lead_customer_lifecycle_events
    WHERE event_type = 'inbound_reply_recorded'
      AND source_message_id = btrim(p_message_id);
    RETURN v_event_id;
  END IF;

  UPDATE public.lead_customer_lifecycle
  SET stage = v_target_stage,
      last_interaction_at = now(),
      updated_by = v_system_actor,
      updated_at = now()
  WHERE lead_id = p_lead_id;

  RETURN v_event_id;
END;
$crm_inbound_reply$;

REVOKE ALL ON FUNCTION public.record_crm_inbound_reply(uuid,text,text,text)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.record_crm_inbound_reply(uuid,text,text,text)
  TO service_role;

COMMIT;
