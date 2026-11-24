"""Regression checks for SQL recovered from the production migration ledger."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"

RECOVERED = {
    "20261119191911_create_jarvis_memory_and_fk_indexes.sql": (
        "create table if not exists public.jarvis_memory",
        "create index if not exists tasks_lead_id_idx",
        "create index if not exists email_drafts_lead_id_idx",
    ),
    "20261119192040_complete_jarvis_runtime_schema.sql": (
        "add column if not exists notes text",
        "create table if not exists public.jarvis_proactive_state",
        "alter column value type jsonb",
    ),
    "20261119192145_enable_rls_on_legacy_posts.sql": (
        "alter table public.posts enable row level security",
    ),
    "20261119192412_revoke_anon_authenticated_public_table_and_sequence_privileges.sql": (
        "revoke all privileges on all tables in schema public from anon, authenticated",
        "revoke all privileges on all sequences in schema public from anon, authenticated",
    ),
    "20261119192559_secure_postgres_default_privileges_public_schema.sql": (
        "alter default privileges for role postgres in schema public",
        "revoke execute on functions from anon, authenticated",
    ),
}


def test_all_remote_ledger_migrations_have_recovered_repository_sources():
    for filename in RECOVERED:
        assert (MIGRATIONS / filename).is_file(), filename


def test_recovered_migration_sql_contains_ledger_statements():
    for filename, fragments in RECOVERED.items():
        sql = (MIGRATIONS / filename).read_text(encoding="utf-8").lower()
        for fragment in fragments:
            assert fragment in sql, (filename, fragment)
