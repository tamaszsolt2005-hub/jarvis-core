alter table public.leads
  add column if not exists notes text,
  add column if not exists source text;

create table if not exists public.jarvis_proactive_state (
  key text primary key,
  snapshot jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);
alter table public.jarvis_proactive_state enable row level security;

alter table public.settings alter column key set not null;
alter table public.settings
  alter column value type jsonb
  using to_jsonb(value);