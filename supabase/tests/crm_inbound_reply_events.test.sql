BEGIN;
SELECT plan(9);

SELECT ok(
  EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='lead_customer_lifecycle_events'
      AND column_name='source_message_id'
  ),
  'CRM event table stores inbound message idempotency keys'
);
SELECT ok(
  EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND indexname='lead_customer_lifecycle_events_inbound_message_uidx'
  ),
  'inbound message IDs have a partial unique index'
);
SELECT ok(
  has_function_privilege('service_role','public.record_crm_inbound_reply(uuid,text,text,text)','EXECUTE')
  AND NOT has_function_privilege('authenticated','public.record_crm_inbound_reply(uuid,text,text,text)','EXECUTE')
  AND NOT has_function_privilege('anon','public.record_crm_inbound_reply(uuid,text,text,text)','EXECUTE'),
  'only service_role can invoke the inbound CRM event RPC'
);

INSERT INTO public.leads (company_name,website)
VALUES ('CRM inbound fixture','https://crm-inbound.invalid')
RETURNING id \gset inbound_lead_
INSERT INTO public.lead_review_states (lead_id,review_status)
VALUES (:'inbound_lead_id','approved');
INSERT INTO public.leads (company_name,website)
VALUES ('CRM inbound unapproved fixture','https://crm-inbound-unapproved.invalid')
RETURNING id \gset inbound_unapproved_lead_

SET LOCAL ROLE service_role;
SELECT set_config('request.jwt.claims','{"role":"service_role"}',true);
SELECT lives_ok(
  'SELECT public.record_crm_inbound_reply(' ||
  quote_literal(:'inbound_lead_id') || '::uuid,' ||
  quote_literal('<inbound-unique-1>') || ',' ||
  quote_literal('interested') || ',' ||
  quote_literal('Bejövő válasz: árajánlatot kér a partner') || ')',
  'service inbox worker records an inbound CRM event'
);
SELECT is(
  (SELECT stage FROM public.lead_customer_lifecycle WHERE lead_id=:'inbound_lead_id'),
  'responded',
  'an approved lead advances from approved to responded'
);
SELECT ok(
  EXISTS (
    SELECT 1 FROM public.lead_customer_lifecycle_events
    WHERE lead_id=:'inbound_lead_id'
      AND event_type='inbound_reply_recorded'
      AND source_message_id='<inbound-unique-1>'
      AND channel='email'
      AND actor_id='00000000-0000-0000-0000-000000000000'::uuid
  ),
  'inbound event stores source ID, email channel and system actor'
);
SELECT lives_ok(
  'SELECT public.record_crm_inbound_reply(' ||
  quote_literal(:'inbound_lead_id') || '::uuid,' ||
  quote_literal('<inbound-unique-1>') || ',' ||
  quote_literal('interested') || ',' ||
  quote_literal('Retry of the same inbound email message') || ')',
  'reprocessing the same message is safe'
);
SELECT is(
  (SELECT count(*) FROM public.lead_customer_lifecycle_events
   WHERE source_message_id='<inbound-unique-1>'),
  1::bigint,
  'a retried message never creates a duplicate CRM event'
);
SELECT is(
  public.record_crm_inbound_reply(
    :'inbound_unapproved_lead_id'::uuid,
    '<inbound-unapproved>',
    'unknown',
    'Inbound reply for a lead that is not approved'
  ),
  NULL::uuid,
  'unapproved leads are not inserted into the CRM lifecycle'
);
RESET ROLE;
SELECT * FROM finish();
ROLLBACK;
