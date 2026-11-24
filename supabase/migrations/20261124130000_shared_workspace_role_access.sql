-- Role-based access for the single shared JARVIS workspace.
-- This is intentionally NOT tenant isolation: all permitted roles see the
-- same workspace rows. Do not use this policy model for multiple customers.
-- Requires the audit schema migrations to have been applied first.

DO $$
DECLARE
  table_name text;
BEGIN
  FOREACH table_name IN ARRAY ARRAY[
    'leads', 'tasks', 'email_drafts', 'settings', 'logs',
    'jarvis_memory', 'jarvis_proactive_state', 'posts',
    'audit_chain_state'
  ] LOOP
    IF to_regclass(format('public.%I', table_name)) IS NULL THEN
      RAISE EXCEPTION 'Required JARVIS table public.% is missing; reconcile schema before RBAC migration', table_name;
    END IF;
  END LOOP;
END;
$$;

-- Remove inherited/default API grants first. service_role retains its
-- explicit privileged server-side access and bypasses RLS by design.
REVOKE ALL ON TABLE
  public.leads, public.tasks, public.email_drafts, public.settings,
  public.logs, public.jarvis_memory, public.jarvis_proactive_state,
  public.posts, public.audit_chain_state
FROM PUBLIC, anon, authenticated;

-- The authenticated role receives only the operations that RLS further
-- constrains. Reader writes are rejected by policies, not by UI convention.
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
  public.leads, public.tasks, public.email_drafts, public.jarvis_memory,
  public.posts, public.settings
TO authenticated;

GRANT SELECT ON TABLE public.logs, public.audit_chain_state TO authenticated;

-- settings uses a legacy integer sequence in the live database. Sequence
-- access alone grants no row access; the table policy remains admin-only.
DO $$
DECLARE
  seq_name text;
BEGIN
  seq_name := pg_get_serial_sequence('public.settings', 'id');
  IF seq_name IS NOT NULL THEN
    EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE %s TO authenticated', seq_name);
  END IF;
END;
$$;

ALTER TABLE public.leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.email_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.jarvis_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.jarvis_proactive_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_chain_state ENABLE ROW LEVEL SECURITY;

-- Shared-workspace business data: all roles can read; admin/operator can
-- create, update and delete. JWT authorization uses trusted app_metadata only.
DO $$
DECLARE
  table_name text;
BEGIN
  FOREACH table_name IN ARRAY ARRAY[
    'leads', 'tasks', 'email_drafts', 'jarvis_memory', 'posts'
  ] LOOP
    EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', table_name || '_shared_read', table_name);
    EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', table_name || '_admin_operator_write', table_name);
    EXECUTE format(
      'CREATE POLICY %I ON public.%I FOR SELECT TO authenticated USING ((SELECT auth.jwt() -> ''app_metadata'' ->> ''role'') IN (''admin'', ''operator'', ''reader''))',
      table_name || '_shared_read', table_name
    );
    EXECUTE format(
      'CREATE POLICY %I ON public.%I FOR ALL TO authenticated USING ((SELECT auth.jwt() -> ''app_metadata'' ->> ''role'') IN (''admin'', ''operator'')) WITH CHECK ((SELECT auth.jwt() -> ''app_metadata'' ->> ''role'') IN (''admin'', ''operator''))',
      table_name || '_admin_operator_write', table_name
    );
  END LOOP;
END;
$$;

-- Settings writes are admin-only. Operators may read only the non-secret
-- lead-research market key; all other settings remain admin-only.
DROP POLICY IF EXISTS settings_admin_only ON public.settings;
DROP POLICY IF EXISTS settings_operator_read_market ON public.settings;
CREATE POLICY settings_admin_only
  ON public.settings
  FOR ALL
  TO authenticated
  USING ((SELECT auth.jwt() -> 'app_metadata' ->> 'role') = 'admin')
  WITH CHECK ((SELECT auth.jwt() -> 'app_metadata' ->> 'role') = 'admin');
CREATE POLICY settings_operator_read_market
  ON public.settings
  FOR SELECT
  TO authenticated
  USING (
    (SELECT auth.jwt() -> 'app_metadata' ->> 'role') = 'operator'
    AND key = 'lead_research_market'
  );

-- Audit events are admin-readable and append-only. Admin/operator users may
-- append events only as themselves; UPDATE/DELETE/TRUNCATE remain forbidden.
DROP POLICY IF EXISTS "Admins can read audit logs" ON public.logs;
DROP POLICY IF EXISTS logs_admin_read_only ON public.logs;
CREATE POLICY logs_admin_read_only
  ON public.logs
  FOR SELECT
  TO authenticated
  USING ((SELECT auth.jwt() -> 'app_metadata' ->> 'role') = 'admin');

-- Authenticated admins/operators may append only their own audit event.
-- The trigger assigns actor_user_id from auth.uid() and advances the chain
-- under its tightly scoped SECURITY DEFINER owner context.
-- SECURITY DEFINER is narrowly scoped to the insert trigger so that it
-- can lock/update the private chain-head row. Direct EXECUTE is revoked below.
CREATE OR REPLACE FUNCTION public.set_logs_audit_hash_chain()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, extensions
AS $
DECLARE
  prior_hash text;
  canonical_row text;
BEGIN
  -- A JWT-authenticated user cannot spoof another actor id.
  IF auth.uid() IS NOT NULL THEN
    NEW.actor_user_id := auth.uid();
  END IF;

  INSERT INTO public.audit_chain_state (singleton, last_hash)
  VALUES (true, repeat('0', 64))
  ON CONFLICT (singleton) DO NOTHING;

  SELECT last_hash INTO prior_hash
    FROM public.audit_chain_state
   WHERE singleton = true
   FOR UPDATE;

  NEW.previous_hash := coalesce(prior_hash, repeat('0', 64));
  canonical_row := (to_jsonb(NEW) - 'previous_hash' - 'entry_hash')::text;
  NEW.entry_hash := encode(
    extensions.digest(convert_to(NEW.previous_hash || ':' || canonical_row, 'UTF8'), 'sha256'),
    'hex'
  );

  UPDATE public.audit_chain_state
     SET last_hash = NEW.entry_hash,
         updated_at = clock_timestamp()
   WHERE singleton = true;
  RETURN NEW;
END;
$;

REVOKE ALL ON FUNCTION public.set_logs_audit_hash_chain() FROM PUBLIC, anon, authenticated;

GRANT INSERT ON TABLE public.logs TO authenticated;
DROP POLICY IF EXISTS logs_admin_operator_append ON public.logs;
CREATE POLICY logs_admin_operator_append
  ON public.logs
  FOR INSERT
  TO authenticated
  WITH CHECK (
    (SELECT auth.jwt() -> 'app_metadata' ->> 'role') IN ('admin', 'operator')
    AND actor_user_id = (SELECT auth.uid())
  );

REVOKE UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
  ON TABLE public.logs FROM PUBLIC, anon, authenticated;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
  ON TABLE public.audit_chain_state FROM PUBLIC, anon, authenticated;

-- Proactive monitor state is a machine-owned singleton, never user-readable.
REVOKE ALL ON TABLE public.jarvis_proactive_state FROM PUBLIC, anon, authenticated;

-- Keep anon explicitly out of every exposed business table.
REVOKE ALL ON TABLE
  public.leads, public.tasks, public.email_drafts, public.settings,
  public.logs, public.jarvis_memory, public.jarvis_proactive_state,
  public.posts, public.audit_chain_state
FROM anon;

COMMENT ON POLICY leads_shared_read ON public.leads IS
  'Single shared workspace: admin/operator/reader can read; this is not tenant isolation.';
