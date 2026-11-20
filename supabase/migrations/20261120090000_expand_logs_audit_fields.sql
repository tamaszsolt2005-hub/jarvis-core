-- Add structured audit metadata to the existing logs table.
-- Additive only: preserves all existing rows and access policies.
alter table public.logs
  add column if not exists operation_id uuid,
  add column if not exists action text,
  add column if not exists status text not null default 'unknown',
  add column if not exists result jsonb,
  add column if not exists error text,
  add column if not exists approved boolean,
  add column if not exists recipient text,
  add column if not exists subject text,
  add column if not exists delivery_id text;

create index if not exists logs_created_at_desc_idx
  on public.logs (created_at desc);
create index if not exists logs_operation_id_idx
  on public.logs (operation_id);
create index if not exists logs_module_action_created_idx
  on public.logs (module, action, created_at desc);
create index if not exists logs_status_created_idx
  on public.logs (status, created_at desc);
