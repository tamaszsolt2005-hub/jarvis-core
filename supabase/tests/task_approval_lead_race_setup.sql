-- Prepare two independently approved operations for the same lead.
SET request.jwt.claims = '{"role":"service_role"}';

-- Avoid the global append-only audit-chain row lock masking the per-lead lock
-- under test. The trigger is restored by the verification script.
ALTER TABLE public.logs DISABLE TRIGGER logs_audit_hash_chain;

INSERT INTO public.leads (id, company_name, status)
VALUES ('74000000-0000-4000-8000-000000000001', 'Lead task race fixture', 'research');

DO $$
BEGIN
  IF NOT public.issue_pending_approval(
    repeat('a', 64),
    'legacy:74000000-0000-4000-8000-000000000004',
    '{"type":"create","operation_id":"74000000-0000-4000-8000-000000000002","title":"Lead race first","priority":"normal","due_at":null,"notes":"","lead_id":"74000000-0000-4000-8000-000000000001"}'::jsonb,
    300
  ) THEN RAISE EXCEPTION 'Could not issue first lead-race approval'; END IF;

  IF NOT public.issue_pending_approval(
    repeat('b', 64),
    'legacy:74000000-0000-4000-8000-000000000005',
    '{"type":"create","operation_id":"74000000-0000-4000-8000-000000000003","title":"Lead race second","priority":"normal","due_at":null,"notes":"","lead_id":"74000000-0000-4000-8000-000000000001"}'::jsonb,
    300
  ) THEN RAISE EXCEPTION 'Could not issue second lead-race approval'; END IF;
END
$$;

CREATE OR REPLACE FUNCTION public.test_pause_lead_task_race()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.lead_id = '74000000-0000-4000-8000-000000000001'::uuid THEN
    PERFORM pg_sleep(3);
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER task_lead_race_pause
  BEFORE INSERT ON public.tasks
  FOR EACH ROW EXECUTE FUNCTION public.test_pause_lead_task_race();
