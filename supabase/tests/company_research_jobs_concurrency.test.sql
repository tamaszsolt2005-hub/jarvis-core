-- True multi-session PostgreSQL race tests.
-- Requires the local Supabase test database and the dblink extension.
-- This file intentionally uses committed, uniquely named fixtures because
-- independent dblink sessions cannot see the caller's uncommitted transaction.
CREATE EXTENSION IF NOT EXISTS dblink WITH SCHEMA extensions;
CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;
SET search_path = public, extensions;
SELECT plan(12);

INSERT INTO public.leads (id, company_name, status)
VALUES ('74000000-0000-4000-8000-000000000002', 'Worker concurrency fixture', 'research')
ON CONFLICT (id) DO NOTHING;

CREATE TEMP TABLE _research_create_race (worker text, created integer);
CREATE TEMP TABLE _research_claim_race (worker text, claimed integer);

SELECT lives_ok(
  $$SELECT extensions.dblink_connect('research_worker_a', 'dbname=' || current_database() || ' user=' || current_user)$$,
  'first independent PostgreSQL session connects'
);
SELECT lives_ok(
  $$SELECT extensions.dblink_connect('research_worker_b', 'dbname=' || current_database() || ' user=' || current_user)$$,
  'second independent PostgreSQL session connects'
);

-- Two sessions reserve 700 each against the same 1000 micro-USD daily cap.
-- Both requests are in flight before either result is collected.
SELECT is(
  extensions.dblink_send_query(
    'research_worker_a',
    $$SELECT count(*)::integer FROM public.company_research_job_create(
      jsonb_build_object(
        'operation_id', 'research-race-budget-a-0001',
        'job_type', 'company_research_refresh',
        'lead_id', '74000000-0000-4000-8000-000000000002',
        'status', 'queued',
        'payload', jsonb_build_object('company_domain', 'race-a.example')
      ), 700, 1000, NULL, NULL
    )$$
  ),
  1,
  'first budget reservation query starts asynchronously'
);
SELECT is(
  extensions.dblink_send_query(
    'research_worker_b',
    $$SELECT count(*)::integer FROM public.company_research_job_create(
      jsonb_build_object(
        'operation_id', 'research-race-budget-b-0001',
        'job_type', 'company_research_refresh',
        'lead_id', '74000000-0000-4000-8000-000000000002',
        'status', 'queued',
        'payload', jsonb_build_object('company_domain', 'race-b.example')
      ), 700, 1000, NULL, NULL
    )$$
  ),
  1,
  'second budget reservation query starts asynchronously'
);

INSERT INTO _research_create_race
SELECT 'a', created
FROM extensions.dblink_get_result('research_worker_a', false) AS result(created integer);
INSERT INTO _research_create_race
SELECT 'b', created
FROM extensions.dblink_get_result('research_worker_b', false) AS result(created integer);
-- Drain each connection's completion marker before reusing it.
SELECT * FROM extensions.dblink_get_result('research_worker_a', false) AS result(created integer);
SELECT * FROM extensions.dblink_get_result('research_worker_b', false) AS result(created integer);

SELECT is(
  (SELECT count(*) FROM _research_create_race WHERE created = 1),
  1::bigint,
  'exactly one concurrent reservation succeeds under the daily budget lock'
);
SELECT is(
  (SELECT COALESCE(sum(reserved_cost_microusd), 0)
   FROM public.company_research_budget_reservations
   WHERE operation_id IN ('research-race-budget-a-0001', 'research-race-budget-b-0001')),
  700::numeric,
  'concurrent reservations never exceed the configured daily budget'
);

-- Ensure at least two jobs are ready, then race two independent workers with
-- a global active lease ceiling of one.
SELECT * FROM public.company_research_job_create(
  jsonb_build_object(
    'operation_id', 'research-race-claim-a-0001',
    'job_type', 'company_research_refresh',
    'lead_id', '74000000-0000-4000-8000-000000000002',
    'status', 'queued',
    'payload', jsonb_build_object('company_domain', 'claim-a.example')
  ), 0, NULL, NULL, NULL
);
SELECT * FROM public.company_research_job_create(
  jsonb_build_object(
    'operation_id', 'research-race-claim-b-0001',
    'job_type', 'company_research_refresh',
    'lead_id', '74000000-0000-4000-8000-000000000002',
    'status', 'queued',
    'payload', jsonb_build_object('company_domain', 'claim-b.example')
  ), 0, NULL, NULL, NULL
);

SELECT is(
  extensions.dblink_send_query(
    'research_worker_a',
    $$SELECT count(*)::integer FROM public.company_research_job_claim('race-worker-a', 120, 1)$$
  ),
  1,
  'first worker claim starts asynchronously'
);
SELECT is(
  extensions.dblink_send_query(
    'research_worker_b',
    $$SELECT count(*)::integer FROM public.company_research_job_claim('race-worker-b', 120, 1)$$
  ),
  1,
  'second worker claim starts asynchronously'
);

INSERT INTO _research_claim_race
SELECT 'a', claimed
FROM extensions.dblink_get_result('research_worker_a', false) AS result(claimed integer);
INSERT INTO _research_claim_race
SELECT 'b', claimed
FROM extensions.dblink_get_result('research_worker_b', false) AS result(claimed integer);
SELECT * FROM extensions.dblink_get_result('research_worker_a', false) AS result(claimed integer);
SELECT * FROM extensions.dblink_get_result('research_worker_b', false) AS result(claimed integer);

SELECT is(
  (SELECT COALESCE(sum(claimed), 0) FROM _research_claim_race),
  1::bigint,
  'two simultaneous workers cannot exceed the global active-lease ceiling'
);
SELECT is(
  (SELECT count(*) FROM public.company_research_jobs
   WHERE status = 'running' AND lease_expires_at > now()),
  1::bigint,
  'database state contains exactly one active lease after the claim race'
);

SELECT lives_ok(
  $$SELECT extensions.dblink_disconnect('research_worker_a')$$,
  'first independent PostgreSQL session disconnects'
);
SELECT lives_ok(
  $$SELECT extensions.dblink_disconnect('research_worker_b')$$,
  'second independent PostgreSQL session disconnects'
);
SELECT * FROM finish();

DELETE FROM public.company_research_budget_reservations
WHERE operation_id IN (
  'research-race-budget-a-0001', 'research-race-budget-b-0001',
  'research-race-claim-a-0001', 'research-race-claim-b-0001'
);
DELETE FROM public.company_research_job_audit
WHERE operation_id IN (
  'research-race-budget-a-0001', 'research-race-budget-b-0001',
  'research-race-claim-a-0001', 'research-race-claim-b-0001'
);
DELETE FROM public.company_research_jobs
WHERE operation_id IN (
  'research-race-budget-a-0001', 'research-race-budget-b-0001',
  'research-race-claim-a-0001', 'research-race-claim-b-0001'
);
DELETE FROM public.leads
WHERE id = '74000000-0000-4000-8000-000000000002';
