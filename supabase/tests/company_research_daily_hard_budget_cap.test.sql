-- Hard daily budget cap: settlement accounts for actual cost, and blocks future admissions.
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;
SELECT plan(8);

INSERT INTO public.leads (id, company_name, status)
VALUES ('75000000-0000-4000-8000-000000000001', 'Hard budget fixture', 'research')
ON CONFLICT (id) DO NOTHING;

SELECT is(
  (SELECT count(*) FROM public.company_research_job_create(
    jsonb_build_object('operation_id','hard-budget-op-0001','job_type','company_research_refresh',
      'lead_id','75000000-0000-4000-8000-000000000001','status','queued',
      'payload',jsonb_build_object('company_domain','hard-budget-a.example'),
      'available_at',(now()-interval '1 minute')::text), 600, 1000, NULL, NULL)),
  1::bigint, 'first job reserves against the persisted daily ceiling'
);

SELECT is(
  (SELECT count(*) FROM public.company_research_job_create(
    jsonb_build_object('operation_id','hard-budget-op-0002','job_type','company_research_refresh',
      'lead_id','75000000-0000-4000-8000-000000000001','status','queued',
      'payload',jsonb_build_object('company_domain','hard-budget-b.example'),
      'available_at',(now()-interval '1 minute')::text), 300, 1000, NULL, NULL)),
  1::bigint, 'second job reserves remaining estimated budget'
);

SELECT is(
  (SELECT operation_id FROM public.company_research_job_claim('hard-budget-worker-a',120,1)),
  'hard-budget-op-0001', 'first reservation is claimed deterministically'
);

SELECT is(
  (SELECT status FROM public.company_research_job_complete(
    'hard-budget-op-0001','hard-budget-worker-a','{}'::jsonb,600)),
  'succeeded', 'actual cost within the cap settles successfully'
);

SELECT is(
  (SELECT operation_id FROM public.company_research_job_claim('hard-budget-worker-b',120,1)),
  'hard-budget-op-0002', 'second reservation is claimed after first settlement'
);

SELECT is(
  (SELECT status FROM public.company_research_job_complete(
    'hard-budget-op-0002','hard-budget-worker-b','{}'::jsonb,500)),
  'dead_letter', 'actual cost over the remaining daily budget cannot complete successfully'
);

SELECT is(
  (SELECT count(*) FROM public.company_research_budget_reservations
   WHERE operation_id='hard-budget-op-0002' AND reservation_status='settled'
     AND actual_cost_microusd=500 AND reserved_cost_microusd=500),
  1::bigint, 'overrun records actual provider cost instead of hiding it'
);

SELECT throws_ok(
  $$SELECT * FROM public.company_research_job_create(
    jsonb_build_object('operation_id','hard-budget-op-0003','job_type','company_research_refresh',
      'lead_id','75000000-0000-4000-8000-000000000001','status','queued',
      'payload',jsonb_build_object('company_domain','hard-budget-c.example')),
    1,1000,NULL,NULL)$$,
  'P0001','research_daily_budget_exceeded',
  'settled actual overrun blocks all further daily reservations'
);

SELECT * FROM finish();
ROLLBACK;
