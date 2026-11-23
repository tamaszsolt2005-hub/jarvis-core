-- Admin-only audit reads, append-only protection, and tamper-evident hash chaining.
-- Requires 20261120090000_expand_logs_audit_fields.sql to have run first.

alter table public.logs
  add column if not exists previous_hash text,
  add column if not exists entry_hash text,
  add column if not exists actor_user_id uuid;

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

-- Private singleton stores the latest committed chain head. It is not an
-- event table and is inaccessible to anon/authenticated clients.
create table if not exists public.audit_chain_state (
  singleton boolean primary key default true check (singleton),
  last_hash text not null default repeat('0', 64)
    check (length(last_hash) = 64),
  updated_at timestamptz not null default now()
);
insert into public.audit_chain_state (singleton, last_hash)
values (true, repeat('0', 64))
on conflict (singleton) do nothing;
alter table public.audit_chain_state enable row level security;
revoke all on table public.audit_chain_state from anon, authenticated;
grant select, insert, update on table public.audit_chain_state to service_role;

grant select on table public.audit_chain_state to authenticated;
drop policy if exists "Admins can read audit chain state" on public.audit_chain_state;
create policy "Admins can read audit chain state"
  on public.audit_chain_state
  for select
  to authenticated
  using ((select auth.jwt() -> 'app_metadata' ->> 'role') = 'admin');

create or replace function public.verify_logs_audit_chain()
returns table (
  ok boolean,
  total_entries bigint,
  invalid_hashes bigint,
  missing_predecessors bigint,
  forks bigint,
  disconnected_entries bigint,
  state_matches boolean
)
language sql
stable
security invoker
set search_path = pg_catalog, public, extensions
as $
  with recursive entries as (
    select
      l.previous_hash,
      l.entry_hash,
      encode(
        extensions.digest(
          convert_to(
            l.previous_hash || ':' || (to_jsonb(l) - 'previous_hash' - 'entry_hash')::text,
            'UTF8'
          ),
          'sha256'
        ),
        'hex'
      ) as computed_hash
    from public.logs as l
    where l.entry_hash is not null
  ),
  walk(entry_hash) as (
    select e.entry_hash
      from entries as e
     where e.previous_hash = repeat('0', 64)
    union
    select child.entry_hash
      from entries as child
      join walk as parent on child.previous_hash = parent.entry_hash
  ),
  metrics as (
    select
      count(*)::bigint as total_entries,
      count(*) filter (where computed_hash is distinct from entry_hash)::bigint as invalid_hashes,
      count(*) filter (
        where previous_hash is distinct from repeat('0', 64)
          and not exists (
            select 1 from entries as parent
             where parent.entry_hash = entries.previous_hash
          )
      )::bigint as missing_predecessors,
      (select count(*)::bigint from (
        select previous_hash from entries group by previous_hash having count(*) > 1
      ) as forked) as forks,
      count(*) filter (where previous_hash = repeat('0', 64))::bigint as genesis_entries,
      (select count(*)::bigint from walk) as reachable_entries,
      (select last_hash from public.audit_chain_state where singleton = true) as state_hash
    from entries
  ),
  checks as (
    select
      *,
      case
        when total_entries = 0 then state_hash = repeat('0', 64)
        else state_hash is not null
          and exists (select 1 from entries where entry_hash = state_hash)
          and not exists (select 1 from entries where previous_hash = state_hash)
      end as state_matches
    from metrics
  )
  select
    invalid_hashes = 0
      and missing_predecessors = 0
      and forks = 0
      and genesis_entries = case when total_entries = 0 then 0 else 1 end
      and reachable_entries = total_entries
      and state_matches as ok,
    total_entries,
    invalid_hashes,
    missing_predecessors,
    forks,
    (total_entries - reachable_entries)::bigint as disconnected_entries,
    state_matches
  from checks;
$;

revoke all on function public.verify_logs_audit_chain() from public, anon;
grant execute on function public.verify_logs_audit_chain() to authenticated, service_role;

create or replace function public.set_logs_audit_hash_chain()
returns trigger
language plpgsql
set search_path = pg_catalog, public, extensions
as $$
declare
  prior_hash text;
  canonical_row text;
begin
  -- The singleton row lock serializes the chain head even for several
  -- inserts in one transaction (where created_at timestamps can be equal).
  insert into public.audit_chain_state (singleton, last_hash)
  values (true, repeat('0', 64))
  on conflict (singleton) do nothing;

  select last_hash
    into prior_hash
    from public.audit_chain_state
   where singleton = true
   for update;

  new.previous_hash := coalesce(prior_hash, repeat('0', 64));
  canonical_row := (to_jsonb(new) - 'previous_hash' - 'entry_hash')::text;
  new.entry_hash := encode(
    extensions.digest(convert_to(new.previous_hash || ':' || canonical_row, 'UTF8'), 'sha256'),
    'hex'
  );

  update public.audit_chain_state
     set last_hash = new.entry_hash,
         updated_at = clock_timestamp()
   where singleton = true;
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
