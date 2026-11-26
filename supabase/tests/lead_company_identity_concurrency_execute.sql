BEGIN;
SET LOCAL ROLE service_role;
SELECT r.lead_id, r.outcome
FROM public.upsert_company_lead(
  (SELECT company_name FROM public.lead_identity_race_control WHERE singleton),
  (SELECT website FROM public.lead_identity_race_control WHERE singleton),
  NULL, 'parallel identity test', 'identity_concurrency_test',
  NULL, false, NULL
) r;
-- Hold the transaction lock long enough for the second PostgreSQL session to overlap.
SELECT pg_sleep(2);
COMMIT;
