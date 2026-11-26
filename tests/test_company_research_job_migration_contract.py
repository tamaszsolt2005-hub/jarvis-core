from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase"
    / "migrations"
    / "20261126153000_company_research_jobs.sql"
)


def test_job_migration_keeps_worker_and_audit_tables_private():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "ALTER TABLE public.company_research_jobs ENABLE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE public.company_research_budget_reservations ENABLE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE public.company_research_job_audit ENABLE ROW LEVEL SECURITY" in sql
    assert "REVOKE ALL ON TABLE public.company_research_job_audit FROM PUBLIC, anon, authenticated" in sql
    assert "GRANT SELECT, INSERT ON TABLE public.company_research_job_audit TO service_role" in sql
    assert "SECURITY DEFINER" not in sql


def test_daily_budget_is_reserved_inside_the_job_create_transaction():
    sql = MIGRATION.read_text(encoding="utf-8")
    create_fn = sql.split("CREATE OR REPLACE FUNCTION public.company_research_job_create", 1)[1]
    create_fn = create_fn.split("\n$$;", 1)[0]
    assert "pg_advisory_xact_lock(742026, 2)" in create_fn
    assert "research_daily_budget_exceeded" in create_fn
    assert "INSERT INTO public.company_research_jobs" in create_fn
    assert "INSERT INTO public.company_research_budget_reservations" in create_fn
    assert "INSERT INTO public.company_research_job_audit" in create_fn


def test_worker_lifecycle_transitions_write_append_only_audit_events():
    sql = MIGRATION.read_text(encoding="utf-8")
    for event in ("'claimed'", "'heartbeat'", "'succeeded'", "'retry_scheduled'", "'dead_letter'"):
        assert event in sql
    assert "company_research_job_audit_list" in sql
    assert "REVOKE ALL ON FUNCTION public.company_research_job_audit_list(text, integer) FROM PUBLIC, anon, authenticated" in sql
    assert "GRANT EXECUTE ON FUNCTION public.company_research_job_audit_list(text, integer) TO service_role" in sql
