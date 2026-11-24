-- Run only against an isolated PostgreSQL/Supabase test database.
BEGIN;
SELECT plan(25);

SELECT ok((SELECT relrowsecurity FROM pg_class WHERE oid='public.leads'::regclass), 'RLS enabled on leads');
SELECT ok((SELECT relrowsecurity FROM pg_class WHERE oid='public.tasks'::regclass), 'RLS enabled on tasks');
SELECT ok((SELECT relrowsecurity FROM pg_class WHERE oid='public.email_drafts'::regclass), 'RLS enabled on email_drafts');
SELECT ok((SELECT relrowsecurity FROM pg_class WHERE oid='public.settings'::regclass), 'RLS enabled on settings');
SELECT ok((SELECT relrowsecurity FROM pg_class WHERE oid='public.jarvis_memory'::regclass), 'RLS enabled on jarvis_memory');
SELECT ok((SELECT relrowsecurity FROM pg_class WHERE oid='public.posts'::regclass), 'RLS enabled on posts');
SELECT ok((SELECT relrowsecurity FROM pg_class WHERE oid='public.jarvis_proactive_state'::regclass), 'RLS enabled on proactive state');
SELECT ok(NOT has_table_privilege('anon','public.leads','SELECT'), 'anon cannot read leads');
SELECT ok(has_table_privilege('authenticated','public.leads','SELECT'), 'authenticated has leads SELECT grant');
SELECT ok(has_table_privilege('authenticated','public.leads','INSERT'), 'authenticated has leads INSERT grant, filtered by RLS');
SELECT ok(NOT has_table_privilege('authenticated','public.logs','INSERT'), 'authenticated cannot append audit events');
SELECT ok(NOT has_table_privilege('authenticated','public.jarvis_proactive_state','SELECT'), 'authenticated cannot read machine state');

INSERT INTO public.leads (id, company_name) VALUES
('a0000000-0000-4000-8000-000000000001','RBAC fixture');

SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims','{"sub":"10000000-0000-0000-0000-000000000003","role":"authenticated","app_metadata":{"role":"reader"}}',true);
SELECT is((SELECT count(*) FROM public.leads WHERE company_name='RBAC fixture'),1::bigint,'reader can read shared leads');
SELECT is((WITH inserted AS (INSERT INTO public.leads (company_name) VALUES ('reader denied') RETURNING 1) SELECT count(*) FROM inserted),0::bigint,'reader cannot insert leads');
SELECT is((WITH changed AS (UPDATE public.leads SET company_name='reader changed' WHERE company_name='RBAC fixture' RETURNING 1) SELECT count(*) FROM changed),0::bigint,'reader cannot update leads');
SELECT is((SELECT count(*) FROM public.settings),0::bigint,'reader cannot read settings');
SELECT is((SELECT count(*) FROM public.logs),0::bigint,'reader cannot read audit events');
SELECT is((SELECT count(*) FROM public.jarvis_proactive_state),0::bigint,'reader cannot read proactive state');

SELECT set_config('request.jwt.claims','{"sub":"10000000-0000-0000-0000-000000000002","role":"authenticated","app_metadata":{"role":"operator"}}',true);
SELECT is((WITH inserted AS (INSERT INTO public.leads (company_name) VALUES ('operator allowed') RETURNING 1) SELECT count(*) FROM inserted),1::bigint,'operator can insert leads');
SELECT is((WITH inserted AS (INSERT INTO public.logs (module,message,level,action,status) VALUES ('rbac_test','operator event','info','test','success') RETURNING 1) SELECT count(*) FROM inserted),1::bigint,'operator can append an audit event');
SELECT is((SELECT actor_user_id::text FROM public.logs WHERE module='rbac_test' LIMIT 1),'10000000-0000-0000-0000-000000000002','audit trigger binds actor to authenticated JWT');
SELECT is((SELECT count(*) FROM public.settings),0::bigint,'operator cannot read settings');

SELECT set_config('request.jwt.claims','{"sub":"10000000-0000-0000-0000-000000000001","role":"authenticated","app_metadata":{"role":"admin"}}',true);
SELECT is((SELECT count(*) FROM public.settings),0::bigint,'admin can query settings table even when empty');
SELECT is((WITH inserted AS (INSERT INTO public.settings (key,value) VALUES ('rbac_fixture','{}'::jsonb) RETURNING 1) SELECT count(*) FROM inserted),1::bigint,'admin can write settings');
SELECT is((SELECT count(*) FROM public.logs WHERE module='rbac_test'),1::bigint,'admin can read the operator audit event');

SELECT * FROM finish();
ROLLBACK;
