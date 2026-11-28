-- Secure CRM owner directory and audited assignment workflow.
BEGIN;

ALTER TABLE public.lead_customer_lifecycle
  ADD COLUMN IF NOT EXISTS assigned_to uuid
  REFERENCES auth.users(id) ON DELETE SET NULL;

ALTER TABLE public.lead_customer_lifecycle_events
  DROP CONSTRAINT IF EXISTS lead_customer_lifecycle_events_event_type_check;
ALTER TABLE public.lead_customer_lifecycle_events
  ADD CONSTRAINT lead_customer_lifecycle_events_event_type_check
  CHECK (event_type IN ('stage_changed','interaction_logged','next_action_set','owner_assigned'));

ALTER TABLE public.lead_customer_lifecycle_events
  ADD COLUMN IF NOT EXISTS assigned_to_user_id uuid;

CREATE INDEX IF NOT EXISTS lead_customer_lifecycle_assigned_to_idx
  ON public.lead_customer_lifecycle (assigned_to)
  WHERE assigned_to IS NOT NULL;

CREATE OR REPLACE FUNCTION public.list_crm_assignable_users()
RETURNS TABLE(user_id uuid, email text, display_name text, role text)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $crm_user_directory$
DECLARE
  v_role text := auth.jwt() -> 'app_metadata' ->> 'role';
BEGIN
  IF auth.uid() IS NULL OR COALESCE(v_role,'') NOT IN ('admin','operator') THEN
    RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'crm_user_directory_requires_admin_or_operator';
  END IF;

  RETURN QUERY
  SELECT u.id,
         u.email::text,
         COALESCE(
           NULLIF(btrim(u.raw_user_meta_data ->> 'full_name'), ''),
           NULLIF(btrim(u.raw_user_meta_data ->> 'name'), ''),
           u.email
         )::text,
         u.app_metadata ->> 'role'
  FROM auth.users AS u
  WHERE u.confirmed_at IS NOT NULL
    AND COALESCE(u.app_metadata ->> 'role','') IN ('admin','operator')
  ORDER BY COALESCE(
    NULLIF(btrim(u.raw_user_meta_data ->> 'full_name'), ''),
    NULLIF(btrim(u.raw_user_meta_data ->> 'name'), ''),
    u.email
  ), u.id;
END;
$crm_user_directory$;

CREATE OR REPLACE FUNCTION public.assign_lead_customer_owner(
  p_lead_id uuid,
  p_assignee_id uuid,
  p_note text
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $crm_owner_assignment$
DECLARE
  v_role text := auth.jwt() -> 'app_metadata' ->> 'role';
  v_old_assignee uuid;
  v_event_id uuid;
BEGIN
  IF auth.uid() IS NULL OR COALESCE(v_role,'') NOT IN ('admin','operator') THEN
    RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'crm_owner_assignment_requires_admin_or_operator';
  END IF;
  IF p_note IS NULL OR length(btrim(p_note)) NOT BETWEEN 5 AND 500 THEN
    RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'crm_owner_assignment_note_required';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM public.lead_review_states
    WHERE lead_id = p_lead_id AND review_status = 'approved'
  ) THEN
    RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'crm_owner_assignment_requires_approved_lead';
  END IF;
  IF p_assignee_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM auth.users AS u
    WHERE u.id = p_assignee_id
      AND u.confirmed_at IS NOT NULL
      AND COALESCE(u.app_metadata ->> 'role','') IN ('admin','operator')
  ) THEN
    RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'crm_owner_assignment_target_not_assignable';
  END IF;

  INSERT INTO public.lead_customer_lifecycle (lead_id, stage, updated_by)
  VALUES (p_lead_id, 'approved_lead', auth.uid())
  ON CONFLICT (lead_id) DO NOTHING;

  SELECT assigned_to INTO v_old_assignee
  FROM public.lead_customer_lifecycle
  WHERE lead_id = p_lead_id
  FOR UPDATE;

  IF v_old_assignee IS NOT DISTINCT FROM p_assignee_id THEN
    RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'crm_owner_assignment_unchanged';
  END IF;

  UPDATE public.lead_customer_lifecycle
  SET assigned_to = p_assignee_id, updated_by = auth.uid(), updated_at = now()
  WHERE lead_id = p_lead_id;

  INSERT INTO public.lead_customer_lifecycle_events (
    lead_id, event_type, summary, actor_id, assigned_to_user_id
  ) VALUES (
    p_lead_id, 'owner_assigned', btrim(p_note), auth.uid(), p_assignee_id
  ) RETURNING id INTO v_event_id;

  RETURN v_event_id;
END;
$crm_owner_assignment$;

REVOKE ALL ON FUNCTION public.list_crm_assignable_users() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.list_crm_assignable_users() TO authenticated;
REVOKE ALL ON FUNCTION public.assign_lead_customer_owner(uuid,uuid,text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.assign_lead_customer_owner(uuid,uuid,text) TO authenticated;

COMMIT;
