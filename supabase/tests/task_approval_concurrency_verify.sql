DO $$
DECLARE
  task_count integer;
  audit_count integer;
  operation_count integer;
  approval_consumed boolean;
BEGIN
  SELECT count(*) INTO task_count
    FROM public.tasks
   WHERE operation_id = '20000000-0000-4000-8000-000000000002'::uuid;
  SELECT count(*) INTO audit_count
    FROM public.logs
   WHERE operation_id = '20000000-0000-4000-8000-000000000002'::uuid
     AND status IN ('pending', 'success');
  SELECT count(*) INTO operation_count
    FROM private.task_action_operations
   WHERE operation_id = '20000000-0000-4000-8000-000000000002'::uuid
     AND result IS NOT NULL AND completed_at IS NOT NULL;
  SELECT consumed_at IS NOT NULL INTO approval_consumed
    FROM private.task_approvals
   WHERE token_hash = repeat('a', 64);
  IF task_count <> 1 OR audit_count <> 2 OR operation_count <> 1
     OR approval_consumed IS DISTINCT FROM true THEN
    RAISE EXCEPTION
      'Concurrency invariant failed: tasks %, audit rows %, operations %, consumed %',
      task_count, audit_count, operation_count, approval_consumed;
  END IF;
END
$$;
DROP TRIGGER IF EXISTS task_approval_race_pause ON public.tasks;
DROP FUNCTION IF EXISTS public.test_pause_task_approval_race();
