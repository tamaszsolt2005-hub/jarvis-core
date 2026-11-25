-- Add the website field to existing installations without touching lead data.
alter table public.leads
    add column if not exists website text;
