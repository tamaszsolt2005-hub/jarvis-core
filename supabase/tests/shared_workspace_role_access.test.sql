-- Run only against an isolated PostgreSQL/Supabase test database.
BEGIN;
SELECT plan(31);

SELECT ok((SELECT relrowsecurity FROM pg_class WHERE oid='public.leads'::regclass), 'RLS enabled on leads');
SELECT ok((SELECT relrowsecurity FROM pg_class WHERE oid='public.tasks'::regclass), 'RLS enabled on tasks');
SELECT ok((SELECT relrowsecurity FROM pg_class WHERE oid='public.email_drafts'::regclass), 'RLS enabled on email_drafts');
SELECT ok((SELECT relrowsecurity FROM pg_class WHERE oid='public.settings'::regclass), 'RLS enabled on settings');
SELECT ok((SELECT relrowsecurity FROM pg_class WHERE oid='public.jarvis_memory'::regclass), 'RLS enabled on jarvis_memory');
SELECT ok((SELECT relrowsecurity FROM pg_class WHERE oid='public.posts'::regclass), 'RLS enabled on posts');
SELECT ok((SELECT relrowsecurity FROM pg_class WHERE oid='public.jarvis_proactive_state'::regclass), 'RLS enabled on proactive state');
SELECT ok((SELECT relrowsecurity FROM pg_class WHERE oid='public.audit_chain_state'::regclass), 'RLS enabled on audit chain state');
SELECT ok(NOT has_table_privilege('anon','public.leads','SELECT'), 'anon cannot read leads');
SELECT ok(has_table_privilege('authenticated','public.leads','SELECT'), 'authenticated has leads SELECT grant');
SELECT ok(has_table_privilege('authenticated','public.leads','INSERT'), 'authenticated has leads INSERT grant, filtered by RLS');
SELECT ok(has_table_privilege('authenticated','public.logs','INSERT'), 'authenticated may attempt append subject to role RLS');
SELECT ok(NOT has_table_privilege('authenticated','public.jarvis_proactive_state','SELECT'), 'authenticated cannot read machine state');

INSERT INTO public.leads (id, company_name) VALUES
('a0000000-0000-4000-8000-000000000001','RBAC fixture');
INSERT INTO public.settings (key,value) VALUES
('lead_research_market','{"country":"Germany"}'::jsonb),
('smtp_password','{"value":"must stay admin-only"}'::jsonb);

SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims','{"sub":"10000000-0000-0000-0000-000000000003","role":"authenticated","app_metadata":{"role":"reader"}}',true);
SELECT is((SELECT count(*) FROM public.leads WHERE company_name='RBAC fixture'),1::bigint,'reader can read shared leads');
SELECT throws_ok(
  $reader$INSERT INTO public.leads (company_name) VALUES ('reader denied')$reader$,
  '42501', NULL, 'reader cannot insert leads'
);
UPDATE public.leads SET company_name='reader changed' WHERE company_name='RBAC fixture';
SELECT is((SELECT count(*) FROM public.leads WHERE company_name='reader changed'),0::bigint,'reader cannot update leads');
SELECT is((SELECT count(*) FROM public.settings),0::bigint,'reader cannot read settings');
SELECT is((SELECT count(*) FROM public.logs),0::bigint,'reader cannot read audit events');
SELECT throws_ok(
  $reader$INSERT INTO public.logs (module,message,level,action,status) VALUES ('reader_test','reader event','info','test','success')$reader$,
  '42501', NULL, 'reader cannot append audit events'
);
SELECT is((SELECT count(*) FROM public.audit_chain_state),0::bigint,'reader cannot read audit chain state');

SELECT set_config('request.jwt.claims','{"sub":"10000000-0000-0000-0000-000000000002","role":"authenticated","app_metadata":{"role":"operator"}}',true);
INSERT INTO public.leads (company_name) VALUES ('operator allowed');
SELECT is((SELECT count(*) FROM public.leads WHERE company_name='operator allowed'),1::bigint,'operator can insert leads');
INSERT INTO public.logs (module,message,level,action,status) VALUES ('rbac_test','operator event','info','test','success');
SELECT is((SELECT count(*) FROM public.logs WHERE module='rbac_test'),1::bigint,'operator can append an audit event');
SELECT is((SELECT actor_user_id::text FROM public.logs WHERE module='rbac_test' LIMIT 1),'10000000-0000-0000-0000-000000000002','audit trigger binds actor to authenticated JWT');
SELECT is((SELECT count(*) FROM public.settings),1::bigint,'operator can read only the research-market setting');
SELECT is((SELECT count(*) FROM public.logs),0::bigint,'operator cannot read audit events');
SELECT is((SELECT count(*) FROM public.audit_chain_state),0::bigint,'operator cannot read audit chain state');
UPDATE public.settings SET value='{"country":"France"}'::jsonb WHERE key='lead_research_market';
SELECT is((SELECT count(*) FROM public.settings WHERE key='lead_research_market' AND value->>'country'='Germany'),1::bigint,'operator cannot change settings');

SELECT set_config('request.jwt.claims','{"sub":"10000000-0000-0000-0000-000000000001","role":"authenticated","app_metadata":{"role":"admin"}}',true);
SELECT is((SELECT count(*) FROM public.settings),2::bigint,'admin can read all settings');
INSERT INTO public.settings (key,value) VALUES ('rbac_fixture','{}'::jsonb);
SELECT is((SELECT count(*) FROM public.settings WHERE key='rbac_fixture'),1::bigint,'admin can write settings');
SELECT is((SELECT count(*) FROM public.logs WHERE module='rbac_test'),1::bigint,'admin can read the operator audit event');
SELECT is((SELECT count(*) FROM public.audit_chain_state),1::bigint,'admin can read audit chain state');

SELECT * FROM finish();
ROLLBACK;
