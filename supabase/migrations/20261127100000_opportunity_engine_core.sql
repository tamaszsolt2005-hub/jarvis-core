-- Core evidence-linked opportunity model. Repository-only until separately reviewed.
-- The shared-workspace roles can read; only the backend service role can write.
BEGIN;

CREATE TABLE IF NOT EXISTS public.business_pain_hypotheses (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id uuid NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
  snapshot_id uuid,
  statement text NOT NULL CHECK (length(btrim(statement)) BETWEEN 1 AND 1200),
  category text NOT NULL DEFAULT 'operational_process'
    CHECK (category IN ('operational_process','sales_marketing','finance','customer_support','technology','compliance','other')),
  confidence numeric(4,3) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  status text NOT NULL DEFAULT 'hypothesis'
    CHECK (status IN ('hypothesis','under_review','supported','rejected')),
  evidence jsonb NOT NULL DEFAULT '[]'::jsonb
    CHECK (jsonb_typeof(evidence) = 'array'),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT business_pain_snapshot_lead_fk
    FOREIGN KEY (lead_id, snapshot_id)
    REFERENCES public.company_research_snapshots(lead_id, snapshot_id)
    ON DELETE SET NULL (snapshot_id)
);

CREATE INDEX IF NOT EXISTS business_pain_hypotheses_lead_created_idx
  ON public.business_pain_hypotheses (lead_id, created_at DESC);
CREATE INDEX IF NOT EXISTS business_pain_hypotheses_status_idx
  ON public.business_pain_hypotheses (status, confidence DESC);

CREATE TABLE IF NOT EXISTS public.market_problem_patterns (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 240),
  description text NOT NULL DEFAULT '' CHECK (length(description) <= 1600),
  confidence numeric(4,3) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  status text NOT NULL DEFAULT 'candidate'
    CHECK (status IN ('candidate','under_review','validated','rejected')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.market_pattern_pains (
  market_pattern_id uuid NOT NULL REFERENCES public.market_problem_patterns(id) ON DELETE CASCADE,
  company_pain_id uuid NOT NULL REFERENCES public.business_pain_hypotheses(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (market_pattern_id, company_pain_id)
);
CREATE INDEX IF NOT EXISTS market_pattern_pains_company_pain_idx
  ON public.market_pattern_pains (company_pain_id, market_pattern_id);

CREATE TABLE IF NOT EXISTS public.saas_opportunities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  market_pattern_id uuid NOT NULL REFERENCES public.market_problem_patterns(id) ON DELETE RESTRICT,
  name text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 240),
  summary text NOT NULL CHECK (length(btrim(summary)) BETWEEN 1 AND 1600),
  status text NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','under_review','shortlisted','rejected')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS saas_opportunities_pattern_created_idx
  ON public.saas_opportunities (market_pattern_id, created_at DESC);

CREATE OR REPLACE FUNCTION public.assert_market_pattern_company_count(p_market_pattern_id uuid)
RETURNS void
LANGUAGE plpgsql
SET search_path = ''
AS $opportunity_function$
DECLARE
  v_status text;
  v_company_count integer;
BEGIN
  SELECT status INTO v_status
  FROM public.market_problem_patterns
  WHERE id = p_market_pattern_id;
  IF v_status = 'validated' THEN
    SELECT count(DISTINCT pain.lead_id) INTO v_company_count
    FROM public.market_pattern_pains link
    JOIN public.business_pain_hypotheses pain ON pain.id = link.company_pain_id
    WHERE link.market_pattern_id = p_market_pattern_id;
    IF v_company_count < 2 THEN
      RAISE EXCEPTION USING
        ERRCODE = '23514',
        MESSAGE = 'validated_market_pattern_requires_two_companies';
    END IF;
  END IF;
END;
$opportunity_function$;

CREATE OR REPLACE FUNCTION public.downgrade_market_pattern_if_under_supported(p_market_pattern_id uuid)
RETURNS void
LANGUAGE plpgsql
SET search_path = ''
AS $opportunity_function$
DECLARE
  v_status text;
  v_company_count integer;
BEGIN
  SELECT status INTO v_status
  FROM public.market_problem_patterns
  WHERE id = p_market_pattern_id;
  IF v_status = 'validated' THEN
    SELECT count(DISTINCT pain.lead_id) INTO v_company_count
    FROM public.market_pattern_pains link
    JOIN public.business_pain_hypotheses pain ON pain.id = link.company_pain_id
    WHERE link.market_pattern_id = p_market_pattern_id;
    IF v_company_count < 2 THEN
      UPDATE public.market_problem_patterns
      SET status = 'under_review', updated_at = now()
      WHERE id = p_market_pattern_id AND status = 'validated';
    END IF;
  END IF;
END;
$opportunity_function$;

CREATE OR REPLACE FUNCTION public.check_market_pattern_company_count_trigger()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = ''
AS $opportunity_function$
BEGIN
  IF TG_TABLE_NAME = 'market_problem_patterns' THEN
    PERFORM public.assert_market_pattern_company_count(NEW.id);
  ELSE
    IF TG_OP <> 'INSERT' THEN
      PERFORM public.downgrade_market_pattern_if_under_supported(OLD.market_pattern_id);
    END IF;
    IF TG_OP <> 'DELETE' THEN
      PERFORM public.assert_market_pattern_company_count(NEW.market_pattern_id);
    END IF;
  END IF;
  RETURN NULL;
END;
$opportunity_function$;

DROP TRIGGER IF EXISTS market_pattern_company_count_guard ON public.market_problem_patterns;
CREATE TRIGGER market_pattern_company_count_guard
AFTER INSERT OR UPDATE OF status ON public.market_problem_patterns
FOR EACH ROW EXECUTE FUNCTION public.check_market_pattern_company_count_trigger();

DROP TRIGGER IF EXISTS market_pattern_pains_company_count_guard ON public.market_pattern_pains;
CREATE TRIGGER market_pattern_pains_company_count_guard
AFTER INSERT OR UPDATE OR DELETE ON public.market_pattern_pains
FOR EACH ROW EXECUTE FUNCTION public.check_market_pattern_company_count_trigger();

REVOKE ALL ON FUNCTION public.assert_market_pattern_company_count(uuid) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.downgrade_market_pattern_if_under_supported(uuid) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.check_market_pattern_company_count_trigger() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.assert_market_pattern_company_count(uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.downgrade_market_pattern_if_under_supported(uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.check_market_pattern_company_count_trigger() TO service_role;

DO $opportunity_security$
DECLARE
  relation_name text;
BEGIN
  FOREACH relation_name IN ARRAY ARRAY[
    'business_pain_hypotheses',
    'market_problem_patterns',
    'market_pattern_pains',
    'saas_opportunities'
  ] LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', relation_name);
    EXECUTE format('REVOKE ALL ON TABLE public.%I FROM PUBLIC, anon, authenticated', relation_name);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE ON TABLE public.%I TO service_role', relation_name);
    EXECUTE format('GRANT SELECT ON TABLE public.%I TO authenticated', relation_name);
    EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', relation_name || '_shared_read', relation_name);
    EXECUTE format(
      'CREATE POLICY %I ON public.%I FOR SELECT TO authenticated USING ((SELECT auth.jwt() -> ''app_metadata'' ->> ''role'') IN (''admin'', ''operator'', ''reader''))',
      relation_name || '_shared_read', relation_name
    );
  END LOOP;
END;
$opportunity_security$;

COMMIT;
