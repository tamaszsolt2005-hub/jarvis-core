-- Idempotent source-backed pain ingestion and cross-company candidate discovery.
-- Repository-only until separately reviewed and deployed.
BEGIN;

CREATE UNIQUE INDEX IF NOT EXISTS business_pain_snapshot_statement_uidx
  ON public.business_pain_hypotheses (lead_id, snapshot_id, statement)
  WHERE snapshot_id IS NOT NULL;

ALTER TABLE public.market_problem_patterns
  ADD COLUMN IF NOT EXISTS fingerprint text;

CREATE UNIQUE INDEX IF NOT EXISTS market_problem_patterns_fingerprint_uidx
  ON public.market_problem_patterns (fingerprint)
  WHERE fingerprint IS NOT NULL;

ALTER TABLE public.saas_opportunities
  ADD COLUMN IF NOT EXISTS discovery_fingerprint text;

CREATE UNIQUE INDEX IF NOT EXISTS saas_opportunities_discovery_fingerprint_uidx
  ON public.saas_opportunities (discovery_fingerprint)
  WHERE discovery_fingerprint IS NOT NULL;

COMMIT;
