-- Isolated PostgreSQL integration tests for company-research worker queue,
-- lease/concurrency ceiling, idempotency, cost reservations, quotas and settlement.
-- Run after migrations with: supabase test db
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;
SELECT plan(15);

INSERT INTO public.leads (id, company_name, status)
VALUES ('74000000-0000-4000-8000-000000000001', 'Worker SQL integration fixture', 'research')
ON CONFLICT (id) DO NOTHING;

-- First reservation: 600 micro-USD against a 1000 micro-USD daily budget.
SELECT is(
  (SELECT count(*) FROM public.company_research_job_create(
    jsonb_build_object(
      'operation_id', 'research-budget-op-0001',
      'job_type', 'company_research_refresh',
      'lead_id', '74000000-0000-4000-8000-000000000001',
      'status', 'queued',
      'payload', jsonb_build_object('company_domain', 'budget-fixture.example'),
      'available_at', (now() - interval '1 minute')::text
    ),
    600, 1000, 10, 10
  )),
  1::bigint,
  'job creation atomically creates the first budget reservation'
);

-- Replaying the same operation must return the original job, not reserve twice.
SELECT is(
  (SELECT count(*) FROM public.company_research_job_create(
    jsonb_build_object(
      'operation_id', 'research-budget-op-0001',
      'job_type', 'company_research_refresh',
      'lead_id', '74000000-0000-4000-8000-000000000001',
      'status', 'queued',
      'payload', jsonb_build_object('company_domain', 'budget-fixture.example'),
      'available_at', (now() - interval '1 minute')::text
    ),
    600, 1000, 10, 10
  )),
  1::bigint,
  'same operation ID is idempotent and returns one existing job'
);

SELECT is(
  (SELECT count(*) FROM public.company_research_budget_reservations
   WHERE operation_id = 'research-budget-op-0001' AND reserved_cost_microusd = 600),
  1::bigint,
  'idempotent replay leaves exactly one unchanged reservation'
);

SELECT throws_ok(
  $$SELECT * FROM public.company_research_job_create(
    jsonb_build_object(
      'operation_id', 'research-budget-op-0002',
      'job_type', 'company_research_refresh',
      'lead_id', '74000000-0000-4000-8000-000000000001',
      'status', 'queued',
      'payload', jsonb_build_object('company_domain', 'other-budget-fixture.example')
    ),
    500, 1000, 10, 10
  )$$,
  'P0001',
  'research_daily_budget_exceeded',
  'daily budget rejects a reservation that would exceed the cap'
);

SELECT throws_ok(
  $$SELECT * FROM public.company_research_job_create(
    jsonb_build_object(
      'operation_id', 'research-hour-limit-0001',
      'job_type', 'company_research_refresh',
      'lead_id', '74000000-0000-4000-8000-000000000001',
      'status', 'queued',
      'payload', jsonb_build_object('company_domain', 'hour-limit-fixture.example')
    ),
    0, NULL, 1, NULL
  )$$,
  'P0001',
  'research_hourly_limit_exceeded',
  'hourly job quota rejects a second job in the same UTC hour'
);

SELECT throws_ok(
  $$SELECT * FROM public.company_research_job_create(
    jsonb_build_object(
      'operation_id', 'research-domain-limit-0001',
      'job_type', 'company_research_refresh',
      'lead_id', '74000000-0000-4000-8000-000000000001',
      'status', 'queued',
      'payload', jsonb_build_object('company_domain', 'budget-fixture.example')
    ),
    0, NULL, NULL, 1
  )$$,
  'P0001',
  'research_domain_daily_limit_exceeded',
  'per-domain daily quota rejects a second job for the same domain'
);

-- A second job is deliberately delayed so the first claim is deterministic.
SELECT is(
  (SELECT count(*) FROM public.company_research_job_create(
    jsonb_build_object(
      'operation_id', 'research-worker-job-0002',
      'job_type', 'company_research_refresh',
      'lead_id', '74000000-0000-4000-8000-000000000001',
      'status', 'queued',
      'payload', jsonb_build_object('company_domain', 'worker-fixture.example'),
      'available_at', (now() + interval '1 hour')::text
    ),
    0, NULL, NULL, NULL
  )),
  1::bigint,
  'second queued job is created for the concurrency ceiling check'
);

SELECT is(
  (SELECT count(*) FROM public.company_research_job_claim('worker-test-1', 120, 1)),
  1::bigint,
  'first worker claims one ready job'
);

SELECT is(
  (SELECT count(*) FROM public.company_research_job_claim('worker-test-2', 120, 1)),
  0::bigint,
  'global active-lease ceiling prevents another claim at capacity'
);

SELECT is(
  (SELECT count(*) FROM public.company_research_job_heartbeat(
    'research-budget-op-0001', 'not-the-owner', 120
  )),
  0::bigint,
  'heartbeat from a non-owner cannot renew a lease'
);

SELECT is(
  (SELECT count(*) FROM public.company_research_job_heartbeat(
    'research-budget-op-0001', 'worker-test-1', 120
  )),
  1::bigint,
  'current lease owner can renew the lease'
);

SELECT is(
  (SELECT count(*) FROM public.company_research_job_complete(
    'research-budget-op-0001', 'worker-test-1',
    jsonb_build_object('snapshot_id', 'fixture-snapshot'), 450
  )),
  1::bigint,
  'valid worker completes the job and settles actual cost'
);

SELECT is(
  (SELECT count(*) FROM public.company_research_budget_reservations
   WHERE operation_id = 'research-budget-op-0001'
     AND reservation_status = 'settled'
     AND actual_cost_microusd = 450
     AND reserved_cost_microusd = 450),
  1::bigint,
  'settlement atomically replaces estimate with actual cost'
);

SELECT is(
  (SELECT count(*) FROM public.company_research_job_audit
   WHERE operation_id = 'research-budget-op-0001'
     AND event_type IN ('enqueued', 'claimed', 'heartbeat', 'succeeded')),
  4::bigint,
  'enqueue, claim, heartbeat and completion all leave audit records'
);

SELECT is(
  (SELECT count(*) FROM public.company_research_jobs
   WHERE operation_id = 'research-budget-op-0001'
     AND status = 'succeeded'
     AND lease_owner IS NULL AND lease_expires_at IS NULL),
  1::bigint,
  'successful completion clears the lease and reaches terminal success'
);

SELECT * FROM finish();

DELETE FROM public.company_research_budget_reservations
WHERE operation_id IN ('research-budget-op-0001', 'research-worker-job-0002');
DELETE FROM public.company_research_job_audit
WHERE operation_id IN ('research-budget-op-0001', 'research-worker-job-0002');
DELETE FROM public.company_research_jobs
WHERE operation_id IN ('research-budget-op-0001', 'research-worker-job-0002');
DELETE FROM public.leads
WHERE id = '74000000-0000-4000-8000-000000000001';

ROLLBACK;
