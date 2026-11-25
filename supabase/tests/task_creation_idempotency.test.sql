-- Verify that chat-approved task creation has a stable unique key.
DO $task_idempotency_check$
DECLARE
  test_operation_id uuid := '123e4567-e89b-42d3-a456-426614174099';
  duplicate_rejected boolean := false;
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'tasks'
      AND column_name = 'operation_id'
      AND data_type = 'uuid'
  ) THEN
    RAISE EXCEPTION 'tasks.operation_id uuid column is missing';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname = 'public'
      AND tablename = 'tasks'
      AND indexname = 'tasks_operation_id_uidx'
  ) THEN
    RAISE EXCEPTION 'tasks operation id unique index is missing';
  END IF;

  INSERT INTO public.tasks (title, operation_id)
  VALUES ('idempotency fixture', test_operation_id);

  BEGIN
    INSERT INTO public.tasks (title, operation_id)
    VALUES ('duplicate idempotency fixture', test_operation_id);
  EXCEPTION WHEN unique_violation THEN
    duplicate_rejected := true;
  END;

  DELETE FROM public.tasks WHERE operation_id = test_operation_id;

  IF NOT duplicate_rejected THEN
    RAISE EXCEPTION 'duplicate task operation_id was not rejected';
  END IF;
END
$task_idempotency_check$;
