create extension if not exists pgcrypto;

create table if not exists public.leads (
  id uuid primary key default gen_random_uuid(),
  company_name text not null,
  email text,
  website text,
  notes text,
  source text,
  status text not null default 'new',
  consent_basis text,
  approved_to_contact boolean not null default false,
  consent_confirmed_at timestamptz,
  opted_out boolean not null default false,
  first_sent_at timestamptz,
  next_follow_up_at timestamptz,
  follow_up_count integer not null default 0,
  followed_up_at timestamptz,
  last_message_id text,
  last_inbound_message_id text,
  reply_category text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Global research stores company-only prospects without an email address or outreach consent.
alter table public.leads alter column email drop not null;
alter table public.leads add column if not exists website text;
alter table public.leads add column if not exists consent_basis text;
alter table public.leads add column if not exists approved_to_contact boolean not null default false;
alter table public.leads add column if not exists consent_confirmed_at timestamptz;
alter table public.leads add column if not exists opted_out boolean not null default false;
alter table public.leads add column if not exists first_sent_at timestamptz;
alter table public.leads add column if not exists next_follow_up_at timestamptz;
alter table public.leads add column if not exists follow_up_count integer not null default 0;
alter table public.leads add column if not exists followed_up_at timestamptz;
alter table public.leads add column if not exists last_message_id text;
alter table public.leads add column if not exists last_inbound_message_id text;
alter table public.leads add column if not exists reply_category text;
alter table public.leads add column if not exists created_at timestamptz not null default now();
alter table public.leads add column if not exists updated_at timestamptz not null default now();

create index if not exists leads_status_idx on public.leads(status);
create index if not exists leads_next_follow_up_idx on public.leads(next_follow_up_at);
create index if not exists leads_email_idx on public.leads(lower(email));

create table if not exists public.logs (
  id uuid primary key default gen_random_uuid(),
  module text not null,
  level text not null default 'info',
  message text not null,
  created_at timestamptz not null default now()
);

-- Existing installations may have an older logs table without the level column.
alter table public.logs add column if not exists level text not null default 'info';

-- Structured audit metadata; additive to preserve the existing log history.
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

create table if not exists public.settings (
  key text primary key,
  value jsonb,
  updated_at timestamptz not null default now()
);

alter table public.leads enable row level security;
alter table public.logs enable row level security;
alter table public.settings enable row level security;


-- JARVIS CRM workspace tables.
create table if not exists public.tasks (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid references public.leads(id) on delete set null,
  title text not null,
  notes text,
  priority text not null default 'normal' check (priority in ('normal','high','urgent')),
  status text not null default 'open' check (status in ('open','done','cancelled')),
  due_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists tasks_status_due_idx on public.tasks(status, due_at);
alter table public.tasks enable row level security;

create table if not exists public.email_drafts (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid references public.leads(id) on delete set null,
  recipient text not null,
  subject text not null,
  body text not null,
  status text not null default 'draft' check (status in ('draft','approved','archived')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists email_drafts_created_idx on public.email_drafts(created_at desc);
alter table public.email_drafts enable row level security;


-- JARVIS long-term memory. Only explicit user-directed business preferences
-- and decisions are stored.
create table if not exists public.jarvis_memory (
  id uuid primary key default gen_random_uuid(),
  category text not null default 'business_preference',
  content text not null check (char_length(content) between 1 and 700),
  source text not null default 'explicit_user_instruction',
  active boolean not null default true,
  created_at timestamptz not null default now()
);
create index if not exists jarvis_memory_active_created_idx
  on public.jarvis_memory(active, created_at desc);
alter table public.jarvis_memory enable row level security;


-- Technical snapshot used only to detect daily lead/task changes.
-- This table does not alter CRM records.
create table if not exists public.jarvis_proactive_state (
  key text primary key,
  snapshot jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);
alter table public.jarvis_proactive_state enable row level security;



-- Admin-only audit reads and append-only hash-chain integrity controls.
alter table public.logs
  add column if not exists previous_hash text,
  add column if not exists entry_hash text,
  add column if not exists actor_user_id uuid;

revoke all on table public.logs from anon, authenticated;
grant select on table public.logs to authenticated;
drop policy if exists "Admins can read audit logs" on public.logs;
create policy "Admins can read audit logs"
  on public.logs for select to authenticated
  using ((select auth.jwt() -> 'app_metadata' ->> 'role') = 'admin');
revoke insert, update, delete, truncate, references, trigger
  on table public.logs from anon, authenticated;

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
  on public.audit_chain_state for select to authenticated
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
    select l.previous_hash, l.entry_hash,
      encode(extensions.digest(convert_to(
        l.previous_hash || ':' || (to_jsonb(l) - 'previous_hash' - 'entry_hash')::text,
        'UTF8'), 'sha256'), 'hex') as computed_hash
    from public.logs as l
    where l.entry_hash is not null
  ),
  walk(entry_hash) as (
    select e.entry_hash from entries as e where e.previous_hash = repeat('0', 64)
    union
    select child.entry_hash from entries as child
      join walk as parent on child.previous_hash = parent.entry_hash
  ),
  metrics as (
    select
      count(*)::bigint as total_entries,
      count(*) filter (where computed_hash is distinct from entry_hash)::bigint as invalid_hashes,
      count(*) filter (
        where previous_hash is distinct from repeat('0', 64)
          and not exists (select 1 from entries as parent
            where parent.entry_hash = entries.previous_hash)
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
    select *,
      case when total_entries = 0 then state_hash = repeat('0', 64)
        else state_hash is not null
          and exists (select 1 from entries where entry_hash = state_hash)
          and not exists (select 1 from entries where previous_hash = state_hash)
      end as state_matches
    from metrics
  )
  select
    invalid_hashes = 0 and missing_predecessors = 0 and forks = 0
      and genesis_entries = case when total_entries = 0 then 0 else 1 end
      and reachable_entries = total_entries and state_matches as ok,
    total_entries, invalid_hashes, missing_predecessors, forks,
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
  insert into public.audit_chain_state (singleton, last_hash)
  values (true, repeat('0', 64))
  on conflict (singleton) do nothing;
  select last_hash into prior_hash
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
     set last_hash = new.entry_hash, updated_at = clock_timestamp()
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
