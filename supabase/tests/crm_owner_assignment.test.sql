BEGIN;
SELECT plan(12);

SELECT ok(
  (SELECT relrowsecurity FROM pg_class WHERE oid='public.lead_customer_lifecycle'::regclass)
  AND (SELECT relrowsecurity FROM pg_class WHERE oid='public.lead_customer_lifecycle_events'::regclass),
  'CRM lifecycle and event tables keep RLS enabled'
);
SELECT ok(
  EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.lead_customer_lifecycle'::regclass
      AND confrelid='auth.users'::regclass
      AND contype='f'
      AND pg_get_constraintdef(oid) LIKE '%assigned_to%'
      AND pg_get_constraintdef(oid) LIKE '%ON DELETE SET NULL%'
  ),
  'current owner references Auth user and clears on account deletion'
);
SELECT ok(
  NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.lead_customer_lifecycle_events'::regclass
      AND pg_get_constraintdef(oid) LIKE '%assigned_to_user_id%'
  ),
  'append-only audit keeps historical assignee UUID without mutable FK'
);
SELECT ok(
  has_function_privilege('authenticated','public.list_crm_assignable_users()','EXECUTE')
  AND NOT has_function_privilege('anon','public.list_crm_assignable_users()','EXECUTE')
  AND has_function_privilege('authenticated','public.assign_lead_customer_owner(uuid,uuid,text)','EXECUTE')
  AND NOT has_function_privilege('anon','public.assign_lead_customer_owner(uuid,uuid,text)','EXECUTE'),
  'only authenticated role receives RPC execute privileges'
);

INSERT INTO auth.users (id,email,confirmed_at,raw_user_meta_data,raw_app_meta_data) VALUES
 ('10000000-0000-0000-0000-000000000003','admin@jarvis.invalid',now(),'{"full_name":"Admin User"}','{"role":"admin"}'),
 ('10000000-0000-0000-0000-000000000004','operator@jarvis.invalid',now(),'{"full_name":"Operator User"}','{"role":"operator"}'),
 ('10000000-0000-0000-0000-000000000005','reader@jarvis.invalid',now(),'{"full_name":"Reader User"}','{"role":"reader"}'),
 ('10000000-0000-0000-0000-000000000006','unconfirmed@jarvis.invalid',NULL,'{}','{"role":"operator"}');

INSERT INTO public.leads (company_name,website)
VALUES ('CRM owner fixture','https://crm-owner.invalid')
RETURNING id \gset owner_lead_
INSERT INTO public.lead_review_states (lead_id,review_status)
VALUES (:'owner_lead_id','approved');

SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
 '{"sub":"10000000-0000-0000-0000-000000000003","role":"authenticated","app_metadata":{"role":"admin"}}',true);

SELECT is(
 (SELECT count(*) FROM public.list_crm_assignable_users()),
 2::bigint,
 'directory lists only confirmed admin and operator accounts'
);
SELECT lives_ok(
 'SELECT public.assign_lead_customer_owner(' ||
 quote_literal(:'owner_lead_id') || '::uuid,' ||
 quote_literal('10000000-0000-0000-0000-000000000004') || '::uuid,' ||
 quote_literal('Assign account owner for follow-up') || ')',
 'admin can assign a confirmed operator to an approved lead'
);
SELECT is(
 (SELECT assigned_to FROM public.lead_customer_lifecycle WHERE lead_id=:'owner_lead_id'),
 '10000000-0000-0000-0000-000000000004'::uuid,
 'assignment updates the current lifecycle owner'
);
SELECT is(
 (SELECT count(*) FROM public.lead_customer_lifecycle_events
  WHERE lead_id=:'owner_lead_id' AND event_type='owner_assigned'
    AND summary='Assign account owner for follow-up'
    AND assigned_to_user_id='10000000-0000-0000-0000-000000000004'),
 1::bigint,
 'assignment appends a reasoned audit event'
);
SELECT throws_ok(
 'SELECT public.assign_lead_customer_owner(' ||
 quote_literal(:'owner_lead_id') || '::uuid,' ||
 quote_literal('10000000-0000-0000-0000-000000000005') || '::uuid,' ||
 quote_literal('Try to assign an unauthorized reader') || ')',
 '23514','crm_owner_assignment_target_not_assignable',
 'reader and unconfirmed users cannot be assigned'
);

SELECT set_config('request.jwt.claims',
 '{"sub":"10000000-0000-0000-0000-000000000005","role":"authenticated","app_metadata":{"role":"reader"}}',true);
SELECT throws_ok(
 'SELECT * FROM public.list_crm_assignable_users()',
 '42501','crm_user_directory_requires_admin_or_operator',
 'reader cannot enumerate the assignable user directory'
);

SELECT set_config('request.jwt.claims',
 '{"sub":"10000000-0000-0000-0000-000000000003","role":"authenticated","app_metadata":{"role":"admin"}}',true);
SELECT lives_ok(
 'SELECT public.assign_lead_customer_owner(' ||
 quote_literal(:'owner_lead_id') || '::uuid,NULL,' ||
 quote_literal('Unassign owner after reassignment') || ')',
 'admin can explicitly remove an owner with an audit reason'
);

RESET ROLE;
SELECT throws_ok(
 'UPDATE public.lead_customer_lifecycle_events SET summary=summary WHERE lead_id=' ||
 quote_literal(:'owner_lead_id') || '::uuid',
 '55000','lead_customer_lifecycle_events_are_append_only',
 'owner assignment audit remains append-only'
);
SELECT * FROM finish();
ROLLBACK;
