BEGIN;

-- Keep auth lookups behind stable, non-definer helpers in a non-exposed schema.
CREATE SCHEMA IF NOT EXISTS private;
REVOKE ALL ON SCHEMA private FROM PUBLIC, anon;
GRANT USAGE ON SCHEMA private TO authenticated;

CREATE OR REPLACE FUNCTION private.current_user_jwt()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = ''
AS $$ SELECT auth.jwt() $$;

CREATE OR REPLACE FUNCTION private.current_user_id()
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = ''
AS $$ SELECT auth.uid() $$;

REVOKE ALL ON FUNCTION private.current_user_jwt() FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION private.current_user_id() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION private.current_user_jwt() TO authenticated;
GRANT EXECUTE ON FUNCTION private.current_user_id() TO authenticated;

-- Rewrite every policy using auth.jwt()/auth.uid() through stable private helpers.
-- Policy names, roles, commands, predicates and write checks are preserved.
CREATE TEMP TABLE _jarvis_policy_rewrite ON COMMIT DROP AS
SELECT schemaname, tablename, policyname, roles, cmd, qual, with_check
FROM pg_policies
WHERE schemaname = 'public'
  AND (
    COALESCE(qual, '') LIKE '%auth.jwt()%'
    OR COALESCE(with_check, '') LIKE '%auth.jwt()%'
    OR COALESCE(qual, '') LIKE '%auth.uid()%'
    OR COALESCE(with_check, '') LIKE '%auth.uid()%'
  );

DO $$
DECLARE
  p record;
  v_sql text;
  v_qual text;
  v_check text;
BEGIN
  FOR p IN SELECT * FROM _jarvis_policy_rewrite LOOP
    EXECUTE format('DROP POLICY %I ON %I.%I', p.policyname, p.schemaname, p.tablename);
    v_sql := format(
      'CREATE POLICY %I ON %I.%I AS PERMISSIVE FOR %s TO %s',
      p.policyname, p.schemaname, p.tablename, p.cmd,
      COALESCE(array_to_string(p.roles, ', '), 'PUBLIC')
    );
    v_qual := replace(replace(p.qual, 'auth.jwt()', 'private.current_user_jwt()'),
                      'auth.uid()', 'private.current_user_id()');
    v_check := replace(replace(p.with_check, 'auth.jwt()', 'private.current_user_jwt()'),
                       'auth.uid()', 'private.current_user_id()');
    IF p.qual IS NOT NULL THEN
      v_sql := v_sql || format(' USING (%s)', v_qual);
    END IF;
    IF p.with_check IS NOT NULL THEN
      v_sql := v_sql || format(' WITH CHECK (%s)', v_check);
    END IF;
    EXECUTE v_sql;
  END LOOP;
END $$;

-- Split broad admin/operator ALL policies into command-specific write policies.
-- This preserves write rights while removing the duplicate SELECT evaluation.
DO $$
DECLARE
  t text;
  policy_name text;
BEGIN
  FOREACH t IN ARRAY ARRAY['email_drafts','jarvis_memory','leads','posts','tasks'] LOOP
    policy_name := t || '_admin_operator_write';
    EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', policy_name, t);
    EXECUTE format(
      'CREATE POLICY %I ON public.%I FOR INSERT TO authenticated WITH CHECK ((SELECT private.current_user_jwt() -> ''app_metadata'' ->> ''role'') IN (''admin'',''operator''))',
      t || '_admin_operator_insert', t
    );
    EXECUTE format(
      'CREATE POLICY %I ON public.%I FOR UPDATE TO authenticated USING ((SELECT private.current_user_jwt() -> ''app_metadata'' ->> ''role'') IN (''admin'',''operator'')) WITH CHECK ((SELECT private.current_user_jwt() -> ''app_metadata'' ->> ''role'') IN (''admin'',''operator''))',
      t || '_admin_operator_update', t
    );
    EXECUTE format(
      'CREATE POLICY %I ON public.%I FOR DELETE TO authenticated USING ((SELECT private.current_user_jwt() -> ''app_metadata'' ->> ''role'') IN (''admin'',''operator''))',
      t || '_admin_operator_delete', t
    );
  END LOOP;
END $$;

-- Lead email drafts are writable only for approved leads and draft-status rows.
DROP POLICY IF EXISTS lead_email_drafts_operator_write ON public.lead_email_drafts;
CREATE POLICY lead_email_drafts_operator_insert
ON public.lead_email_drafts FOR INSERT TO authenticated
WITH CHECK (
  (SELECT private.current_user_jwt() -> 'app_metadata' ->> 'role') IN ('admin','operator')
  AND status = 'draft'
  AND EXISTS (
    SELECT 1 FROM public.lead_review_states s
    WHERE s.lead_id = lead_email_drafts.lead_id AND s.review_status = 'approved'
  )
);
CREATE POLICY lead_email_drafts_operator_update
ON public.lead_email_drafts FOR UPDATE TO authenticated
USING (
  (SELECT private.current_user_jwt() -> 'app_metadata' ->> 'role') IN ('admin','operator')
  AND status = 'draft'
  AND EXISTS (
    SELECT 1 FROM public.lead_review_states s
    WHERE s.lead_id = lead_email_drafts.lead_id AND s.review_status = 'approved'
  )
)
WITH CHECK (
  (SELECT private.current_user_jwt() -> 'app_metadata' ->> 'role') IN ('admin','operator')
  AND status = 'draft'
  AND EXISTS (
    SELECT 1 FROM public.lead_review_states s
    WHERE s.lead_id = lead_email_drafts.lead_id AND s.review_status = 'approved'
  )
);
CREATE POLICY lead_email_drafts_operator_delete
ON public.lead_email_drafts FOR DELETE TO authenticated
USING (
  (SELECT private.current_user_jwt() -> 'app_metadata' ->> 'role') IN ('admin','operator')
  AND status = 'draft'
  AND EXISTS (
    SELECT 1 FROM public.lead_review_states s
    WHERE s.lead_id = lead_email_drafts.lead_id AND s.review_status = 'approved'
  )
);

-- Admins retain full settings access; operators retain read access to only the market key.
DROP POLICY IF EXISTS settings_admin_only ON public.settings;
DROP POLICY IF EXISTS settings_operator_read_market ON public.settings;
CREATE POLICY settings_role_read
ON public.settings FOR SELECT TO authenticated
USING (
  (SELECT private.current_user_jwt() -> 'app_metadata' ->> 'role') = 'admin'
  OR (
    (SELECT private.current_user_jwt() -> 'app_metadata' ->> 'role') = 'operator'
    AND key = 'lead_research_market'
  )
);
CREATE POLICY settings_admin_insert
ON public.settings FOR INSERT TO authenticated
WITH CHECK ((SELECT private.current_user_jwt() -> 'app_metadata' ->> 'role') = 'admin');
CREATE POLICY settings_admin_update
ON public.settings FOR UPDATE TO authenticated
USING ((SELECT private.current_user_jwt() -> 'app_metadata' ->> 'role') = 'admin')
WITH CHECK ((SELECT private.current_user_jwt() -> 'app_metadata' ->> 'role') = 'admin');
CREATE POLICY settings_admin_delete
ON public.settings FOR DELETE TO authenticated
USING ((SELECT private.current_user_jwt() -> 'app_metadata' ->> 'role') = 'admin');

COMMIT;
