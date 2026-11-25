from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_audit_migration_uses_trusted_admin_claim_and_denies_mutations():
    sql = (ROOT / "supabase/migrations/20261123093000_admin_audit_access_and_hash_chain.sql").read_text()
    normalized = " ".join(sql.lower().split())
    assert "auth.jwt()" in sql
    assert "app_metadata" in sql
    assert "auth.jwt() -> 'user_metadata'" not in sql
    assert "to authenticated" in normalized
    assert "grant select on table public.logs to authenticated" in normalized
    assert "revoke insert, update, delete, truncate" in normalized
    assert "before update or delete" in normalized
    assert "before truncate" in normalized


def test_audit_hash_chain_serializes_inserts_and_uses_sha256():
    sql = (ROOT / "supabase/migrations/20261123093000_admin_audit_access_and_hash_chain.sql").read_text()
    assert "audit_chain_state" in sql
    assert "for update" in sql.lower()
    assert "extensions.digest" in sql
    assert "'sha256'" in sql
    assert "previous_hash" in sql
    assert "entry_hash" in sql


def test_audit_database_test_covers_reader_admin_and_append_only_contract():
    sql = (ROOT / "supabase/tests/audit_access_and_integrity.test.sql").read_text()
    normalized = " ".join(sql.lower().split())
    assert '"role":"reader"' in sql
    assert '"role":"admin"' in sql
    assert "update is rejected" in normalized
    assert "delete is rejected" in normalized
    assert "select plan(17)" in normalized
    assert "second event links to the first event" in normalized


def test_audit_integrity_rpc_is_invoker_scoped_and_admin_read_protected():
    sql = (ROOT / "supabase/migrations/20261123093000_admin_audit_access_and_hash_chain.sql").read_text().lower()
    assert "verify_logs_audit_chain" in sql
    assert "security invoker" in sql
    assert "grant execute on function public.verify_logs_audit_chain() to authenticated" in " ".join(sql.split())
    assert "admins can read audit chain state" in sql
    assert "disconnected_entries" in sql
    assert "set search_path = pg_catalog\nas $" in sql
    assert "coalesce(state_hash = repeat('0', 64), false)" in sql



def test_atomic_task_approval_migration_binds_principal_payload_and_expiry():
    sql = (ROOT / "supabase/migrations/20261125160000_atomic_task_approvals_and_operations.sql").read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists private.task_approvals" in normalized
    assert "create table if not exists private.task_action_operations" in normalized
    assert "extensions.digest" in normalized
    assert "payload_hash" in normalized
    assert "consumed_at is null" in normalized
    assert "expires_at > clock_timestamp()" in normalized
    assert "auth.uid()" in normalized
    assert "auth.jwt()" in normalized
    assert "app_metadata" in normalized
    assert "user_metadata" not in normalized
    assert "on conflict (operation_id) do nothing" in normalized
    assert "for update" in normalized
    assert "execute_approved_task_action" in normalized
    assert "revoke all on function public.execute_approved_task_action" in normalized
    assert "grant execute on function public.execute_approved_task_action" in normalized
    assert "set search_path = pg_catalog" in normalized


def test_task_execution_and_audit_writes_share_one_security_definer_transaction():
    sql = (ROOT / "supabase/migrations/20261125160000_atomic_task_approvals_and_operations.sql").read_text()
    normalized = " ".join(sql.lower().split())
    execution = normalized[normalized.index("create or replace function public.execute_approved_task_action"):]
    assert execution.index("update private.task_approvals") < execution.index("insert into public.logs")
    assert execution.index("insert into public.logs") < execution.index("insert into public.tasks")
    assert execution.index("insert into public.tasks") < execution.index("update private.task_action_operations")
    assert "approved, actor_user_id" in execution
    assert "status, result" in execution



def test_task_create_payload_accepts_explicit_null_due_at_and_replay_is_serialized():
    sql = (ROOT / "supabase/migrations/20261125160000_atomic_task_approvals_and_operations.sql").read_text()
    normalized = " ".join(sql.lower().split())
    assert "when jsonb_typeof(p_action -> 'due_at') = 'null' then false" in normalized
    assert "when jsonb_typeof(p_action -> 'due_at') = 'string'" in normalized
    assert "case when jsonb_typeof(p_action -> 'due_at') = 'string'" in normalized
    execution = normalized[normalized.index("create or replace function public.execute_approved_task_action"):]
    assert "on conflict (operation_id) do nothing" in execution
    assert "for update" in execution
    assert "if v_stored_result is not null then return v_stored_result" in execution
    assert "update private.task_approvals" in execution
    assert "consumed_at is null" in execution



def test_final_task_privilege_lockdown_is_separate_for_zero_downtime_rollout():
    migration = (ROOT / "supabase/migrations/20261125170000_enforce_atomic_task_write_privileges.sql").read_text()
    normalized = " ".join(migration.lower().split())
    assert "revoke insert, update, delete, truncate, references, trigger on table public.tasks" in normalized
    assert "from public, anon, authenticated, service_role" in normalized
    assert "grant select on table public.tasks to authenticated, service_role" in normalized
