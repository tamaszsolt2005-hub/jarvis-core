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
