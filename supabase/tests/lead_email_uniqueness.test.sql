-- Verify case/whitespace-insensitive email uniqueness without touching real rows.
DO $lead_email_unique_test$
DECLARE
  test_email text := 'jarvis-unique-' || gen_random_uuid()::text || '@example.invalid';
  duplicate_rejected boolean := false;
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
     WHERE schemaname = 'public'
       AND tablename = 'leads'
       AND indexname = 'leads_email_normalized_uidx'
  ) THEN
    RAISE EXCEPTION 'normalized lead email unique index is missing';
  END IF;

  INSERT INTO public.leads (company_name, email)
  VALUES ('unique email fixture', test_email);

  BEGIN
    INSERT INTO public.leads (company_name, email)
    VALUES ('duplicate email fixture', '  ' || upper(test_email) || '  ');
  EXCEPTION WHEN unique_violation THEN
    duplicate_rejected := true;
  END;

  DELETE FROM public.leads
   WHERE lower(btrim(email)) = lower(test_email);

  IF NOT duplicate_rejected THEN
    RAISE EXCEPTION 'case/whitespace duplicate lead email was not rejected';
  END IF;
END
$lead_email_unique_test$;
