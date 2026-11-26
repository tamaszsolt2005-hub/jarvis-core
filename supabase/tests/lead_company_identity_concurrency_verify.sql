DO $lead_company_identity_concurrency_verify$
DECLARE
  fixture_name text;
  fixture_website text;
  matching_leads integer;
  matching_aliases integer;
BEGIN
  SELECT company_name, website INTO fixture_name, fixture_website
  FROM public.lead_identity_race_control WHERE singleton;

  SELECT count(*) INTO matching_leads
  FROM public.leads WHERE company_name = fixture_name;
  IF matching_leads <> 1 THEN
    RAISE EXCEPTION 'parallel company claims created % lead rows instead of one', matching_leads;
  END IF;

  SELECT count(*) INTO matching_aliases
  FROM public.lead_company_aliases
  WHERE alias_value IN (
    public.normalize_lead_company_name(fixture_name),
    public.normalize_lead_company_domain(fixture_website)
  );
  IF matching_aliases <> 2 THEN
    RAISE EXCEPTION 'company identity aliases were not both claimed';
  END IF;

  DELETE FROM public.leads WHERE company_name = fixture_name;
  DROP TABLE public.lead_identity_race_control;
END
$lead_company_identity_concurrency_verify$;
