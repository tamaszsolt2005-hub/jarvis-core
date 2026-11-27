-- Human-controlled worker pause/resume and operational visibility.
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;
CREATE SCHEMA IF NOT EXISTS auth;
CREATE OR REPLACE FUNCTION auth.jwt() RETURNS jsonb
LANGUAGE sql STABLE
AS $jwt$ SELECT COALESCE(NULLIF(current_setting('request.jwt.claims', true), ''), '{}')::jsonb $jwt$;
GRANT USAGE ON SCHEMA auth TO authenticated;
GRANT EXECUTE ON FUNCTION auth.jwt() TO authenticated;
SELECT plan(15);

SELECT ok((SELECT relrowsecurity FROM pg_class WHERE oid='public.company_research_runtime_control'::regclass),
  'worker runtime control enforces RLS');
SELECT ok((SELECT relrowsecurity FROM pg_class WHERE oid='public.company_research_runtime_control_events'::regclass),
  'worker control event log enforces RLS');
SELECT ok(NOT has_table_privilege('anon','public.company_research_runtime_control','SELECT')
  AND NOT has_table_privilege('authenticated','public.company_research_runtime_control','SELECT'),
  'API roles cannot read control table directly');
SELECT ok(NOT has_table_privilege('authenticated','public.company_research_runtime_control_events','INSERT')
  AND NOT has_table_privilege('authenticated','public.company_research_runtime_control_events','UPDATE'),
  'API roles cannot mutate control audit directly');
SELECT ok(has_function_privilege('authenticated','public.company_research_worker_control_state()','EXECUTE')
  AND has_function_privilege('authenticated','public.company_research_worker_set_paused(boolean,text)','EXECUTE'),
  'authenticated role can call guarded control RPCs');
SELECT ok(NOT has_function_privilege('anon','public.company_research_worker_control_state()','EXECUTE')
  AND NOT has_function_privilege('anon','public.company_research_worker_set_paused(boolean,text)','EXECUTE'),
  'anon cannot call control RPCs');

SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims','{"app_metadata":{"role":"admin"},"sub":"00000000-0000-4000-8000-000000000010"}',true);
SELECT ok(public.company_research_worker_control_state()->>'paused' = 'false',
  'admin can read initial unpaused state'::text);
SELECT throws_ok(
  $$SELECT public.company_research_worker_set_paused(true,'short')$$,
  '22023', 'research_control_note_required',
  'pause requires an explanatory note'
);
SELECT set_config('request.jwt.claims','{"app_metadata":{"role":"reader"},"sub":"00000000-0000-4000-8000-000000000011"}',true);
SELECT throws_ok(
  $$SELECT public.company_research_worker_set_paused(true,'Reader must not pause worker')$$,
  '42501', 'research_control_write_forbidden',
  'reader cannot pause or resume worker'
);
SELECT set_config('request.jwt.claims','{"app_metadata":{"role":"admin"},"sub":"00000000-0000-4000-8000-000000000010"}',true);
SELECT ok(public.company_research_worker_set_paused(true,'Operator requested maintenance')->>'paused' = 'true',
  'admin can pause research worker'::text);
SELECT ok(NOT has_table_privilege('authenticated','public.company_research_runtime_control_events','SELECT'),
  'authenticated cannot directly read append-only event table');

RESET ROLE;
INSERT INTO public.leads(company_name) VALUES ('Worker Ops Test');
INSERT INTO public.company_research_jobs(operation_id,job_type,lead_id,payload,status)
SELECT 'worker-ops-test-0001','company_research_refresh',id,
  '{"company_name":"Worker Ops Test","company_domain":"example.test"}'::jsonb,'queued'
FROM public.leads WHERE company_name='Worker Ops Test';
INSERT INTO public.company_research_budget_reservations(operation_id,budget_date,reserved_cost_microusd)
VALUES ('worker-ops-test-0001',(now() AT TIME ZONE 'UTC')::date,0);

SET LOCAL ROLE service_role;
SELECT is((SELECT count(*) FROM public.company_research_job_claim('worker-ops-test',60,3)),0::bigint,
  'paused worker cannot claim queued jobs');
RESET ROLE;

SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims','{"app_metadata":{"role":"operator"},"sub":"00000000-0000-4000-8000-000000000012"}',true);
SELECT ok(public.company_research_worker_set_paused(false,'Maintenance completed')->>'paused' = 'false',
  'operator can resume research worker'::text);
SELECT ok(NOT has_table_privilege('authenticated','public.company_research_runtime_control_events','SELECT'),
  'authenticated cannot directly inspect event log');
RESET ROLE;
SET LOCAL ROLE service_role;
SELECT is((SELECT count(*) FROM public.company_research_job_claim('worker-ops-test',60,3)),1::bigint,
  'resumed worker can claim queued jobs');
RESET ROLE;
SELECT * FROM finish();
ROLLBACK;
