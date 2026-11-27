-- Append-only, human-approved opportunity assessment history.
-- Repository-only until separately reviewed and applied.
BEGIN;

CREATE TABLE IF NOT EXISTS public.opportunity_assessments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  opportunity_id uuid NOT NULL REFERENCES public.saas_opportunities(id) ON DELETE RESTRICT,
  market_pattern_id uuid NOT NULL REFERENCES public.market_problem_patterns(id) ON DELETE RESTRICT,
  opportunity_name_snapshot text NOT NULL CHECK (length(btrim(opportunity_name_snapshot)) BETWEEN 1 AND 240),
  opportunity_summary_snapshot text NOT NULL CHECK (length(btrim(opportunity_summary_snapshot)) BETWEEN 1 AND 1600),
  market_pattern_title_snapshot text NOT NULL CHECK (length(btrim(market_pattern_title_snapshot)) BETWEEN 1 AND 240),
  idempotency_key uuid NOT NULL UNIQUE,
  approval_status text NOT NULL DEFAULT 'approved' CHECK (approval_status = 'approved'),
  score_problem_evidence numeric(5,2) NOT NULL CHECK (score_problem_evidence BETWEEN 0 AND 100),
  score_business_value numeric(5,2) NOT NULL CHECK (score_business_value BETWEEN 0 AND 100),
  score_willingness_to_pay numeric(5,2) NOT NULL CHECK (score_willingness_to_pay BETWEEN 0 AND 100),
  score_feasibility numeric(5,2) NOT NULL CHECK (score_feasibility BETWEEN 0 AND 100),
  score_reusability numeric(5,2) NOT NULL CHECK (score_reusability BETWEEN 0 AND 100),
  score_risk numeric(5,2) NOT NULL CHECK (score_risk BETWEEN 0 AND 100),
  weighted_score numeric(5,2) GENERATED ALWAYS AS (
    round(score_problem_evidence * 0.25 + score_business_value * 0.20
      + score_willingness_to_pay * 0.15 + score_feasibility * 0.15
      + score_reusability * 0.15 + (100 - score_risk) * 0.10, 2)
  ) STORED,
  assessment_confidence numeric(4,3) NOT NULL CHECK (assessment_confidence BETWEEN 0 AND 1),
  score_rationale jsonb NOT NULL,
  score_evidence jsonb NOT NULL,
  evaluator_model text NOT NULL CHECK (length(btrim(evaluator_model)) BETWEEN 1 AND 120),
  evaluator_version text NOT NULL CHECK (length(btrim(evaluator_version)) BETWEEN 1 AND 80),
  approved_by uuid NOT NULL DEFAULT auth.uid(),
  approved_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT opportunity_assessments_rationale_check CHECK (
    jsonb_typeof(score_rationale) = 'object'
    AND COALESCE((
      jsonb_typeof(score_rationale->'problem_evidence') = 'string' AND length(btrim(score_rationale->>'problem_evidence')) > 0
      AND jsonb_typeof(score_rationale->'business_value') = 'string' AND length(btrim(score_rationale->>'business_value')) > 0
      AND jsonb_typeof(score_rationale->'willingness_to_pay') = 'string' AND length(btrim(score_rationale->>'willingness_to_pay')) > 0
      AND jsonb_typeof(score_rationale->'feasibility') = 'string' AND length(btrim(score_rationale->>'feasibility')) > 0
      AND jsonb_typeof(score_rationale->'reusability') = 'string' AND length(btrim(score_rationale->>'reusability')) > 0
      AND jsonb_typeof(score_rationale->'risk') = 'string' AND length(btrim(score_rationale->>'risk')) > 0
    ), FALSE)
  ),
  CONSTRAINT opportunity_assessments_evidence_shape_check CHECK (
    jsonb_typeof(score_evidence) = 'object'
    AND CASE WHEN jsonb_typeof(score_evidence->'problem_evidence') = 'array' THEN jsonb_array_length(score_evidence->'problem_evidence') > 0 ELSE FALSE END
    AND CASE WHEN jsonb_typeof(score_evidence->'business_value') = 'array' THEN jsonb_array_length(score_evidence->'business_value') > 0 ELSE FALSE END
    AND CASE WHEN jsonb_typeof(score_evidence->'willingness_to_pay') = 'array' THEN jsonb_array_length(score_evidence->'willingness_to_pay') > 0 ELSE FALSE END
    AND CASE WHEN jsonb_typeof(score_evidence->'feasibility') = 'array' THEN jsonb_array_length(score_evidence->'feasibility') > 0 ELSE FALSE END
    AND CASE WHEN jsonb_typeof(score_evidence->'reusability') = 'array' THEN jsonb_array_length(score_evidence->'reusability') > 0 ELSE FALSE END
    AND CASE WHEN jsonb_typeof(score_evidence->'risk') = 'array' THEN jsonb_array_length(score_evidence->'risk') > 0 ELSE FALSE END
  )
);

CREATE INDEX IF NOT EXISTS opportunity_assessments_created_idx
  ON public.opportunity_assessments (approved_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS opportunity_assessments_opportunity_idx
  ON public.opportunity_assessments (opportunity_id, approved_at DESC);

CREATE OR REPLACE FUNCTION public.guard_opportunity_assessment_insert()
RETURNS trigger LANGUAGE plpgsql SET search_path = ''
AS $assessment_guard$
DECLARE
  v_role text;
  v_company_count integer;
  v_dimension text;
  v_reference jsonb;
  v_pain_id uuid;
BEGIN
  v_role := auth.jwt() -> 'app_metadata' ->> 'role';
  IF COALESCE(v_role, '') NOT IN ('admin', 'operator') OR auth.uid() IS NULL THEN
    RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'opportunity_approval_requires_admin_or_operator';
  END IF;
  IF NEW.approved_by IS DISTINCT FROM auth.uid() THEN
    RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'opportunity_approval_actor_mismatch';
  END IF;
  NEW.approved_at := now();
  NEW.created_at := now();

  SELECT candidate.name, candidate.summary, pattern.title
    INTO NEW.opportunity_name_snapshot, NEW.opportunity_summary_snapshot, NEW.market_pattern_title_snapshot
  FROM public.saas_opportunities candidate
  JOIN public.market_problem_patterns pattern ON pattern.id = candidate.market_pattern_id
  WHERE candidate.id = NEW.opportunity_id
    AND candidate.market_pattern_id = NEW.market_pattern_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'opportunity_pattern_mismatch';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM public.market_problem_patterns pattern
    WHERE pattern.id = NEW.market_pattern_id AND pattern.status = 'validated'
  ) THEN
    RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'opportunity_pattern_not_validated';
  END IF;
  SELECT count(DISTINCT pain.lead_id) INTO v_company_count
  FROM public.market_pattern_pains link
  JOIN public.business_pain_hypotheses pain ON pain.id = link.company_pain_id
  WHERE link.market_pattern_id = NEW.market_pattern_id;
  IF v_company_count < 2 THEN
    RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'opportunity_pattern_requires_two_companies';
  END IF;

  FOREACH v_dimension IN ARRAY ARRAY[
    'problem_evidence','business_value','willingness_to_pay','feasibility','reusability','risk'
  ] LOOP
    FOR v_reference IN
      SELECT value FROM jsonb_array_elements(NEW.score_evidence -> v_dimension)
    LOOP
      IF jsonb_typeof(v_reference) <> 'object'
        OR COALESCE(v_reference ->> 'evidence_type','') NOT IN ('supporting','contradicting','context')
        OR COALESCE(v_reference ->> 'source_url','') !~ '^https?://'
        OR length(btrim(COALESCE(v_reference ->> 'excerpt',''))) = 0
      THEN
        RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'opportunity_evidence_reference_invalid';
      END IF;
      BEGIN
        v_pain_id := (v_reference ->> 'pain_hypothesis_id')::uuid;
      EXCEPTION WHEN invalid_text_representation THEN
        RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'opportunity_evidence_invalid_pain_id';
      END;
      IF NOT EXISTS (
        SELECT 1
        FROM public.market_pattern_pains link
        JOIN public.business_pain_hypotheses pain ON pain.id = link.company_pain_id
        CROSS JOIN LATERAL jsonb_array_elements(pain.evidence) source
        WHERE link.market_pattern_id = NEW.market_pattern_id
          AND pain.id = v_pain_id
          AND source ->> 'source_url' = v_reference ->> 'source_url'
          AND source ->> 'excerpt' = v_reference ->> 'excerpt'
      ) THEN
        RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'opportunity_evidence_must_match_linked_company_source';
      END IF;
    END LOOP;
  END LOOP;
  RETURN NEW;
END;
$assessment_guard$;

CREATE OR REPLACE FUNCTION public.reject_opportunity_assessment_mutation()
RETURNS trigger LANGUAGE plpgsql SET search_path = ''
AS $assessment_immutable$
BEGIN
  RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'opportunity_assessments_are_append_only';
END;
$assessment_immutable$;

DROP TRIGGER IF EXISTS opportunity_assessment_insert_guard ON public.opportunity_assessments;
CREATE TRIGGER opportunity_assessment_insert_guard
BEFORE INSERT ON public.opportunity_assessments
FOR EACH ROW EXECUTE FUNCTION public.guard_opportunity_assessment_insert();
DROP TRIGGER IF EXISTS opportunity_assessment_immutable_guard ON public.opportunity_assessments;
CREATE TRIGGER opportunity_assessment_immutable_guard
BEFORE UPDATE OR DELETE ON public.opportunity_assessments
FOR EACH ROW EXECUTE FUNCTION public.reject_opportunity_assessment_mutation();

REVOKE ALL ON FUNCTION public.guard_opportunity_assessment_insert() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.reject_opportunity_assessment_mutation() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.guard_opportunity_assessment_insert() TO authenticated;
GRANT EXECUTE ON FUNCTION public.reject_opportunity_assessment_mutation() TO authenticated;

ALTER TABLE public.opportunity_assessments ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.opportunity_assessments FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT, INSERT ON TABLE public.opportunity_assessments TO authenticated;
GRANT SELECT ON TABLE public.opportunity_assessments TO service_role;
DROP POLICY IF EXISTS opportunity_assessments_shared_read ON public.opportunity_assessments;
CREATE POLICY opportunity_assessments_shared_read ON public.opportunity_assessments
  FOR SELECT TO authenticated
  USING ((SELECT auth.jwt() -> 'app_metadata' ->> 'role') IN ('admin','operator','reader'));
DROP POLICY IF EXISTS opportunity_assessments_admin_operator_insert ON public.opportunity_assessments;
CREATE POLICY opportunity_assessments_admin_operator_insert ON public.opportunity_assessments
  FOR INSERT TO authenticated
  WITH CHECK (
    (SELECT auth.jwt() -> 'app_metadata' ->> 'role') IN ('admin','operator')
    AND approved_by = (SELECT auth.uid())
  );

COMMENT ON TABLE public.opportunity_assessments IS
  'Append-only, human-approved snapshots of evidence-linked SaaS opportunity assessments.';
COMMENT ON COLUMN public.opportunity_assessments.approved_by IS
  'Supabase Auth user UUID; set and verified by the insert guard.';
COMMENT ON COLUMN public.opportunity_assessments.idempotency_key IS
  'Unique preview approval key; prevents duplicate saves after client retries.';

COMMIT;
