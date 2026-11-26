-- Prove that a failure in the final audit append rolls back the task,
-- the operation ledger, and approval consumption in the same transaction.
-- Run only against the isolated PostgreSQL CI database after migrations
-- 20261125150000 and 20261125160000 have been applied.

SET request.jwt.claims = '{"role":"service_role"}';

DO $seed$
BEGIN
  IF NOT public.issue_pending_approval(
    repeat('c', 64),
    'legacy:50000000-0000-4000-8000-000000000005',
    '{"type":"create","operation_id":"60000000-0000-4000-8000-000000000006","title":"Audit rollback fixture","priority":"normal","due_at":null,"notes":""}'::jsonb,
    300
  ) THEN
    RAISE EXCEPTION 'Could not seed audit rollback approval';
  END IF;
END
$seed$;

CREATE OR REPLACE FUNCTION public.test_reject_task_success_audit()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.module = 'task_actions'
     AND NEW.operation_id = '60000000-0000-4000-8000-000000000006'::uuid
     AND NEW.status = 'success' THEN
    RAISE EXCEPTION 'injected final audit failure' USING ERRCODE = '58000';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER task_audit_failure_injection
  BEFORE INSERT ON public.logs
  FOR EACH ROW
  EXECUTE FUNCTION public.test_reject_task_success_audit();

DO $verify$
DECLARE
  audit_failed boolean := false;
  approval_consumed boolean;
BEGIN
  BEGIN
    PERFORM public.execute_approved_task_action(
      repeat('c', 64),
      'legacy:50000000-0000-4000-8000-000000000005',
      '60000000-0000-4000-8000-000000000006'::uuid,
      '{"type":"create","operation_id":"60000000-0000-4000-8000-000000000006","title":"Audit rollback fixture","priority":"normal","due_at":null,"notes":""}'::jsonb
    );
  EXCEPTION WHEN SQLSTATE '58000' THEN
    audit_failed := true;
  END;

  IF NOT audit_failed THEN
    RAISE EXCEPTION 'Expected the injected final audit failure';
  END IF;

  IF EXISTS (
    SELECT 1 FROM public.tasks
     WHERE operation_id = '60000000-0000-4000-8000-000000000006'::uuid
  ) THEN
    RAISE EXCEPTION 'Task row survived a failed final audit append';
  END IF;

  IF EXISTS (
    SELECT 1 FROM private.task_action_operations
     WHERE operation_id = '60000000-0000-4000-8000-000000000006'::uuid
  ) THEN
    RAISE EXCEPTION 'Operation ledger row survived a failed final audit append';
  END IF;

  IF EXISTS (
    SELECT 1 FROM public.logs
     WHERE operation_id = '60000000-0000-4000-8000-000000000006'::uuid
  ) THEN
    RAISE EXCEPTION 'Partial audit rows survived the failed transaction';
  END IF;

  SELECT consumed_at IS NOT NULL
    INTO approval_consumed
    FROM private.task_approvals
   WHERE token_hash = repeat('c', 64);

  IF approval_consumed IS DISTINCT FROM false THEN
    RAISE EXCEPTION 'Approval consumption was not rolled back after audit failure';
  END IF;
END
$verify$;

DROP TRIGGER task_audit_failure_injection ON public.logs;
DROP FUNCTION public.test_reject_task_success_audit();

DELETE FROM private.task_approvals
 WHERE token_hash = repeat('c', 64);
