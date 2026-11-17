-- Add the log severity column to existing installations.
alter table public.logs add column if not exists level text not null default 'info';
