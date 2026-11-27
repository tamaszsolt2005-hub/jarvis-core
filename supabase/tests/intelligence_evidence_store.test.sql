-- Durable cross-domain evidence index and read-only dashboard access.
BEGIN;
SELECT plan(11);

SELECT ok(
  (SELECT relrowsecurity FROM pg_class WHERE oid='public.intelligence_evidence'::regclass),
  'central evidence index enforces row-level security'
);
SELECT ok(
  NOT has_table_privilege('anon','public.intelligence_evidence','SELECT')
    AND NOT has_table_privilege('anon','public.intelligence_evidence','INSERT'),
  'anon has no access to the central evidence index'
);
SELECT ok(
  has_table_privilege('authenticated','public.intelligence_evidence','SELECT')
    AND NOT has_table_privilege('authenticated','public.intelligence_evidence','INSERT')
    AND NOT has_table_privilege('authenticated','public.intelligence_evidence','UPDATE')
    AND NOT has_table_privilege('authenticated','public.intelligence_evidence','DELETE'),
  'authenticated users have read-only access'
);
SELECT ok(
  has_table_privilege('service_role','public.intelligence_evidence','SELECT')
    AND has_table_privilege('service_role','public.intelligence_evidence','INSERT')
    AND NOT has_table_privilege('service_role','public.intelligence_evidence','UPDATE')
    AND NOT has_table_privilege('service_role','public.intelligence_evidence','DELETE'),
  'backend can append but cannot mutate indexed evidence'
);
SELECT ok(
  EXISTS (SELECT 1 FROM information_schema.columns
          WHERE table_schema='public' AND table_name='leads'
            AND column_name='research_evidence'),
  'leads can store explicitly structured research evidence'
);
SELECT is(
  (SELECT count(*) FROM pg_trigger
   WHERE NOT tgisinternal AND tgname IN (
     'capture_dossier_intelligence_evidence',
     'capture_pain_intelligence_evidence',
     'capture_lead_intelligence_evidence'
   )),
  3::bigint, 'all three source domains have evidence capture triggers'
);

INSERT INTO public.leads (company_name, website, research_evidence)
VALUES (
  'Intelligence evidence fixture',
  'https://intelligence-fixture.invalid',
  '[{"source_url":"https://sources.invalid/lead","excerpt":"Lead research evidence","evidence_type":"supporting","observed_at":"2026-11-27T10:00:00Z"}]'::jsonb
)
RETURNING id \gset intelligence_

INSERT INTO public.company_research_snapshots (
  snapshot_id, lead_id, company_domain, schema_version, researched_at,
  content_sha256, dossier
) VALUES (
  '90000000-0000-0000-0000-000000000001', :'intelligence_id',
  'intelligence-fixture.invalid', 1, '2026-11-27T10:00:00Z',
  repeat('a',64),
  '{"evidence_records":[{"evidence_id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","source_url":"https://sources.invalid/dossier","excerpt":"Dossier fact evidence","source_kind":"company_dossier_fact","evidence_type":"context","observed_at":"2026-11-27T10:00:00Z"}]}'::jsonb
);

INSERT INTO public.business_pain_hypotheses (
  lead_id, statement, confidence, evidence
) VALUES (
  :'intelligence_id', 'A sourced operational pain hypothesis', 0.650,
  '[{"source_url":"https://sources.invalid/pain","excerpt":"Pain hypothesis evidence","evidence_type":"contradicting","observed_at":"2026-11-27T10:00:00Z"}]'::jsonb
);

SELECT is(
  (SELECT count(*) FROM public.intelligence_evidence WHERE source_domain='lead'),
  1::bigint, 'structured Lead evidence is indexed'
);
SELECT is(
  (SELECT count(*) FROM public.intelligence_evidence WHERE source_domain='company_dossier'),
  1::bigint, 'dossier snapshot evidence is indexed'
);
SELECT is(
  (SELECT count(*) FROM public.intelligence_evidence WHERE source_domain='opportunity'),
  1::bigint, 'company pain evidence is indexed without changing its hypothesis semantics'
);
SELECT is(
  (SELECT count(*) FROM public.intelligence_evidence),
  3::bigint, 'central evidence index unifies all three domains'
);

SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  '{"sub":"10000000-0000-0000-0000-000000000003","role":"authenticated","app_metadata":{"role":"reader"}}',true);
SELECT is(
  (SELECT count(*) FROM public.intelligence_evidence),
  3::bigint, 'reader can view the shared evidence overview'
);
RESET ROLE;

SELECT * FROM finish();
ROLLBACK;
