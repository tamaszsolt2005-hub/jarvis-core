-- Local PostgreSQL-only fixture for the two 20261117 remote-ledger discrepancies.
-- This is deliberately not a migration-repair script and must never target production.
\set ON_ERROR_STOP on

CREATE TABLE public.jarvis_migration_ledger_fixture (
  version text PRIMARY KEY
);
INSERT INTO public.jarvis_migration_ledger_fixture(version) VALUES
  ('20261119191911'), ('20261119192040'), ('20261119192145'),
  ('20261119192412'), ('20261119192559');

CREATE TABLE public.leads (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_name text NOT NULL
);
CREATE TABLE public.logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  module text NOT NULL,
  message text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.settings (
  id serial PRIMARY KEY,
  key text NOT NULL UNIQUE,
  value jsonb
);
CREATE TABLE public.posts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  content text NOT NULL
);

-- Mirror the already-present production effects without pretending that
-- their missing migration versions have been repaired in the real ledger.
ALTER TABLE public.leads ADD COLUMN website text;
ALTER TABLE public.logs ADD COLUMN level text NOT NULL DEFAULT 'info';
INSERT INTO public.leads(id, company_name, website)
VALUES ('80000000-0000-0000-0000-000000000011', 'legacy lead', 'https://example.invalid');
INSERT INTO public.logs(id, module, message, level)
VALUES ('80000000-0000-0000-0000-000000000012', 'legacy', 'keep me', 'warning');
INSERT INTO public.settings(key, value) VALUES ('legacy_key', '{"preserve":true}');
INSERT INTO public.posts(id, content)
VALUES ('80000000-0000-0000-0000-000000000013', 'legacy post');

-- Apply the repository migrations against the already-present effects.
-- Their ADD COLUMN IF NOT EXISTS clauses must be safe and data-preserving.
\echo 'Fixture seeded with five remote versions and both 20261117 schema effects.'
