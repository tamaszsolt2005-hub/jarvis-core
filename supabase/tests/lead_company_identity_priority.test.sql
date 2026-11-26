-- Isolated PostgreSQL test for atomic company identity and consent-aware email ranking.
DO $lead_company_identity_priority_test$
DECLARE
  suffix text := replace(gen_random_uuid()::text, '-', '');
  company text := 'JARVIS identity fixture ' || replace(gen_random_uuid()::text, '-', '');
  website text := 'https://jarvis-' || replace(gen_random_uuid()::text, '-', '') || '.example.invalid';
  info_email text;
  personal_email text;
  later_email text;
  lead_a uuid;
  lead_b uuid;
  selected text;
  candidate_count integer;
  consent_rejected boolean := false;
BEGIN
  info_email := 'info@company-' || suffix || '.example.invalid';
  personal_email := 'xy+' || suffix || '@gmail.com';
  later_email := 'new+' || suffix || '@outlook.com';

  IF public.lead_email_priority_score(personal_email)
       <= public.lead_email_priority_score(info_email) THEN
    RAISE EXCEPTION 'a named Gmail contact must outrank a generic info@ mailbox';
  END IF;

  SELECT r.lead_id INTO lead_a
  FROM public.upsert_company_lead(
    company, website, NULL, 'research fixture', 'identity_test',
    NULL, false, NULL
  ) r;

  SELECT r.lead_id INTO lead_b
  FROM public.upsert_company_lead(
    company, website, NULL, 'duplicate research fixture', 'identity_test',
    NULL, false, NULL
  ) r;

  IF lead_a IS NULL OR lead_a <> lead_b THEN
    RAISE EXCEPTION 'same company name/domain created more than one lead';
  END IF;

  PERFORM public.upsert_company_lead(
    company, website, info_email, NULL, 'identity_test',
    'consent', true, clock_timestamp()
  );

  PERFORM public.upsert_company_lead(
    company, website, personal_email, NULL, 'identity_test',
    'consent', true, clock_timestamp()
  );

  SELECT email INTO selected FROM public.leads WHERE id = lead_a;
  SELECT count(*) INTO candidate_count
  FROM public.lead_contact_candidates WHERE lead_id = lead_a;

  IF selected <> personal_email THEN
    RAISE EXCEPTION 'higher-priority consented contact was not selected: %', selected;
  END IF;
  IF candidate_count <> 2 THEN
    RAISE EXCEPTION 'contact candidates were not both retained: %', candidate_count;
  END IF;

  -- Consent for one address must never authorize another address.
  BEGIN
    PERFORM public.upsert_company_lead(
      company, website, later_email, NULL, 'identity_test',
      NULL, false, NULL
    );
  EXCEPTION WHEN SQLSTATE '22023' THEN
    consent_rejected := true;
  END;
  IF NOT consent_rejected THEN
    RAISE EXCEPTION 'contact candidate without its own consent was accepted';
  END IF;

  -- Once outreach has begun, the selected recipient is frozen.
  UPDATE public.leads SET first_sent_at = clock_timestamp() WHERE id = lead_a;
  PERFORM public.upsert_company_lead(
    company, website, later_email, NULL, 'identity_test',
    'consent', true, clock_timestamp()
  );
  SELECT email INTO selected FROM public.leads WHERE id = lead_a;
  IF selected <> personal_email THEN
    RAISE EXCEPTION 'recipient changed after outreach had begun';
  END IF;

  DELETE FROM public.leads WHERE id = lead_a;
END
$lead_company_identity_priority_test$;
