-- Run with: supabase test db (isolated development database only).
-- The test is transactional and rolls back its synthetic rows.
begin;

do $$
declare
  first_row public.logs%rowtype;
  second_row public.logs%rowtype;
begin
  if not (select relrowsecurity from pg_class where oid = 'public.logs'::regclass) then
    raise exception 'RLS must be enabled on public.logs';
  end if;
  if not has_table_privilege('authenticated', 'public.logs', 'SELECT') then
    raise exception 'authenticated must have SELECT grant for policy-filtered reads';
  end if;
  if has_table_privilege('anon', 'public.logs', 'SELECT') then
    raise exception 'anon must not have SELECT grant on public.logs';
  end if;
  if has_table_privilege('authenticated', 'public.logs', 'INSERT')
     or has_table_privilege('authenticated', 'public.logs', 'UPDATE')
     or has_table_privilege('authenticated', 'public.logs', 'DELETE')
     or has_table_privilege('authenticated', 'public.logs', 'TRUNCATE') then
    raise exception 'authenticated must not mutate audit rows';
  end if;

  insert into public.logs (module, level, message, action, status)
  values ('audit_security_test', 'info', 'first synthetic event', 'test', 'success')
  returning * into first_row;

  if first_row.entry_hash is null or length(first_row.entry_hash) <> 64 then
    raise exception 'first audit event must have a SHA-256 entry hash';
  end if;
  if first_row.previous_hash <> repeat('0', 64) then
    raise exception 'first hash-chain event must use the genesis hash';
  end if;

  insert into public.logs (module, level, message, action, status)
  values ('audit_security_test', 'info', 'second synthetic event', 'test', 'success')
  returning * into second_row;

  if second_row.previous_hash <> first_row.entry_hash then
    raise exception 'second event must link to the previous entry hash';
  end if;

  begin
    update public.logs set message = 'tampered' where id = first_row.id;
    raise exception 'UPDATE unexpectedly succeeded';
  exception when sqlstate '55000' then
    null;
  end;

  begin
    delete from public.logs where id = first_row.id;
    raise exception 'DELETE unexpectedly succeeded';
  exception when sqlstate '55000' then
    null;
  end;
end;
$$;

-- Reader JWT: RLS must hide the synthetic events.
set local role authenticated;
select set_config(
  'request.jwt.claims',
  '{"sub":"10000000-0000-0000-0000-000000000001","role":"authenticated","app_metadata":{"role":"reader"}}',
  true
);
do $$
begin
  if (select count(*) from public.logs where module = 'audit_security_test') <> 0 then
    raise exception 'reader role must not read audit events';
  end if;
end;
$$;

-- Admin JWT: only the trusted app_metadata claim grants access.
select set_config(
  'request.jwt.claims',
  '{"sub":"10000000-0000-0000-0000-000000000002","role":"authenticated","app_metadata":{"role":"admin"}}',
  true
);
do $$
begin
  if (select count(*) from public.logs where module = 'audit_security_test') <> 2 then
    raise exception 'admin role must read the synthetic audit events';
  end if;
end;
$$;

rollback;
