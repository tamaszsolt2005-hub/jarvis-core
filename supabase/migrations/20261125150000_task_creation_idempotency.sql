-- Stable idempotency key for chat-approved task creation.
-- Nullable for legacy rows and non-chat task creation paths.
ALTER TABLE public.tasks
  ADD COLUMN IF NOT EXISTS operation_id uuid;

CREATE UNIQUE INDEX IF NOT EXISTS tasks_operation_id_uidx
  ON public.tasks (operation_id)
  WHERE operation_id IS NOT NULL;
