"""Regression checks for the deployable Supabase schema.""" 
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_schema_migrations_are_real_sql_lines_not_escaped_text():
    schema = (ROOT / "supabase" / "schema.sql").read_text(encoding="utf-8")
    assert "\\n" not in schema
    assert "alter table public.leads add column if not exists website text;" in schema
    migration = (ROOT / "supabase" / "migrations" / "20261117_add_leads_website.sql").read_text(encoding="utf-8")
    assert "add column if not exists website text" in migration
    assert "alter table public.leads add column if not exists consent_basis text;" in schema
    assert "alter table public.leads add column if not exists approved_to_contact boolean not null default false;" in schema
    assert "create table if not exists public.jarvis_proactive_state" in schema
    assert "create table if not exists public.jarvis_memory" in schema


def test_crm_tables_have_row_level_security_enabled():
    schema = (ROOT / "supabase" / "schema.sql").read_text(encoding="utf-8").lower()
    for table in ("leads", "tasks", "email_drafts", "jarvis_memory", "jarvis_proactive_state"):
        assert f"alter table public.{table} enable row level security;" in schema
