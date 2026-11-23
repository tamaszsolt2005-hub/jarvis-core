-- Admin-only audit reads, append-only protection, and tamper-evident hash chaining.
-- Requires 20261120090000_expand_logs_audit_fields.sql to have run first.

alter table public.logs
  add column if not exists previous_hash text,
  add column if not exists entry_hash text;

-- Audit rows are readable only by authenticated users whose trusted JWT
-- app_metadata.role is admin. user_metadata is intentionally never consulted.
alter table public.logs enable row level security;
revoke all on table public.logs from anon, authenticated;
grant select on table public.logs to authenticated;

drop policy if exists "Admins can read audit logs" on public.logs;
create policy "Admins can read audit logs"
  on public.logs
  for select
  to authenticated
  using (
    (select auth.jwt() -> 'app_metadata' ->> 'role') = 'admin'
  );

-- Authenticated clients may read (subject to RLS), but can never append,
-- rewrite, or delete audit events. Appends remain a server-side service task.
revoke insert, update, delete, truncate, references, trigger
  on table public.logs from anon, authenticated;

create or replace function public.set_logs_audit_hash_chain()
returns trigger
language plpgsql
set search_path = pg_catalog, public, extensions
as $$
declare
  prior_hash text;
  canonical_row text;
begin
  -- Serialize writers so concurrent inserts cannot fork the chain.
  perform pg_advisory_xact_lock(741928361);

  select entry_hash
    into prior_hash
    from public.logs
   where entry_hash is not null
   order by created_at desc, id desc
   limit 1;

  new.previous_hash := coalesce(prior_hash, repeat('0', 64));
  canonical_row := (to_jsonb(new) - 'previous_hash' - 'entry_hash')::text;
  new.entry_hash := encode(
    extensions.digest(convert_to(new.previous_hash || ':' || canonical_row, 'UTF8'), 'sha256'),
    'hex'
  );
  return new;
end;
$$;

create or replace function public.reject_logs_audit_mutation()
returns trigger
language plpgsql
set search_path = pg_catalog, public
as $$
begin
  raise exception 'Audit log rows are append-only; % is not permitted', tg_op
    using errcode = '55000';
end;
$$;

drop trigger if exists logs_audit_hash_chain on public.logs;
create trigger logs_audit_hash_chain
  before insert on public.logs
  for each row execute function public.set_logs_audit_hash_chain();

drop trigger if exists logs_audit_no_update_delete on public.logs;
create trigger logs_audit_no_update_delete
  before update or delete on public.logs
  for each row execute function public.reject_logs_audit_mutation();

drop trigger if exists logs_audit_no_truncate on public.logs;
create trigger logs_audit_no_truncate
  before truncate on public.logs
  for each statement execute function public.reject_logs_audit_mutation();

comment on column public.logs.previous_hash is
  'Previous audit-chain entry hash; null for legacy rows predating chain activation.';
comment on column public.logs.entry_hash is
  'SHA-256 hash of the canonical audit row and previous_hash; null for legacy rows.';
