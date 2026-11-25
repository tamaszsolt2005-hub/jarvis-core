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

create index if not exists tasks_lead_id_idx on public.tasks(lead_id);
create index if not exists email_drafts_lead_id_idx on public.email_drafts(lead_id);