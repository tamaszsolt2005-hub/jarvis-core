-- Prevent a previously rejected SaaS idea from being scored and approved later.
-- Additive guard: keeps the existing assessment insert and evidence guards intact.
BEGIN;

CREATE OR REPLACE FUNCTION public.reject_assessment_for_rejected_opportunity()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = ''
AS $rejected_opportunity_guard$
DECLARE
  v_status text;
BEGIN
  SELECT candidate.status
    INTO v_status
  FROM public.saas_opportunities AS candidate
  WHERE candidate.id = NEW.opportunity_id
  FOR SHARE;

  IF v_status = 'rejected' THEN
    RAISE EXCEPTION USING
      ERRCODE = '23514',
      MESSAGE = 'rejected_opportunity_cannot_be_assessed';
  END IF;

  RETURN NEW;
END;
$rejected_opportunity_guard$;

REVOKE ALL ON FUNCTION public.reject_assessment_for_rejected_opportunity()
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.reject_assessment_for_rejected_opportunity()
  TO service_role;

DROP TRIGGER IF EXISTS opportunity_assessment_rejected_candidate_guard
  ON public.opportunity_assessments;
CREATE TRIGGER opportunity_assessment_rejected_candidate_guard
BEFORE INSERT ON public.opportunity_assessments
FOR EACH ROW
EXECUTE FUNCTION public.reject_assessment_for_rejected_opportunity();

COMMIT;
