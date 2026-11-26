-- Isolated PostgreSQL worker lifecycle edge cases.
-- Covers expired lease reclaim, stale-owner rejection, retry/dead-letter,
-- final-attempt lease expiry and UTC daily budget rollover.
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;
SELECT plan(19);

INSERT INTO public.leads (id, company_name, status)
VALUES ('74000000-0000-4000-8000-000000000003', 'Worker lifecycle edge fixture', 'research')
ON CONFLICT (id) DO NOTHING;

-- An expired lease below max_attempts is reclaimed by a new worker.
SELECT is(
  (SELECT count(*) FROM public.company_research_job_create(
    jsonb_build_object(
      'operation_id', 'research-lease-reclaim-0001',
      'job_type', 'company_research_refresh',
      'lead_id', '74000000-0000-4000-8000-000000000003',
      'status', 'queued', 'max_attempts', 2,
      'payload', jsonb_build_object('company_domain', 'lease-reclaim.example')
    ), 0, NULL, NULL, NULL
  )),
  1::bigint, 'lease reclaim fixture is enqueued'
);
SELECT is(
  (SELECT count(*) FROM public.company_research_job_claim('lease-owner-old', 120, 1)),
  1::bigint, 'first worker obtains the initial lease'
);
UPDATE public.company_research_jobs
SET lease_expires_at = now() - interval '1 second'
WHERE operation_id = 'research-lease-reclaim-0001';
SELECT is(
  (SELECT count(*) FROM public.company_research_job_claim('lease-owner-new', 120, 1)),
  1::bigint, 'new worker reclaims an expired non-final lease'
);
SELECT is(
  (SELECT count(*) FROM public.company_research_jobs
   WHERE operation_id = 'research-lease-reclaim-0001'
     AND status = 'running' AND attempt_count = 2
     AND lease_owner = 'lease-owner-new' AND lease_expires_at > now()),
  1::bigint, 'reclaim increments attempts and transfers the active lease'
);
SELECT is(
  (SELECT count(*) FROM public.company_research_job_heartbeat(
    'research-lease-reclaim-0001', 'lease-owner-old', 120
  )),
  0::bigint, 'previous owner cannot heartbeat after lease replacement'
);
SELECT is(
  (SELECT count(*) FROM public.company_research_job_complete(
    'research-lease-reclaim-0001', 'lease-owner-old', '{}'::jsonb, NULL
  )),
  0::bigint, 'previous owner cannot complete after lease replacement'
);

-- Retryable failure schedules a retry, then max_attempts forces dead-letter.
SELECT is(
  (SELECT count(*) FROM public.company_research_job_create(
    jsonb_build_object(
      'operation_id', 'research-retry-deadletter-0001',
      'job_type', 'company_research_refresh',
      'lead_id', '74000000-0000-4000-8000-000000000003',
      'status', 'queued', 'max_attempts', 2,
      'payload', jsonb_build_object('company_domain', 'retry-deadletter.example')
    ), 0, NULL, NULL, NULL
  )),
  1::bigint, 'retry fixture is enqueued'
);
SELECT is(
  (SELECT count(*) FROM public.company_research_job_claim('retry-worker-1', 120, 1)),
  1::bigint, 'first retry worker claims the job'
);
SELECT is(
  (SELECT count(*) FROM public.company_research_job_fail(
    'research-retry-deadletter-0001', 'retry-worker-1',
    'provider_unavailable', 'temporary provider failure', true, 1, 2
  )),
  1::bigint, 'retryable failure is accepted from current lease owner'
);
SELECT is(
  (SELECT count(*) FROM public.company_research_jobs
   WHERE operation_id = 'research-retry-deadletter-0001'
     AND status = 'retry_wait' AND lease_owner IS NULL
     AND lease_expires_at IS NULL AND attempt_count = 1),
  1::bigint, 'retry transition clears lease and preserves attempt count'
);
UPDATE public.company_research_jobs
SET available_at = now() - interval '1 second'
WHERE operation_id = 'research-retry-deadletter-0001';
SELECT is(
  (SELECT count(*) FROM public.company_research_job_claim('retry-worker-2', 120, 1)),
  1::bigint, 'job becomes claimable after retry delay'
);
SELECT is(
  (SELECT count(*) FROM public.company_research_job_fail(
    'research-retry-deadletter-0001', 'retry-worker-2',
    'provider_unavailable', 'retry limit reached', true, 1, 2
  )),
  1::bigint, 'final retryable failure is accepted'
);
SELECT is(
  (SELECT count(*) FROM public.company_research_jobs
   WHERE operation_id = 'research-retry-deadletter-0001'
     AND status = 'dead_letter' AND lease_owner IS NULL
     AND lease_expires_at IS NULL AND attempt_count = 2),
  1::bigint, 'max attempts moves retryable failure to dead-letter'
);
SELECT is(
  (SELECT count(*) FROM public.company_research_job_audit
   WHERE operation_id = 'research-retry-deadletter-0001'
     AND event_type IN ('retry_scheduled', 'dead_letter')),
  2::bigint, 'retry and dead-letter transitions are both audited'
);

-- A worker that disappears on its final attempt is dead-lettered on next claim.
SELECT is(
  (SELECT count(*) FROM public.company_research_job_create(
    jsonb_build_object(
      'operation_id', 'research-final-lease-expiry-0001',
      'job_type', 'company_research_refresh',
      'lead_id', '74000000-0000-4000-8000-000000000003',
      'status', 'queued', 'max_attempts', 1,
      'payload', jsonb_build_object('company_domain', 'final-expiry.example')
    ), 0, NULL, NULL, NULL
  )),
  1::bigint, 'final-attempt expiry fixture is enqueued'
);
SELECT is(
  (SELECT count(*) FROM public.company_research_job_claim('final-expiry-worker', 120, 1)),
  1::bigint, 'final-attempt worker claims the job'
);
UPDATE public.company_research_jobs
SET lease_expires_at = now() - interval '1 second'
WHERE operation_id = 'research-final-lease-expiry-0001';
SELECT is(
  (SELECT count(*) FROM public.company_research_job_claim('after-expiry-worker', 120, 1)),
  0::bigint, 'expired final-attempt job is not reclaimed'
);
SELECT is(
  (SELECT count(*) FROM public.company_research_jobs
   WHERE operation_id = 'research-final-lease-expiry-0001'
     AND status = 'dead_letter' AND lease_owner IS NULL
     AND lease_expires_at IS NULL AND last_error_code = 'lease_expired'),
  1::bigint, 'expired final-attempt lease is moved to dead-letter'
);

-- A reservation from the previous UTC date does not consume today's budget.
SELECT public.company_research_job_create(
  jsonb_build_object(
    'operation_id', 'research-budget-rollover-old',
    'job_type', 'company_research_refresh',
    'lead_id', '74000000-0000-4000-8000-000000000003',
    'status', 'queued',
    'payload', jsonb_build_object('company_domain', 'budget-rollover-old.example')
  ), 1000, NULL, NULL, NULL
);
UPDATE public.company_research_budget_reservations
SET budget_date = (now() AT TIME ZONE 'UTC')::date - 1
WHERE operation_id = 'research-budget-rollover-old';
SELECT is(
  (SELECT count(*) FROM public.company_research_job_create(
    jsonb_build_object(
      'operation_id', 'research-budget-rollover-new',
      'job_type', 'company_research_refresh',
      'lead_id', '74000000-0000-4000-8000-000000000003',
      'status', 'queued',
      'payload', jsonb_build_object('company_domain', 'budget-rollover-new.example')
    ), 1000, 1000, NULL, NULL
  )),
  1::bigint, 'previous UTC day reservation does not block the new daily budget'
);

SELECT * FROM finish();

DELETE FROM public.company_research_budget_reservations
WHERE operation_id IN (
  'research-lease-reclaim-0001', 'research-retry-deadletter-0001',
  'research-final-lease-expiry-0001', 'research-budget-rollover-old',
  'research-budget-rollover-new'
);
DELETE FROM public.company_research_job_audit
WHERE operation_id IN (
  'research-lease-reclaim-0001', 'research-retry-deadletter-0001',
  'research-final-lease-expiry-0001', 'research-budget-rollover-old',
  'research-budget-rollover-new'
);
DELETE FROM public.company_research_jobs
WHERE operation_id IN (
  'research-lease-reclaim-0001', 'research-retry-deadletter-0001',
  'research-final-lease-expiry-0001', 'research-budget-rollover-old',
  'research-budget-rollover-new'
);
DELETE FROM public.leads
WHERE id = '74000000-0000-4000-8000-000000000003';
ROLLBACK;
