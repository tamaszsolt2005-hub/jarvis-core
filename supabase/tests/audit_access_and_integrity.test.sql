-- Run with: supabase test db (isolated development database only).
begin;
select plan(17);

select ok(
  (select relrowsecurity from pg_class where oid = 'public.logs'::regclass),
  'RLS is enabled on public.logs'
);
select ok(
  has_table_privilege('authenticated', 'public.logs', 'SELECT'),
  'authenticated receives a SELECT grant filtered by RLS'
);
select ok(
  not has_table_privilege('anon', 'public.logs', 'SELECT'),
  'anon has no SELECT grant on audit rows'
);
select ok(
  not has_table_privilege('authenticated', 'public.logs', 'INSERT')
  and not has_table_privilege('authenticated', 'public.logs', 'UPDATE')
  and not has_table_privilege('authenticated', 'public.logs', 'DELETE'),
  'authenticated cannot directly mutate audit rows'
);

select lives_ok(
  $$
    insert into public.logs (id, module, level, message, action, status)
    values
      ('90000000-0000-0000-0000-000000000001', 'audit_security_test', 'info', 'first synthetic event', 'test', 'success'),
      ('90000000-0000-0000-0000-000000000002', 'audit_security_test', 'info', 'second synthetic event', 'test', 'success')
  $$,
  'server-side append creates two audit rows'
);

select ok(
  (select length(entry_hash) = 64
     from public.logs
    where id = '90000000-0000-0000-0000-000000000001'),
  'first event receives a SHA-256 hash'
);
select is(
  (select previous_hash from public.logs where id = '90000000-0000-0000-0000-000000000002'),
  (select entry_hash from public.logs where id = '90000000-0000-0000-0000-000000000001'),
  'second event links to the first event'
);

select throws_ok(
  $$update public.logs set message = 'tampered' where id = '90000000-0000-0000-0000-000000000001'$$,
  '55000', null, 'UPDATE is rejected'
);
select throws_ok(
  $$delete from public.logs where id = '90000000-0000-0000-0000-000000000001'$$,
  '55000', null, 'DELETE is rejected'
);
select throws_ok(
  $$truncate public.logs$$,
  '55000', null, 'TRUNCATE is rejected'
);

select ok(
  (select ok from public.verify_logs_audit_chain()),
  'valid audit chain passes integrity verification for the database owner'
);

set local role authenticated;
select set_config(
  'request.jwt.claims',
  '{"sub":"10000000-0000-0000-0000-000000000001","role":"authenticated","app_metadata":{"role":"reader"}}',
  true
);
select is(
  (select count(*) from public.logs where module = 'audit_security_test'),
  0::bigint,
  'reader cannot read audit events'
);
select ok(
  (select ok from public.verify_logs_audit_chain()) is false,
  'reader cannot obtain a successful integrity result'
);

select set_config(
  'request.jwt.claims',
  '{"sub":"10000000-0000-0000-0000-000000000002","role":"authenticated","app_metadata":{"role":"admin"}}',
  true
);
select is(
  (select count(*) from public.logs where module = 'audit_security_test'),
  2::bigint,
  'admin can read audit events'
);
select ok(
  (select ok from public.verify_logs_audit_chain()),
  'admin can verify the audit hash chain'
);

select * from finish();
rollback;
