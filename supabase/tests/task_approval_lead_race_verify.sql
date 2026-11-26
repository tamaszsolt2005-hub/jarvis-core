DO $$
DECLARE
  v_open_tasks integer;
  v_successes integer;
  v_blocked integer;
BEGIN
  SELECT count(*) INTO v_open_tasks FROM public.tasks
   WHERE lead_id = '74000000-0000-4000-8000-000000000001'::uuid AND status = 'open';
  SELECT count(*) INTO v_successes FROM private.task_action_operations
   WHERE operation_id IN (
     '74000000-0000-4000-8000-000000000002'::uuid,
     '74000000-0000-4000-8000-000000000003'::uuid
   ) AND result ->> 'status' = 'success';
  SELECT count(*) INTO v_blocked FROM private.task_action_operations
   WHERE operation_id IN (
     '74000000-0000-4000-8000-000000000002'::uuid,
     '74000000-0000-4000-8000-000000000003'::uuid
   ) AND result ->> 'status' = 'blocked';

  IF v_open_tasks <> 1 OR v_successes <> 1 OR v_blocked <> 1 THEN
    RAISE EXCEPTION
      'Lead task race failed: open tasks %, successful operations %, blocked operations %',
      v_open_tasks, v_successes, v_blocked;
  END IF;
END
$$;

ALTER TABLE public.logs ENABLE TRIGGER logs_audit_hash_chain;
DROP TRIGGER IF EXISTS task_lead_race_pause ON public.tasks;
DROP FUNCTION IF EXISTS public.test_pause_lead_task_race();
DELETE FROM public.tasks
 WHERE operation_id IN (
   '74000000-0000-4000-8000-000000000002'::uuid,
   '74000000-0000-4000-8000-000000000003'::uuid
 );
DELETE FROM private.task_action_operations
 WHERE operation_id IN (
   '74000000-0000-4000-8000-000000000002'::uuid,
   '74000000-0000-4000-8000-000000000003'::uuid
 );
DELETE FROM private.task_approvals
 WHERE token_hash IN (repeat('a', 64), repeat('b', 64));
DELETE FROM public.leads WHERE id = '74000000-0000-4000-8000-000000000001'::uuid;
