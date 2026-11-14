create extension if not exists pgcrypto;

create table if not exists public.leads (
  id uuid primary key default gen_random_uuid(),
  company_name text not null,
  email text not null,
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
