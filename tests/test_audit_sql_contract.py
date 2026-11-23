from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_audit_migration_uses_trusted_admin_claim_and_denies_mutations():
    sql = (ROOT / "supabase/migrations/20261123093000_admin_audit_access_and_hash_chain.sql").read_text()
    normalized = " ".join(sql.lower().split())
    assert "auth.jwt()" in sql
    assert "app_metadata" in sql
    assert "user_metadata" not in sql
    assert "to authenticated" in normalized
    assert "grant select on table public.logs to authenticated" in normalized
    assert "revoke insert, update, delete, truncate" in normalized
    assert "before update or delete" in normalized
    assert "before truncate" in normalized


def test_audit_hash_chain_serializes_inserts_and_uses_sha256():
    sql = (ROOT / "supabase/migrations/20261123093000_admin_audit_access_and_hash_chain.sql").read_text()
    assert "pg_advisory_xact_lock" in sql
    assert "extensions.digest" in sql
    assert "'sha256'" in sql
    assert "previous_hash" in sql
    assert "entry_hash" in sql


def test_audit_database_test_covers_reader_admin_and_append_only_contract():
    sql = (ROOT / "supabase/tests/audit_access_and_integrity.test.sql").read_text()
    assert '"role":"reader"' in sql
    assert '"role":"admin"' in sql
    assert "UPDATE unexpectedly succeeded" in sql
    assert "DELETE unexpectedly succeeded" in sql
    assert "second event must link" in sql
