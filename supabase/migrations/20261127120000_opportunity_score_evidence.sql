-- Require every scored dimension to cite source evidence already stored on company pain hypotheses.
BEGIN;

ALTER TABLE public.saas_opportunities
  ADD COLUMN IF NOT EXISTS score_evidence jsonb NOT NULL DEFAULT '{}'::jsonb;

-- A complete score must carry at least one source reference for every dimension.
-- The application validator additionally verifies that each reference exactly
-- matches the source URL, excerpt, timestamp and type stored on its pain record.
ALTER TABLE public.saas_opportunities
  DROP CONSTRAINT IF EXISTS saas_opportunities_score_evidence_check;
ALTER TABLE public.saas_opportunities
  ADD CONSTRAINT saas_opportunities_score_evidence_check
  CHECK (
    jsonb_typeof(score_evidence) = 'object'
    AND (
      scoring_status <> 'scored'
      OR COALESCE((
        CASE WHEN jsonb_typeof(score_evidence->'problem_evidence') = 'array'
          THEN jsonb_array_length(score_evidence->'problem_evidence') > 0
          ELSE FALSE END
        AND CASE WHEN jsonb_typeof(score_evidence->'business_value') = 'array'
          THEN jsonb_array_length(score_evidence->'business_value') > 0
          ELSE FALSE END
        AND CASE WHEN jsonb_typeof(score_evidence->'willingness_to_pay') = 'array'
          THEN jsonb_array_length(score_evidence->'willingness_to_pay') > 0
          ELSE FALSE END
        AND CASE WHEN jsonb_typeof(score_evidence->'feasibility') = 'array'
          THEN jsonb_array_length(score_evidence->'feasibility') > 0
          ELSE FALSE END
        AND CASE WHEN jsonb_typeof(score_evidence->'reusability') = 'array'
          THEN jsonb_array_length(score_evidence->'reusability') > 0
          ELSE FALSE END
        AND CASE WHEN jsonb_typeof(score_evidence->'risk') = 'array'
          THEN jsonb_array_length(score_evidence->'risk') > 0
          ELSE FALSE END
      ), FALSE)
    )
  );

COMMENT ON COLUMN public.saas_opportunities.score_evidence IS
  'Per-dimension source references; each scored dimension must cite stored company pain evidence. Application validation verifies exact source matches.';

COMMIT;
