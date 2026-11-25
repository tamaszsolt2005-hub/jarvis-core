-- Verify one-use revoke semantics and deterministic replay of a completed
-- operation. Run only in the isolated CI database after migrations 1500/1600.
SET request.jwt.claims = '{"role":"service_role"}';

DO $replay_and_revoke$
DECLARE
  v_first jsonb;
  v_replay jsonb;
  v_revoked boolean;
  v_revoke_again boolean;
  v_blocked boolean := false;
BEGIN
  IF NOT public.issue_pending_approval(
    repeat('d', 64),
    'legacy:70000000-0000-4000-8000-000000000007',
    '{"type":"create","operation_id":"71000000-0000-4000-8000-000000000007","title":"Replay fixture","priority":"normal","due_at":null,"notes":""}'::jsonb,
    300
  ) THEN
    RAISE EXCEPTION 'Could not seed replay approval';
  END IF;

  v_first := public.execute_approved_task_action(
    repeat('d', 64),
    'legacy:70000000-0000-4000-8000-000000000007',
    '71000000-0000-4000-8000-000000000007'::uuid,
    '{"type":"create","operation_id":"71000000-0000-4000-8000-000000000007","title":"Replay fixture","priority":"normal","due_at":null,"notes":""}'::jsonb
  );
  v_replay := public.execute_approved_task_action(
    repeat('d', 64),
    'legacy:70000000-0000-4000-8000-000000000007',
    '71000000-0000-4000-8000-000000000007'::uuid,
    '{"type":"create","operation_id":"71000000-0000-4000-8000-000000000007","title":"Replay fixture","priority":"normal","due_at":null,"notes":""}'::jsonb
  );

  IF v_first IS DISTINCT FROM v_replay THEN
    RAISE EXCEPTION 'Replaying a completed operation returned a different result';
  END IF;
  IF (SELECT count(*) FROM public.tasks
       WHERE operation_id = '71000000-0000-4000-8000-000000000007'::uuid) <> 1
     OR (SELECT count(*) FROM public.logs
       WHERE operation_id = '71000000-0000-4000-8000-000000000007'::uuid
         AND status IN ('pending', 'success')) <> 2
     OR (SELECT count(*) FROM private.task_action_operations
       WHERE operation_id = '71000000-0000-4000-8000-000000000007'::uuid
         AND result = v_first AND completed_at IS NOT NULL) <> 1 THEN
    RAISE EXCEPTION 'Completed operation replay duplicated task, audit, or ledger rows';
  END IF;

  IF NOT public.issue_pending_approval(
    repeat('e', 64),
    'legacy:72000000-0000-4000-8000-000000000007',
    '{"type":"create","operation_id":"72000000-0000-4000-8000-000000000007","title":"Revoked fixture","priority":"normal","due_at":null,"notes":""}'::jsonb,
    300
  ) THEN
    RAISE EXCEPTION 'Could not seed revoke approval';
  END IF;

  v_revoked := public.revoke_pending_approval(
    repeat('e', 64), 'legacy:72000000-0000-4000-8000-000000000007'
  );
  v_revoke_again := public.revoke_pending_approval(
    repeat('e', 64), 'legacy:72000000-0000-4000-8000-000000000007'
  );
  IF v_revoked IS DISTINCT FROM true OR v_revoke_again IS DISTINCT FROM false THEN
    RAISE EXCEPTION 'Approval revoke must succeed once and be idempotent thereafter';
  END IF;

  BEGIN
    PERFORM public.execute_approved_task_action(
      repeat('e', 64),
      'legacy:72000000-0000-4000-8000-000000000007',
      '72000000-0000-4000-8000-000000000007'::uuid,
      '{"type":"create","operation_id":"72000000-0000-4000-8000-000000000007","title":"Revoked fixture","priority":"normal","due_at":null,"notes":""}'::jsonb
    );
  EXCEPTION WHEN SQLSTATE '42501' THEN
    v_blocked := true;
  END;
  IF NOT v_blocked THEN
    RAISE EXCEPTION 'A revoked approval was accepted for task execution';
  END IF;
  IF EXISTS (SELECT 1 FROM public.tasks
              WHERE operation_id = '72000000-0000-4000-8000-000000000007'::uuid)
     OR EXISTS (SELECT 1 FROM private.task_action_operations
                 WHERE operation_id = '72000000-0000-4000-8000-000000000007'::uuid) THEN
    RAISE EXCEPTION 'Revoked approval created a task or operation ledger row';
  END IF;
END
$replay_and_revoke$;

DELETE FROM private.task_approvals WHERE token_hash IN (repeat('d', 64), repeat('e', 64));
