-- Append-only history for source-grounded company research dossiers.
-- This migration is repository-only until separately reviewed and explicitly applied.
BEGIN;

CREATE TABLE IF NOT EXISTS public.company_research_snapshots (
  snapshot_id uuid PRIMARY KEY,
  lead_id uuid NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
  company_domain text NOT NULL CHECK (company_domain <> ''),
  schema_version integer NOT NULL CHECK (schema_version > 0),
  researched_at timestamptz NOT NULL,
  content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
  dossier jsonb NOT NULL CHECK (jsonb_typeof(dossier) = 'object'),
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT company_research_snapshots_lead_snapshot_unique UNIQUE (lead_id, snapshot_id)
);

CREATE INDEX IF NOT EXISTS company_research_snapshots_lead_time_idx
  ON public.company_research_snapshots (lead_id, researched_at DESC, snapshot_id DESC);

CREATE INDEX IF NOT EXISTS company_research_snapshots_domain_time_idx
  ON public.company_research_snapshots (company_domain, researched_at DESC);

ALTER TABLE public.company_research_snapshots ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.company_research_snapshots FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT ON TABLE public.company_research_snapshots TO service_role;
GRANT SELECT ON TABLE public.company_research_snapshots TO authenticated;
DROP POLICY IF EXISTS company_research_snapshots_shared_read ON public.company_research_snapshots;
CREATE POLICY company_research_snapshots_shared_read
  ON public.company_research_snapshots
  FOR SELECT
  TO authenticated
  USING ((SELECT auth.jwt() -> 'app_metadata' ->> 'role') IN ('admin','operator','reader'));

COMMIT;
