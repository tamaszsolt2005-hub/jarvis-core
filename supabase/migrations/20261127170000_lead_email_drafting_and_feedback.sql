-- Lead-linked email drafting, human approval and structured style feedback.
-- Repository-only until separately reviewed and applied. Delivery remains hard-disabled.
BEGIN;

CREATE TABLE IF NOT EXISTS public.lead_email_drafts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id uuid NOT NULL UNIQUE REFERENCES public.leads(id) ON DELETE CASCADE,
  subject text NOT NULL DEFAULT '' CHECK (length(subject) <= 200),
  body text NOT NULL DEFAULT '' CHECK (length(body) <= 20000),
  recipient_email text,
  recipient_source_url text,
  status text NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','approved','rejected')),
  generated_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  approved_by uuid,
  approved_at timestamptz,
  CHECK (recipient_email IS NULL OR (length(recipient_email) <= 320 AND recipient_email ~* '^[^[:space:]@,;<>]+@[^[:space:]@,;<>]+[.][^[:space:]@,;<>]+$')),
  CHECK (recipient_source_url IS NULL OR (length(recipient_source_url) <= 2048 AND recipient_source_url ~* '^https?://'))
);

CREATE TABLE IF NOT EXISTS public.lead_email_draft_revisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  draft_id uuid NOT NULL REFERENCES public.lead_email_drafts(id) ON DELETE CASCADE,
  subject text NOT NULL CHECK (length(subject) <= 200),
  body text NOT NULL CHECK (length(body) <= 20000),
  actor_id uuid NOT NULL DEFAULT auth.uid(),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.lead_email_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  draft_id uuid NOT NULL REFERENCES public.lead_email_drafts(id) ON DELETE CASCADE,
  lead_id uuid NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
  event_type text NOT NULL CHECK (event_type IN ('generated','edited','approved','rejected','reopened')),
  note text,
  actor_id uuid NOT NULL DEFAULT auth.uid(),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.email_style_feedback (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  draft_id uuid NOT NULL REFERENCES public.lead_email_drafts(id) ON DELETE CASCADE,
  lead_id uuid NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
  category text NOT NULL CHECK (category IN ('too_formal','too_long','too_generic','not_persuasive','other')),
  note text NOT NULL CHECK (length(btrim(note)) BETWEEN 5 AND 2000),
  actor_id uuid NOT NULL DEFAULT auth.uid(),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.email_style_preferences (
  scope text PRIMARY KEY CHECK (scope = 'global'),
  formality text NOT NULL DEFAULT 'neutral' CHECK (formality IN ('neutral','direct')),
  concision text NOT NULL DEFAULT 'standard' CHECK (concision IN ('standard','concise')),
  personalization text NOT NULL DEFAULT 'high' CHECK (personalization IN ('standard','high')),
  assertiveness text NOT NULL DEFAULT 'balanced' CHECK (assertiveness IN ('balanced','direct')),
  updated_by uuid,
  updated_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO public.email_style_preferences (scope) VALUES ('global') ON CONFLICT (scope) DO NOTHING;

CREATE INDEX IF NOT EXISTS lead_email_events_lead_created_idx
  ON public.lead_email_events (lead_id, created_at DESC);
CREATE INDEX IF NOT EXISTS lead_email_feedback_created_idx
  ON public.email_style_feedback (created_at DESC);

CREATE OR REPLACE FUNCTION public.reject_lead_email_history_mutation()
RETURNS trigger LANGUAGE plpgsql SET search_path = ''
AS $email_history_guard$
BEGIN
  RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'lead_email_history_is_append_only';
END;
$email_history_guard$;

DROP TRIGGER IF EXISTS lead_email_revisions_immutable_guard ON public.lead_email_draft_revisions;
CREATE TRIGGER lead_email_revisions_immutable_guard
BEFORE UPDATE OR DELETE ON public.lead_email_draft_revisions
FOR EACH ROW EXECUTE FUNCTION public.reject_lead_email_history_mutation();
DROP TRIGGER IF EXISTS lead_email_events_immutable_guard ON public.lead_email_events;
CREATE TRIGGER lead_email_events_immutable_guard
BEFORE UPDATE OR DELETE ON public.lead_email_events
FOR EACH ROW EXECUTE FUNCTION public.reject_lead_email_history_mutation();
DROP TRIGGER IF EXISTS email_style_feedback_immutable_guard ON public.email_style_feedback;
CREATE TRIGGER email_style_feedback_immutable_guard
BEFORE UPDATE OR DELETE ON public.email_style_feedback
FOR EACH ROW EXECUTE FUNCTION public.reject_lead_email_history_mutation();

CREATE OR REPLACE FUNCTION public.record_lead_email_event(
  p_draft_id uuid,
  p_event_type text,
  p_note text DEFAULT NULL,
  p_feedback_category text DEFAULT NULL
)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
AS $record_lead_email_event$
DECLARE
  v_role text := auth.jwt() -> 'app_metadata' ->> 'role';
  v_actor uuid := auth.uid();
  v_draft public.lead_email_drafts%ROWTYPE;
  v_note text := NULLIF(btrim(p_note), '');
  v_event_id uuid;
BEGIN
  IF v_actor IS NULL OR COALESCE(v_role,'') NOT IN ('admin','operator') THEN
    RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'lead_email_requires_admin_or_operator';
  END IF;
  SELECT * INTO v_draft FROM public.lead_email_drafts WHERE id = p_draft_id FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION USING ERRCODE = '23503', MESSAGE = 'lead_email_draft_not_found';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM public.lead_review_states
    WHERE lead_id = v_draft.lead_id AND review_status = 'approved'
  ) THEN
    RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'lead_email_requires_approved_lead';
  END IF;

  IF p_event_type = 'approved' THEN
    IF v_draft.recipient_email IS NULL OR v_draft.recipient_source_url IS NULL
       OR length(btrim(v_draft.subject)) = 0 OR length(btrim(v_draft.body)) < 20 THEN
      RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'lead_email_recipient_source_and_content_required';
    END IF;
    UPDATE public.lead_email_drafts SET status = 'approved',
      approved_by = v_actor, approved_at = now(), updated_at = now()
    WHERE id = p_draft_id;
  ELSIF p_event_type = 'rejected' THEN
    IF v_note IS NULL OR length(v_note) < 5 OR length(v_note) > 2000
       OR p_feedback_category IS NULL OR p_feedback_category NOT IN ('too_formal','too_long','too_generic','not_persuasive','other') THEN
      RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'lead_email_rejection_feedback_required';
    END IF;
    UPDATE public.lead_email_drafts SET status = 'rejected',
      approved_by = NULL, approved_at = NULL, updated_at = now()
    WHERE id = p_draft_id;
    INSERT INTO public.email_style_feedback(draft_id,lead_id,category,note,actor_id)
    VALUES (p_draft_id,v_draft.lead_id,p_feedback_category,v_note,v_actor);
    UPDATE public.email_style_preferences SET
      formality = CASE WHEN p_feedback_category = 'too_formal' THEN 'direct' ELSE formality END,
      concision = CASE WHEN p_feedback_category = 'too_long' THEN 'concise' ELSE concision END,
      personalization = CASE WHEN p_feedback_category = 'too_generic' THEN 'high' ELSE personalization END,
      assertiveness = CASE WHEN p_feedback_category = 'not_persuasive' THEN 'direct' ELSE assertiveness END,
      updated_by = v_actor, updated_at = now()
    WHERE scope = 'global';
  ELSIF p_event_type = 'reopened' THEN
    UPDATE public.lead_email_drafts SET status = 'draft', approved_by = NULL,
      approved_at = NULL, updated_at = now() WHERE id = p_draft_id;
  ELSIF p_event_type NOT IN ('generated','edited') THEN
    RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'lead_email_event_type_invalid';
  END IF;

  INSERT INTO public.lead_email_events(draft_id,lead_id,event_type,note,actor_id)
  VALUES (p_draft_id,v_draft.lead_id,p_event_type,v_note,v_actor)
  RETURNING id INTO v_event_id;
  RETURN v_event_id;
END;
$record_lead_email_event$;

ALTER TABLE public.lead_email_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lead_email_draft_revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lead_email_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.email_style_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.email_style_preferences ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.lead_email_drafts, public.lead_email_draft_revisions,
  public.lead_email_events, public.email_style_feedback, public.email_style_preferences
  FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT ON TABLE public.lead_email_drafts, public.lead_email_draft_revisions,
  public.lead_email_events, public.email_style_feedback, public.email_style_preferences
  TO authenticated, service_role;
GRANT INSERT (lead_id,subject,body,recipient_email,recipient_source_url),
  UPDATE (recipient_email,recipient_source_url,subject,body,updated_at)
  ON TABLE public.lead_email_drafts TO authenticated;
GRANT INSERT (draft_id,subject,body) ON TABLE public.lead_email_draft_revisions TO authenticated;

DO $email_rls$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'lead_email_drafts','lead_email_draft_revisions','lead_email_events',
    'email_style_feedback','email_style_preferences'
  ] LOOP
    EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', t || '_role_read', t);
    EXECUTE format(
      'CREATE POLICY %I ON public.%I FOR SELECT TO authenticated USING ((SELECT auth.jwt() -> ''app_metadata'' ->> ''role'') IN (''admin'',''operator'',''reader''))',
      t || '_role_read', t
    );
  END LOOP;
END;
$email_rls$;

DROP POLICY IF EXISTS lead_email_drafts_operator_write ON public.lead_email_drafts;
CREATE POLICY lead_email_drafts_operator_write ON public.lead_email_drafts
  FOR ALL TO authenticated
  USING ((SELECT auth.jwt() -> 'app_metadata' ->> 'role') IN ('admin','operator'))
  WITH CHECK ((SELECT auth.jwt() -> 'app_metadata' ->> 'role') IN ('admin','operator'));
DROP POLICY IF EXISTS lead_email_revisions_operator_insert ON public.lead_email_draft_revisions;
CREATE POLICY lead_email_revisions_operator_insert ON public.lead_email_draft_revisions
  FOR INSERT TO authenticated
  WITH CHECK ((SELECT auth.jwt() -> 'app_metadata' ->> 'role') IN ('admin','operator'));
DROP POLICY IF EXISTS email_style_preferences_operator_write ON public.email_style_preferences;
CREATE POLICY email_style_preferences_operator_write ON public.email_style_preferences
  FOR UPDATE TO authenticated
  USING ((SELECT auth.jwt() -> 'app_metadata' ->> 'role') IN ('admin','operator'))
  WITH CHECK ((SELECT auth.jwt() -> 'app_metadata' ->> 'role') IN ('admin','operator'));

REVOKE ALL ON FUNCTION public.reject_lead_email_history_mutation() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.record_lead_email_event(uuid,text,text,text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.reject_lead_email_history_mutation() TO authenticated;
GRANT EXECUTE ON FUNCTION public.record_lead_email_event(uuid,text,text,text) TO authenticated;

COMMENT ON TABLE public.lead_email_drafts IS
  'One editable, lead-linked outreach draft per approved lead. Approval does not enqueue or send email.';
COMMENT ON TABLE public.email_style_feedback IS
  'Append-only structured human feedback; notes are not executed as model instructions.';
COMMENT ON TABLE public.email_style_preferences IS
  'Explicit global style controls derived from fixed feedback categories; not model retraining.';

COMMIT;
