-- Catalog-level postconditions for the complete audit + shared-workspace RBAC chain.
-- Run only after all repository migrations against the isolated PostgreSQL 17 fixture.
-- This file is intentionally read-only: it verifies the resulting catalog and ACLs.

DO $catalog_postconditions$
DECLARE
  object_count integer;
  bad_count integer;
  expected_tables text[] := ARRAY[
    'leads', 'tasks', 'email_drafts', 'settings', 'logs',
    'jarvis_memory', 'jarvis_proactive_state', 'posts', 'audit_chain_state'
  ];
BEGIN
  -- All expected application relations exist, are owned by the fixture owner,
  -- and have RLS enabled.
  SELECT count(*) INTO object_count
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE n.nspname = 'public'
     AND c.relname = ANY(expected_tables)
     AND c.relkind = 'r'
     AND c.relowner = 'postgres'::regrole;
  IF object_count <> cardinality(expected_tables) THEN
    RAISE EXCEPTION 'expected % postgres-owned public tables, found %',
      cardinality(expected_tables), object_count;
  END IF;

  SELECT count(*) INTO object_count
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE n.nspname = 'public'
     AND c.relname = ANY(expected_tables)
     AND c.relrowsecurity;
  IF object_count <> cardinality(expected_tables) THEN
    RAISE EXCEPTION 'RLS is not enabled on every expected public table';
  END IF;

  -- The migration chain should install exactly the documented policy set:
  -- 5 shared business tables x 2, settings x 2, logs x 2, chain state x 1.
  SELECT count(*) INTO object_count
    FROM pg_policies
   WHERE schemaname = 'public'
     AND tablename = ANY(expected_tables);
  IF object_count <> 15 THEN
    RAISE EXCEPTION 'expected 15 public RBAC policies, found %', object_count;
  END IF;

  SELECT count(*) INTO bad_count
    FROM pg_policies
   WHERE schemaname = 'public'
     AND tablename = ANY(expected_tables)
     AND (coalesce(qual, '') || ' ' || coalesce(with_check, '')) ILIKE '%user_metadata%';
  IF bad_count <> 0 THEN
    RAISE EXCEPTION 'an RLS policy trusts user_metadata for authorization';
  END IF;

  -- No API role may access public tables anonymously. Authenticated grants
  -- are deliberately narrower on the audit chain and machine-owned state.
  SELECT count(*) INTO bad_count
    FROM unnest(expected_tables) AS t(table_name)
   WHERE has_table_privilege('anon', format('public.%I', table_name), 'SELECT')
      OR has_table_privilege('anon', format('public.%I', table_name), 'INSERT')
      OR has_table_privilege('anon', format('public.%I', table_name), 'UPDATE')
      OR has_table_privilege('anon', format('public.%I', table_name), 'DELETE');
  IF bad_count <> 0 THEN
    RAISE EXCEPTION 'anon has unexpected privileges on a public application table';
  END IF;

  IF NOT has_table_privilege('authenticated', 'public.tasks', 'SELECT')
     OR has_table_privilege('authenticated', 'public.tasks', 'INSERT')
     OR has_table_privilege('authenticated', 'public.tasks', 'UPDATE')
     OR has_table_privilege('authenticated', 'public.tasks', 'DELETE')
     OR NOT has_table_privilege('service_role', 'public.tasks', 'SELECT')
     OR has_table_privilege('service_role', 'public.tasks', 'INSERT')
     OR has_table_privilege('service_role', 'public.tasks', 'UPDATE')
     OR has_table_privilege('service_role', 'public.tasks', 'DELETE') THEN
    RAISE EXCEPTION 'task table grants bypass atomic approval RPC';
  END IF;

  IF NOT has_table_privilege('authenticated', 'public.logs', 'SELECT')
     OR NOT has_table_privilege('authenticated', 'public.logs', 'INSERT')
     OR has_table_privilege('authenticated', 'public.logs', 'UPDATE')
     OR has_table_privilege('authenticated', 'public.logs', 'DELETE')
     OR has_table_privilege('authenticated', 'public.logs', 'TRUNCATE') THEN
    RAISE EXCEPTION 'authenticated logs grants do not match append/read-only design';
  END IF;

  IF NOT has_table_privilege('authenticated', 'public.audit_chain_state', 'SELECT')
     OR has_table_privilege('authenticated', 'public.audit_chain_state', 'INSERT')
     OR has_table_privilege('authenticated', 'public.audit_chain_state', 'UPDATE')
     OR has_table_privilege('authenticated', 'public.audit_chain_state', 'DELETE')
     OR has_table_privilege('authenticated', 'public.jarvis_proactive_state', 'SELECT') THEN
    RAISE EXCEPTION 'chain-state or proactive-state grants are broader than intended';
  END IF;

  IF NOT has_sequence_privilege('authenticated', 'public.settings_id_seq', 'USAGE')
     OR NOT has_sequence_privilege('authenticated', 'public.settings_id_seq', 'SELECT') THEN
    RAISE EXCEPTION 'authenticated settings sequence grants are missing';
  END IF;

  -- Verify function ownership, SECURITY DEFINER boundary and EXECUTE ACLs.
  SELECT count(*) INTO object_count
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
   WHERE n.nspname = 'public'
     AND p.proname IN (
       'verify_logs_audit_chain',
       'set_logs_audit_hash_chain',
       'reject_logs_audit_mutation'
     )
     AND p.proowner = 'postgres'::regrole;
  IF object_count <> 3 THEN
    RAISE EXCEPTION 'expected three postgres-owned audit functions, found %', object_count;
  END IF;

  IF NOT (SELECT prosecdef FROM pg_proc
           WHERE oid = 'public.set_logs_audit_hash_chain()'::regprocedure)
     OR (SELECT prosecdef FROM pg_proc
           WHERE oid = 'public.verify_logs_audit_chain()'::regprocedure) THEN
    RAISE EXCEPTION 'audit function SECURITY DEFINER / INVOKER boundary is incorrect';
  END IF;

  IF has_function_privilege('anon', 'public.set_logs_audit_hash_chain()', 'EXECUTE')
     OR has_function_privilege('authenticated', 'public.set_logs_audit_hash_chain()', 'EXECUTE')
     OR has_function_privilege('anon', 'public.verify_logs_audit_chain()', 'EXECUTE')
     OR NOT has_function_privilege('authenticated', 'public.verify_logs_audit_chain()', 'EXECUTE')
     OR NOT has_function_privilege('service_role', 'public.verify_logs_audit_chain()', 'EXECUTE') THEN
    RAISE EXCEPTION 'audit function EXECUTE ACLs do not match the intended boundary';
  END IF;

  -- Trigger inventory and validity: insert hashing, update/delete rejection,
  -- and truncate rejection must all be installed and enabled.
  SELECT count(*) INTO object_count
    FROM pg_trigger t
    WHERE t.tgrelid = 'public.logs'::regclass
      AND NOT t.tgisinternal
      AND t.tgname IN (
        'logs_audit_hash_chain',
        'logs_audit_no_update_delete',
        'logs_audit_no_truncate'
      )
      AND t.tgenabled = 'O';
  IF object_count <> 3 THEN
    RAISE EXCEPTION 'expected three enabled audit triggers, found %', object_count;
  END IF;

  -- All structured-audit indexes must exist and be valid.
  SELECT count(*) INTO object_count
    FROM pg_index i
    JOIN pg_class idx ON idx.oid = i.indexrelid
   WHERE i.indrelid = 'public.logs'::regclass
     AND idx.relname = ANY(ARRAY[
       'logs_created_at_desc_idx',
       'logs_operation_id_idx',
       'logs_module_action_created_idx',
       'logs_status_created_idx'
     ])
     AND i.indisvalid
     AND i.indisready;
  IF object_count <> 4 THEN
    RAISE EXCEPTION 'expected four valid structured-audit indexes, found %', object_count;
  END IF;

  -- Owner-specific default ACLs must not reintroduce API-role grants.
  SELECT count(*) INTO bad_count
    FROM pg_default_acl d
    JOIN pg_namespace n ON n.oid = d.defaclnamespace
    CROSS JOIN LATERAL aclexplode(d.defaclacl) a
   WHERE n.nspname = 'public'
     AND d.defaclrole = 'postgres'::regrole
     AND a.grantee IN ('anon'::regrole, 'authenticated'::regrole);
  IF bad_count <> 0 THEN
    RAISE EXCEPTION 'postgres public-schema default ACLs grant privileges to API roles';
  END IF;

  -- Approval state is isolated in an unexposed schema. Application roles
  -- execute only the narrow SECURITY DEFINER RPCs, never table DML.
  IF has_schema_privilege('anon', 'private', 'USAGE')
     OR has_schema_privilege('authenticated', 'private', 'USAGE')
     OR has_schema_privilege('service_role', 'private', 'USAGE') THEN
    RAISE EXCEPTION 'private approval schema is exposed to an API role';
  END IF;

  IF has_table_privilege('anon', 'private.task_approvals', 'SELECT')
     OR has_table_privilege('authenticated', 'private.task_approvals', 'SELECT')
     OR has_table_privilege('service_role', 'private.task_approvals', 'SELECT')
     OR has_table_privilege('anon', 'private.task_action_operations', 'INSERT')
     OR has_table_privilege('authenticated', 'private.task_action_operations', 'INSERT')
     OR has_table_privilege('service_role', 'private.task_action_operations', 'INSERT') THEN
    RAISE EXCEPTION 'an API role has direct access to private approval/idempotency tables';
  END IF;

  SELECT count(*) INTO object_count
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
   WHERE n.nspname = 'public'
     AND p.proname IN (
       'issue_pending_approval',
       'consume_pending_approval',
       'revoke_pending_approval',
       'execute_approved_task_action'
     )
     AND p.prosecdef
     AND p.proconfig @> ARRAY['search_path=pg_catalog'];
  IF object_count <> 4 THEN
    RAISE EXCEPTION 'expected four SECURITY DEFINER approval RPCs with fixed search_path, found %', object_count;
  END IF;

  IF has_function_privilege('anon', 'public.issue_pending_approval(text,text,jsonb,integer)', 'EXECUTE')
     OR has_function_privilege('anon', 'public.consume_pending_approval(text,text,jsonb)', 'EXECUTE')
     OR has_function_privilege('anon', 'public.revoke_pending_approval(text,text)', 'EXECUTE')
     OR has_function_privilege('anon', 'public.execute_approved_task_action(text,text,uuid,jsonb)', 'EXECUTE')
     OR has_function_privilege('authenticated', 'public.issue_pending_approval(text,text,jsonb,integer)', 'EXECUTE')
     OR NOT has_function_privilege('service_role', 'public.issue_pending_approval(text,text,jsonb,integer)', 'EXECUTE')
     OR NOT has_function_privilege('authenticated', 'public.consume_pending_approval(text,text,jsonb)', 'EXECUTE')
     OR NOT has_function_privilege('authenticated', 'public.revoke_pending_approval(text,text)', 'EXECUTE')
     OR NOT has_function_privilege('authenticated', 'public.execute_approved_task_action(text,text,uuid,jsonb)', 'EXECUTE')
     OR NOT has_function_privilege('service_role', 'public.consume_pending_approval(text,text,jsonb)', 'EXECUTE')
     OR NOT has_function_privilege('service_role', 'public.revoke_pending_approval(text,text)', 'EXECUTE')
     OR NOT has_function_privilege('service_role', 'public.execute_approved_task_action(text,text,uuid,jsonb)', 'EXECUTE') THEN
    RAISE EXCEPTION 'approval RPC EXECUTE grants do not match the user/service trust boundary';
  END IF;

  IF has_function_privilege('anon', 'private.assert_task_approval_principal(text,boolean)', 'EXECUTE')
     OR has_function_privilege('authenticated', 'private.assert_task_approval_principal(text,boolean)', 'EXECUTE')
     OR has_function_privilege('service_role', 'private.assert_task_approval_principal(text,boolean)', 'EXECUTE') THEN
    RAISE EXCEPTION 'internal approval principal validator is executable by an API role';
  END IF;

  RAISE NOTICE 'Catalog postconditions passed: ownership, RLS, 15 policies, API grants, audit triggers and private atomic-approval RPC ACLs.';
END
$catalog_postconditions$;
