-- Verify the production legacy-mode path: service_role can execute the
-- approval RPC even after direct task-table writes have been revoked.
SET request.jwt.claims = '{"role":"service_role"}';
DO $$
BEGIN
  IF NOT public.issue_pending_approval(
    repeat('b', 64),
    'legacy:30000000-0000-4000-8000-000000000003',
    '{"type":"create","operation_id":"40000000-0000-4000-8000-000000000004","title":"Legacy RPC task fixture","priority":"normal","due_at":null,"notes":""}'::jsonb,
    300
  ) THEN
    RAISE EXCEPTION 'Could not seed service-role approval';
  END IF;
END
$$;

SELECT public.execute_approved_task_action(
  repeat('b', 64),
  'legacy:30000000-0000-4000-8000-000000000003',
  '40000000-0000-4000-8000-000000000004'::uuid,
  '{"type":"create","operation_id":"40000000-0000-4000-8000-000000000004","title":"Legacy RPC task fixture","priority":"normal","due_at":null,"notes":""}'::jsonb
);

DO $$
DECLARE
  task_count integer;
  audit_count integer;
  operation_count integer;
  approval_consumed boolean;
BEGIN
  SELECT count(*) INTO task_count FROM public.tasks
   WHERE operation_id = '40000000-0000-4000-8000-000000000004'::uuid;
  SELECT count(*) INTO audit_count FROM public.logs
   WHERE operation_id = '40000000-0000-4000-8000-000000000004'::uuid
     AND status IN ('pending', 'success');
  SELECT count(*) INTO operation_count FROM private.task_action_operations
   WHERE operation_id = '40000000-0000-4000-8000-000000000004'::uuid
     AND result IS NOT NULL AND completed_at IS NOT NULL;
  SELECT consumed_at IS NOT NULL INTO approval_consumed FROM private.task_approvals
   WHERE token_hash = repeat('b', 64);
  IF task_count <> 1 OR audit_count <> 2 OR operation_count <> 1
     OR approval_consumed IS DISTINCT FROM true THEN
    RAISE EXCEPTION 'Legacy service-role RPC failed: tasks %, audit %, operations %, consumed %',
      task_count, audit_count, operation_count, approval_consumed;
  END IF;
  IF has_table_privilege('service_role', 'public.tasks', 'INSERT')
     OR has_table_privilege('service_role', 'public.tasks', 'UPDATE')
     OR has_table_privilege('service_role', 'public.tasks', 'DELETE') THEN
    RAISE EXCEPTION 'service_role retained direct task table mutation privileges';
  END IF;
END
$$;


-- Prove actual service_role statements fail, not only that catalog ACLs look safe.
SET ROLE service_role;
DO $direct_dml_denied$
DECLARE
  insert_denied boolean := false;
  update_denied boolean := false;
  delete_denied boolean := false;
BEGIN
  BEGIN
    INSERT INTO public.tasks (title) VALUES ('Direct service-role insert must fail');
  EXCEPTION WHEN insufficient_privilege THEN
    insert_denied := true;
  END;
  BEGIN
    UPDATE public.tasks
       SET title = 'Direct service-role update must fail'
     WHERE operation_id = '40000000-0000-4000-8000-000000000004'::uuid;
  EXCEPTION WHEN insufficient_privilege THEN
    update_denied := true;
  END;
  BEGIN
    DELETE FROM public.tasks
     WHERE operation_id = '40000000-0000-4000-8000-000000000004'::uuid;
  EXCEPTION WHEN insufficient_privilege THEN
    delete_denied := true;
  END;

  IF NOT insert_denied OR NOT update_denied OR NOT delete_denied THEN
    RAISE EXCEPTION 'Direct service_role DML was not fully blocked: insert %, update %, delete %',
      insert_denied, update_denied, delete_denied;
  END IF;
END
$direct_dml_denied$;
RESET ROLE;
