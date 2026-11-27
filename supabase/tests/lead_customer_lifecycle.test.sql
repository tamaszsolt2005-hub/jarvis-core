BEGIN;
SELECT plan(8);

SELECT ok(
  (SELECT relrowsecurity FROM pg_class WHERE oid='public.lead_customer_lifecycle'::regclass)
  AND (SELECT relrowsecurity FROM pg_class WHERE oid='public.lead_customer_lifecycle_events'::regclass),
  'CRM lifecycle and event tables enforce RLS'
);
SELECT ok(
  NOT has_table_privilege('anon','public.lead_customer_lifecycle','SELECT')
  AND NOT has_table_privilege('anon','public.lead_customer_lifecycle_events','SELECT'),
  'anon cannot read CRM lifecycle data'
);
SELECT ok(
  has_table_privilege('authenticated','public.lead_customer_lifecycle','SELECT')
  AND has_table_privilege('authenticated','public.lead_customer_lifecycle_events','SELECT')
  AND NOT has_table_privilege('authenticated','public.lead_customer_lifecycle','INSERT')
  AND NOT has_table_privilege('authenticated','public.lead_customer_lifecycle','UPDATE')
  AND NOT has_table_privilege('authenticated','public.lead_customer_lifecycle_events','INSERT'),
  'authenticated roles can read but cannot directly write CRM lifecycle data'
);
SELECT ok(
  has_function_privilege('authenticated','public.record_lead_customer_lifecycle_event(uuid,text,text,text,text,text,date)','EXECUTE')
  AND NOT has_function_privilege('anon','public.record_lead_customer_lifecycle_event(uuid,text,text,text,text,text,date)','EXECUTE'),
  'only authenticated callers can invoke the role-checked CRM lifecycle RPC'
);

INSERT INTO public.leads (company_name, website)
VALUES ('CRM lifecycle fixture','https://crm-lifecycle.invalid')
RETURNING id \gset crm_lead_
INSERT INTO public.lead_review_states (lead_id,review_status)
VALUES (:'crm_lead_id','approved');

SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  '{"sub":"10000000-0000-0000-0000-000000000003","role":"authenticated","app_metadata":{"role":"operator"}}',true);
SELECT lives_ok(
  'SELECT public.record_lead_customer_lifecycle_event(' ||
  quote_literal(:'crm_lead_id') || '::uuid,''stage_changed'',''contacted'',NULL,' ||
  quote_literal('First contact made after manual human outreach') || ',NULL,NULL)',
  'operator can record a stage change for an approved lead'
);
SELECT lives_ok(
  'SELECT public.record_lead_customer_lifecycle_event(' ||
  quote_literal(:'crm_lead_id') || '::uuid,''interaction_logged'',NULL,''meeting'',' ||
  quote_literal('Discovery meeting held; customer described the current workflow') || ',NULL,NULL)',
  'operator can record a human-entered customer interaction'
);
SELECT is(
  (SELECT stage FROM public.lead_customer_lifecycle WHERE lead_id=:'crm_lead_id'),
  'contacted',
  'CRM lifecycle stores the latest lead stage'
);
SELECT is(
  (SELECT count(*) FROM public.lead_customer_lifecycle_events WHERE lead_id=:'crm_lead_id'),
  2::bigint,
  'CRM interactions are preserved as append-only history'
);
RESET ROLE;

SELECT * FROM finish();
ROLLBACK;
