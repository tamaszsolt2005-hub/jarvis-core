-- Verify the worker queue remains inaccessible to public API roles.
-- Execute only against the isolated PostgreSQL integration fixture.
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;
SELECT plan(12);

SELECT is(
  (SELECT count(*) FROM pg_class c
   JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE n.nspname = 'public'
     AND c.relname IN (
       'company_research_jobs',
       'company_research_budget_reservations',
       'company_research_job_audit',
       'company_research_snapshots'
     )
     AND c.relrowsecurity),
  4::bigint,
  'worker and snapshot persistence tables enforce row-level security'
);

SELECT is(
  (SELECT count(*) FROM unnest(ARRAY[
    'public.company_research_jobs',
    'public.company_research_budget_reservations',
    'public.company_research_job_audit',
    'public.company_research_snapshots'
  ]) AS relations(relation_name)
  WHERE has_table_privilege('anon', relation_name, 'SELECT')
     OR has_table_privilege('anon', relation_name, 'INSERT')
     OR has_table_privilege('anon', relation_name, 'UPDATE')
     OR has_table_privilege('anon', relation_name, 'DELETE')),
  0::bigint,
  'anon has no direct worker-table privileges'
);

SELECT is(
  (SELECT count(*) FROM unnest(ARRAY[
    'public.company_research_jobs',
    'public.company_research_budget_reservations',
    'public.company_research_job_audit'
  ]) AS relations(relation_name)
  WHERE has_table_privilege('authenticated', relation_name, 'SELECT')
     OR has_table_privilege('authenticated', relation_name, 'INSERT')
     OR has_table_privilege('authenticated', relation_name, 'UPDATE')
     OR has_table_privilege('authenticated', relation_name, 'DELETE')),
  0::bigint,
  'authenticated has no direct worker-table privileges'
);

SELECT ok(
  has_table_privilege('service_role', 'public.company_research_snapshots', 'SELECT')
  AND has_table_privilege('service_role', 'public.company_research_snapshots', 'INSERT')
  AND NOT has_table_privilege('service_role', 'public.company_research_snapshots', 'UPDATE')
  AND NOT has_table_privilege('service_role', 'public.company_research_snapshots', 'DELETE'),
  'service_role can read and append snapshots but cannot mutate or delete history'
);

SELECT is(
  (SELECT count(*) FROM unnest(ARRAY[
    'public.company_research_snapshots'
  ]) AS relations(relation_name)
  WHERE has_table_privilege('anon', relation_name, 'SELECT')
     OR has_table_privilege('anon', relation_name, 'INSERT')
     OR has_table_privilege('anon', relation_name, 'UPDATE')
     OR has_table_privilege('anon', relation_name, 'DELETE')
     OR has_table_privilege('authenticated', relation_name, 'INSERT')
     OR has_table_privilege('authenticated', relation_name, 'UPDATE')
     OR has_table_privilege('authenticated', relation_name, 'DELETE')
     OR NOT has_table_privilege('authenticated', relation_name, 'SELECT')),
  0::bigint,
  'authenticated can read snapshots but cannot mutate them; anon has no access'
);

SELECT is(
  (SELECT count(*) FROM unnest(ARRAY[
    'public.company_research_jobs',
    'public.company_research_budget_reservations'
  ]) AS relations(relation_name)
  WHERE has_table_privilege('service_role', relation_name, 'SELECT')
    AND has_table_privilege('service_role', relation_name, 'INSERT')
    AND has_table_privilege('service_role', relation_name, 'UPDATE')),
  2::bigint,
  'service_role has required job and budget read/write privileges'
);

SELECT ok(
  has_table_privilege('service_role', 'public.company_research_job_audit', 'SELECT')
  AND has_table_privilege('service_role', 'public.company_research_job_audit', 'INSERT')
  AND NOT has_table_privilege('service_role', 'public.company_research_job_audit', 'UPDATE')
  AND NOT has_table_privilege('service_role', 'public.company_research_job_audit', 'DELETE'),
  'service_role can append and read audit but cannot update or delete it'
);

SELECT is(
  (SELECT count(*) FROM unnest(ARRAY[
    'public.company_research_job_audit_list(text,integer)',
    'public.company_research_job_create(jsonb,bigint,bigint,integer,integer)',
    'public.company_research_job_claim(text,integer,integer)',
    'public.company_research_job_heartbeat(text,text,integer)',
    'public.company_research_job_complete(text,text,jsonb,bigint)',
    'public.company_research_job_fail(text,text,text,text,boolean,integer,integer)'
  ]) AS functions(function_signature)
  WHERE has_function_privilege('anon', function_signature, 'EXECUTE')),
  0::bigint,
  'anon cannot execute worker RPC functions'
);

SELECT is(
  (SELECT count(*) FROM unnest(ARRAY[
    'public.company_research_job_audit_list(text,integer)',
    'public.company_research_job_create(jsonb,bigint,bigint,integer,integer)',
    'public.company_research_job_claim(text,integer,integer)',
    'public.company_research_job_heartbeat(text,text,integer)',
    'public.company_research_job_complete(text,text,jsonb,bigint)',
    'public.company_research_job_fail(text,text,text,text,boolean,integer,integer)'
  ]) AS functions(function_signature)
  WHERE has_function_privilege('authenticated', function_signature, 'EXECUTE')),
  0::bigint,
  'authenticated cannot execute worker RPC functions'
);

SELECT is(
  (SELECT count(*) FROM unnest(ARRAY[
    'public.company_research_job_audit_list(text,integer)',
    'public.company_research_job_create(jsonb,bigint,bigint,integer,integer)',
    'public.company_research_job_claim(text,integer,integer)',
    'public.company_research_job_heartbeat(text,text,integer)',
    'public.company_research_job_complete(text,text,jsonb,bigint)',
    'public.company_research_job_fail(text,text,text,text,boolean,integer,integer)'
  ]) AS functions(function_signature)
  WHERE has_function_privilege('service_role', function_signature, 'EXECUTE')),
  6::bigint,
  'service_role can execute all six worker RPC functions'
);

SELECT ok(
  (SELECT rolbypassrls FROM pg_roles WHERE rolname = 'service_role'),
  'isolated backend service role bypasses RLS as expected'
);

SELECT ok(
  NOT has_table_privilege('service_role', 'public.company_research_job_audit', 'TRUNCATE')
  AND NOT has_table_privilege('service_role', 'public.company_research_job_audit', 'REFERENCES')
  AND NOT has_table_privilege('service_role', 'public.company_research_job_audit', 'TRIGGER'),
  'service_role has no extra audit table mutation privileges'
);

SELECT * FROM finish();
ROLLBACK;
