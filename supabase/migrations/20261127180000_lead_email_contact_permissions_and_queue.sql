-- Contact authorization, suppression controls and a non-sending eligibility queue.
-- Repository-only migration. No sender/dispatcher is introduced or enabled.
BEGIN;

CREATE TABLE IF NOT EXISTS public.lead_email_contact_permissions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id uuid NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
  email_normalized text NOT NULL CHECK (email_normalized = lower(btrim(email_normalized))),
  status text NOT NULL CHECK (status IN ('authorized','revoked')),
  legal_basis text NOT NULL CHECK (legal_basis IN ('explicit_consent','legitimate_interest_reviewed','contractual_necessity','other_reviewed')),
  evidence_url text,
  evidence_note text NOT NULL CHECK (length(btrim(evidence_note)) BETWEEN 5 AND 2000),
  verified_at timestamptz NOT NULL DEFAULT now(),
  valid_until timestamptz,
  reviewed_by uuid NOT NULL DEFAULT auth.uid(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (lead_id, email_normalized),
  CHECK (valid_until IS NULL OR valid_until > verified_at),
  CHECK (evidence_url IS NULL OR (length(evidence_url) <= 2048 AND evidence_url ~* '^https://'))
);

CREATE TABLE IF NOT EXISTS public.lead_email_contact_permission_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id uuid NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
  email_normalized text NOT NULL,
  event_type text NOT NULL CHECK (event_type IN ('authorized','revoked','updated')),
  legal_basis text NOT NULL,
  evidence_note text NOT NULL,
  evidence_url text,
  actor_id uuid NOT NULL DEFAULT auth.uid(),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.email_suppression_list (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email_normalized text NOT NULL UNIQUE CHECK (email_normalized = lower(btrim(email_normalized))),
  reason text NOT NULL CHECK (reason IN ('unsubscribe','direct_objection','complaint','invalid_address','manual_suppression')),
  note text NOT NULL CHECK (length(btrim(note)) BETWEEN 3 AND 1000),
  source_url text,
  created_by uuid NOT NULL DEFAULT auth.uid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (source_url IS NULL OR (length(source_url) <= 2048 AND source_url ~* '^https://'))
);

CREATE TABLE IF NOT EXISTS public.lead_email_send_queue (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  draft_id uuid NOT NULL UNIQUE REFERENCES public.lead_email_drafts(id) ON DELETE CASCADE,
  lead_id uuid NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
  recipient_email text NOT NULL,
  status text NOT NULL CHECK (status IN ('blocked','ready_for_manual_review','cancelled')),
  block_reason text,
  evaluated_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.lead_email_send_queue_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  queue_id uuid NOT NULL REFERENCES public.lead_email_send_queue(id) ON DELETE CASCADE,
  event_type text NOT NULL CHECK (event_type IN ('evaluated_blocked','evaluated_ready','cancelled','suppressed')),
  detail text,
  actor_id uuid NOT NULL DEFAULT auth.uid(),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS lead_email_permissions_email_idx
  ON public.lead_email_contact_permissions(email_normalized, status);
CREATE INDEX IF NOT EXISTS email_suppression_email_idx
  ON public.email_suppression_list(email_normalized);
CREATE INDEX IF NOT EXISTS lead_email_send_queue_status_idx
  ON public.lead_email_send_queue(status, evaluated_at DESC);

CREATE OR REPLACE FUNCTION public.reject_lead_email_control_history_mutation()
RETURNS trigger LANGUAGE plpgsql SET search_path = ''
AS $email_control_history_guard$
BEGIN
  RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'email_control_history_is_append_only';
END;
$email_control_history_guard$;

CREATE TRIGGER lead_email_permission_events_immutable
BEFORE UPDATE OR DELETE ON public.lead_email_contact_permission_events
FOR EACH ROW EXECUTE FUNCTION public.reject_lead_email_control_history_mutation();
CREATE TRIGGER lead_email_queue_events_immutable
BEFORE UPDATE OR DELETE ON public.lead_email_send_queue_events
FOR EACH ROW EXECUTE FUNCTION public.reject_lead_email_control_history_mutation();

CREATE OR REPLACE FUNCTION public.record_lead_email_contact_permission(
  p_lead_id uuid,
  p_email text,
  p_status text,
  p_legal_basis text,
  p_evidence_note text,
  p_evidence_url text DEFAULT NULL,
  p_valid_until timestamptz DEFAULT NULL
)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
AS $record_email_contact_permission$
DECLARE
  v_actor uuid := auth.uid();
  v_role text := auth.jwt() -> 'app_metadata' ->> 'role';
  v_email text := lower(btrim(p_email));
  v_id uuid;
BEGIN
  IF v_actor IS NULL OR COALESCE(v_role,'') NOT IN ('admin','operator') THEN
    RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'email_permission_requires_admin_or_operator';
  END IF;
  IF v_email !~ '^[^[:space:]@,;<>]+@[^[:space:]@,;<>]+[.][^[:space:]@,;<>]+$'
     OR p_status NOT IN ('authorized','revoked')
     OR p_legal_basis NOT IN ('explicit_consent','legitimate_interest_reviewed','contractual_necessity','other_reviewed')
     OR length(btrim(COALESCE(p_evidence_note,''))) NOT BETWEEN 5 AND 2000
     OR (p_evidence_url IS NOT NULL AND (length(p_evidence_url) > 2048 OR p_evidence_url !~* '^https://'))
     OR (p_valid_until IS NOT NULL AND p_valid_until <= now()) THEN
    RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'email_permission_fields_invalid';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM public.lead_email_drafts d
    WHERE d.lead_id = p_lead_id AND lower(d.recipient_email) = v_email
  ) THEN
    RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'permission_email_must_match_lead_draft_recipient';
  END IF;
  INSERT INTO public.lead_email_contact_permissions
    (lead_id,email_normalized,status,legal_basis,evidence_note,evidence_url,verified_at,valid_until,reviewed_by,updated_at)
  VALUES
    (p_lead_id,v_email,p_status,p_legal_basis,btrim(p_evidence_note),p_evidence_url,now(),p_valid_until,v_actor,now())
  ON CONFLICT (lead_id,email_normalized) DO UPDATE SET
    status=EXCLUDED.status, legal_basis=EXCLUDED.legal_basis,
    evidence_note=EXCLUDED.evidence_note, evidence_url=EXCLUDED.evidence_url,
    verified_at=now(), valid_until=EXCLUDED.valid_until,
    reviewed_by=v_actor, updated_at=now()
  RETURNING id INTO v_id;

  INSERT INTO public.lead_email_contact_permission_events
    (lead_id,email_normalized,event_type,legal_basis,evidence_note,evidence_url,actor_id)
  VALUES (p_lead_id,v_email,p_status,p_legal_basis,btrim(p_evidence_note),p_evidence_url,v_actor);

  IF p_status = 'revoked' THEN
    INSERT INTO public.email_suppression_list(email_normalized,reason,note,source_url,created_by)
    VALUES (v_email,'direct_objection','A kapcsolattartási jogosultság visszavonva.',p_evidence_url,v_actor)
    ON CONFLICT (email_normalized) DO NOTHING;
  END IF;
  RETURN v_id;
END;
$record_email_contact_permission$;

CREATE OR REPLACE FUNCTION public.suppress_lead_email_recipient(
  p_email text, p_reason text, p_note text, p_source_url text DEFAULT NULL
)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
AS $suppress_email_recipient$
DECLARE
  v_actor uuid := auth.uid();
  v_role text := auth.jwt() -> 'app_metadata' ->> 'role';
  v_email text := lower(btrim(p_email));
  v_id uuid;
BEGIN
  IF v_actor IS NULL OR COALESCE(v_role,'') NOT IN ('admin','operator') THEN
    RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'email_suppression_requires_admin_or_operator';
  END IF;
  IF v_email !~ '^[^[:space:]@,;<>]+@[^[:space:]@,;<>]+[.][^[:space:]@,;<>]+$'
     OR p_reason NOT IN ('unsubscribe','direct_objection','complaint','invalid_address','manual_suppression')
     OR length(btrim(COALESCE(p_note,''))) NOT BETWEEN 3 AND 1000
     OR (p_source_url IS NOT NULL AND (length(p_source_url) > 2048 OR p_source_url !~* '^https://')) THEN
    RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'email_suppression_fields_invalid';
  END IF;
  INSERT INTO public.email_suppression_list(email_normalized,reason,note,source_url,created_by)
  VALUES (v_email,p_reason,btrim(p_note),p_source_url,v_actor)
  ON CONFLICT (email_normalized) DO UPDATE SET
    reason=EXCLUDED.reason, note=EXCLUDED.note, source_url=EXCLUDED.source_url,
    created_by=v_actor, created_at=now()
  RETURNING id INTO v_id;
  UPDATE public.lead_email_send_queue
  SET status='blocked', block_reason='suppressed_recipient', evaluated_at=now(), updated_at=now()
  WHERE lower(recipient_email)=v_email AND status <> 'cancelled';
  INSERT INTO public.lead_email_send_queue_events(queue_id,event_type,detail,actor_id)
  SELECT id,'suppressed','A cím felkerült a leiratkozási/tiltólistára.',v_actor
  FROM public.lead_email_send_queue WHERE lower(recipient_email)=v_email;
  RETURN v_id;
END;
$suppress_email_recipient$;

CREATE OR REPLACE FUNCTION public.evaluate_lead_email_send_eligibility(p_draft_id uuid)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
AS $evaluate_email_eligibility$
DECLARE
  v_actor uuid := auth.uid();
  v_role text := auth.jwt() -> 'app_metadata' ->> 'role';
  v_draft public.lead_email_drafts%ROWTYPE;
  v_email text;
  v_status text := 'blocked';
  v_reason text := 'missing_or_unapproved_draft';
  v_queue_id uuid;
BEGIN
  IF v_actor IS NULL OR COALESCE(v_role,'') NOT IN ('admin','operator') THEN
    RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'email_queue_requires_admin_or_operator';
  END IF;
  SELECT * INTO v_draft FROM public.lead_email_drafts WHERE id=p_draft_id;
  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE = '23503', MESSAGE = 'email_draft_not_found'; END IF;
  v_email := lower(btrim(COALESCE(v_draft.recipient_email,'')));

  IF v_draft.status <> 'approved' THEN
    v_reason := 'draft_not_approved';
  ELSIF EXISTS (SELECT 1 FROM public.email_suppression_list s WHERE s.email_normalized=v_email) THEN
    v_reason := 'recipient_suppressed';
  ELSIF NOT EXISTS (
    SELECT 1 FROM public.lead_email_contact_permissions p
    WHERE p.lead_id=v_draft.lead_id AND p.email_normalized=v_email
      AND p.status='authorized'
      AND (p.valid_until IS NULL OR p.valid_until > now())
  ) THEN
    v_reason := 'no_valid_contact_permission';
  ELSE
    v_status := 'ready_for_manual_review';
    v_reason := NULL;
  END IF;

  INSERT INTO public.lead_email_send_queue(draft_id,lead_id,recipient_email,status,block_reason,evaluated_at,updated_at)
  VALUES (p_draft_id,v_draft.lead_id,v_email,v_status,v_reason,now(),now())
  ON CONFLICT (draft_id) DO UPDATE SET
    recipient_email=EXCLUDED.recipient_email,status=EXCLUDED.status,
    block_reason=EXCLUDED.block_reason,evaluated_at=now(),updated_at=now()
  RETURNING id INTO v_queue_id;

  INSERT INTO public.lead_email_send_queue_events(queue_id,event_type,detail,actor_id)
  VALUES (
    v_queue_id,
    CASE WHEN v_status='ready_for_manual_review' THEN 'evaluated_ready' ELSE 'evaluated_blocked' END,
    COALESCE(v_reason,'Eligibility checks passed; delivery remains disabled.'),v_actor
  );
  RETURN v_queue_id;
END;
$evaluate_email_eligibility$;

ALTER TABLE public.lead_email_contact_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lead_email_contact_permission_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.email_suppression_list ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lead_email_send_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lead_email_send_queue_events ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.lead_email_contact_permissions,
  public.lead_email_contact_permission_events, public.email_suppression_list,
  public.lead_email_send_queue, public.lead_email_send_queue_events
  FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT ON TABLE public.lead_email_contact_permissions,
  public.lead_email_contact_permission_events, public.email_suppression_list,
  public.lead_email_send_queue, public.lead_email_send_queue_events
  TO authenticated, service_role;

DO $email_control_rls$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'lead_email_contact_permissions','lead_email_contact_permission_events',
    'email_suppression_list','lead_email_send_queue','lead_email_send_queue_events'
  ] LOOP
    EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I',t || '_role_read',t);
    EXECUTE format(
      'CREATE POLICY %I ON public.%I FOR SELECT TO authenticated USING ((SELECT auth.jwt() -> ''app_metadata'' ->> ''role'') IN (''admin'',''operator'',''reader''))',
      t || '_role_read',t
    );
  END LOOP;
END;
$email_control_rls$;

REVOKE ALL ON FUNCTION public.reject_lead_email_control_history_mutation() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.record_lead_email_contact_permission(uuid,text,text,text,text,text,timestamptz) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.suppress_lead_email_recipient(text,text,text,text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.evaluate_lead_email_send_eligibility(uuid) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.reject_lead_email_control_history_mutation() TO authenticated;
GRANT EXECUTE ON FUNCTION public.record_lead_email_contact_permission(uuid,text,text,text,text,text,timestamptz) TO authenticated;
GRANT EXECUTE ON FUNCTION public.suppress_lead_email_recipient(text,text,text,text) TO authenticated;
GRANT EXECUTE ON FUNCTION public.evaluate_lead_email_send_eligibility(uuid) TO authenticated;

COMMENT ON TABLE public.lead_email_send_queue IS
  'Non-sending eligibility register only. ready_for_manual_review is not authorization to deliver.';
COMMENT ON TABLE public.email_suppression_list IS
  'Global email suppression list; a match always blocks eligibility regardless of lead or campaign.';

COMMIT;
