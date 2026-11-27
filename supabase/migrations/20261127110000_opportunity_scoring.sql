-- Explainable, evidence-gated scoring for SaaS opportunity candidates.
BEGIN;

ALTER TABLE public.saas_opportunities
  ADD COLUMN IF NOT EXISTS scoring_status text NOT NULL DEFAULT 'insufficient_evidence',
  ADD COLUMN IF NOT EXISTS score_problem_evidence numeric(5,2),
  ADD COLUMN IF NOT EXISTS score_business_value numeric(5,2),
  ADD COLUMN IF NOT EXISTS score_willingness_to_pay numeric(5,2),
  ADD COLUMN IF NOT EXISTS score_feasibility numeric(5,2),
  ADD COLUMN IF NOT EXISTS score_reusability numeric(5,2),
  ADD COLUMN IF NOT EXISTS score_risk numeric(5,2),
  ADD COLUMN IF NOT EXISTS assessment_confidence numeric(4,3),
  ADD COLUMN IF NOT EXISTS score_rationale jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS weighted_score numeric(5,2)
    GENERATED ALWAYS AS (
      CASE WHEN score_problem_evidence IS NOT NULL
             AND score_business_value IS NOT NULL
             AND score_willingness_to_pay IS NOT NULL
             AND score_feasibility IS NOT NULL
             AND score_reusability IS NOT NULL
             AND score_risk IS NOT NULL
      THEN round(
        score_problem_evidence * 0.25 + score_business_value * 0.20
        + score_willingness_to_pay * 0.15 + score_feasibility * 0.15
        + score_reusability * 0.15 + (100 - score_risk) * 0.10, 2
      )
      ELSE NULL END
    ) STORED;

DO $scoring_constraints$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='saas_opportunities_scoring_status_check') THEN
    ALTER TABLE public.saas_opportunities ADD CONSTRAINT saas_opportunities_scoring_status_check
      CHECK (scoring_status IN ('insufficient_evidence','scored'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='saas_opportunities_score_range_check') THEN
    ALTER TABLE public.saas_opportunities ADD CONSTRAINT saas_opportunities_score_range_check
      CHECK (
        (score_problem_evidence IS NULL OR score_problem_evidence BETWEEN 0 AND 100)
        AND (score_business_value IS NULL OR score_business_value BETWEEN 0 AND 100)
        AND (score_willingness_to_pay IS NULL OR score_willingness_to_pay BETWEEN 0 AND 100)
        AND (score_feasibility IS NULL OR score_feasibility BETWEEN 0 AND 100)
        AND (score_reusability IS NULL OR score_reusability BETWEEN 0 AND 100)
        AND (score_risk IS NULL OR score_risk BETWEEN 0 AND 100)
      );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='saas_opportunities_assessment_confidence_check') THEN
    ALTER TABLE public.saas_opportunities ADD CONSTRAINT saas_opportunities_assessment_confidence_check
      CHECK (assessment_confidence IS NULL OR assessment_confidence BETWEEN 0 AND 1);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='saas_opportunities_score_completeness_check') THEN
    ALTER TABLE public.saas_opportunities ADD CONSTRAINT saas_opportunities_score_completeness_check
      CHECK (
        (scoring_status = 'scored'
          AND score_problem_evidence IS NOT NULL AND score_business_value IS NOT NULL
          AND score_willingness_to_pay IS NOT NULL AND score_feasibility IS NOT NULL
          AND score_reusability IS NOT NULL AND score_risk IS NOT NULL
          AND assessment_confidence IS NOT NULL)
        OR
        (scoring_status = 'insufficient_evidence'
          AND score_problem_evidence IS NULL AND score_business_value IS NULL
          AND score_willingness_to_pay IS NULL AND score_feasibility IS NULL
          AND score_reusability IS NULL AND score_risk IS NULL
          AND assessment_confidence IS NULL)
      );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='saas_opportunities_score_rationale_check') THEN
    ALTER TABLE public.saas_opportunities ADD CONSTRAINT saas_opportunities_score_rationale_check
      CHECK (
        jsonb_typeof(score_rationale) = 'object'
        AND (scoring_status <> 'scored' OR (
          jsonb_typeof(score_rationale->'problem_evidence') = 'string' AND length(btrim(score_rationale->>'problem_evidence')) > 0
          AND jsonb_typeof(score_rationale->'business_value') = 'string' AND length(btrim(score_rationale->>'business_value')) > 0
          AND jsonb_typeof(score_rationale->'willingness_to_pay') = 'string' AND length(btrim(score_rationale->>'willingness_to_pay')) > 0
          AND jsonb_typeof(score_rationale->'feasibility') = 'string' AND length(btrim(score_rationale->>'feasibility')) > 0
          AND jsonb_typeof(score_rationale->'reusability') = 'string' AND length(btrim(score_rationale->>'reusability')) > 0
          AND jsonb_typeof(score_rationale->'risk') = 'string' AND length(btrim(score_rationale->>'risk')) > 0
        ))
      );
  END IF;
END;
$scoring_constraints$;

COMMENT ON COLUMN public.saas_opportunities.score_risk IS
  'Risk penalty input: 0 means no material risk, 100 means extreme risk; weighted score subtracts this dimension.';
COMMENT ON COLUMN public.saas_opportunities.weighted_score IS
  'Generated 0-100 score; NULL until all six dimensions are assessed.';

COMMIT;
