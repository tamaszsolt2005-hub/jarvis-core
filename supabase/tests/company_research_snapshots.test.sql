BEGIN;

DO $snapshot_schema_test$
DECLARE
  test_lead_id uuid;
  test_snapshot_id uuid := gen_random_uuid();
  stored_count integer;
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relname = 'company_research_snapshots'
      AND c.relrowsecurity
  ) THEN
    RAISE EXCEPTION 'company research snapshots must have RLS enabled';
  END IF;

  IF has_table_privilege('anon', 'public.company_research_snapshots', 'SELECT')
     OR has_table_privilege('anon', 'public.company_research_snapshots', 'INSERT')
     OR has_table_privilege('authenticated', 'public.company_research_snapshots', 'INSERT')
     OR NOT has_table_privilege('authenticated', 'public.company_research_snapshots', 'SELECT') THEN
    RAISE EXCEPTION 'snapshots must be authenticated read-only and never anon-accessible';
  END IF;

  IF NOT has_table_privilege('service_role', 'public.company_research_snapshots', 'SELECT')
     OR NOT has_table_privilege('service_role', 'public.company_research_snapshots', 'INSERT') THEN
    RAISE EXCEPTION 'service_role requires backend-only read and insert access';
  END IF;

  INSERT INTO public.leads (company_name, website)
  VALUES ('Snapshot test company', 'https://snapshot-test.invalid')
  RETURNING id INTO test_lead_id;

  INSERT INTO public.company_research_snapshots (
    snapshot_id, lead_id, company_domain, schema_version, researched_at,
    content_sha256, dossier
  ) VALUES (
    test_snapshot_id, test_lead_id, 'snapshot-test.invalid', 1, now(),
    repeat('a', 64), '{"facts":[{"category":"business_model","fact":"B2B"}]}'::jsonb
  );

  SELECT count(*) INTO stored_count
  FROM public.company_research_snapshots
  WHERE lead_id = test_lead_id AND snapshot_id = test_snapshot_id
    AND dossier->'facts'->0->>'fact' = 'B2B';

  IF stored_count <> 1 THEN
    RAISE EXCEPTION 'full dossier snapshot was not persisted';
  END IF;

  BEGIN
    INSERT INTO public.company_research_snapshots (
      snapshot_id, lead_id, company_domain, schema_version, researched_at,
      content_sha256, dossier
    ) VALUES (
      test_snapshot_id, test_lead_id, 'snapshot-test.invalid', 1, now(),
      repeat('a', 64), '{}'::jsonb
    );
    RAISE EXCEPTION 'duplicate snapshot ID unexpectedly accepted';
  EXCEPTION WHEN unique_violation THEN
    NULL;
  END;
END
$snapshot_schema_test$;

ROLLBACK;
