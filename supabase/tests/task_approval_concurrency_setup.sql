-- Seed one service-role-issued approval for the two-session concurrency test.
SET request.jwt.claims = '{"role":"service_role"}';
DO $$
BEGIN
  IF NOT public.issue_pending_approval(
    repeat('a', 64),
    'auth:10000000-0000-4000-8000-000000000001',
    '{"type":"create","operation_id":"20000000-0000-4000-8000-000000000002","title":"Concurrent approval fixture","priority":"normal","due_at":null,"notes":""}'::jsonb,
    300
  ) THEN
    RAISE EXCEPTION 'Could not seed concurrency approval';
  END IF;
END
$$;

-- Hold the winning transaction inside task insertion long enough for the
-- competing session to collide on the operation_id unique key.
CREATE OR REPLACE FUNCTION public.test_pause_task_approval_race()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.operation_id = '20000000-0000-4000-8000-000000000002'::uuid THEN
    PERFORM pg_sleep(3);
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER task_approval_race_pause
  BEFORE INSERT ON public.tasks
  FOR EACH ROW EXECUTE FUNCTION public.test_pause_task_approval_race();
