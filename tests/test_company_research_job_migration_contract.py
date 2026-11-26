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



def test_hourly_and_per_domain_quotas_are_checked_atomically_before_insert():
    sql = MIGRATION.read_text(encoding="utf-8")
    create_fn = sql.split("CREATE OR REPLACE FUNCTION public.company_research_job_create", 1)[1]
    create_fn = create_fn.split("\n$$;", 1)[0]
    assert "pg_advisory_xact_lock(742026, 2)" in create_fn
    assert "research_hourly_limit_exceeded" in create_fn
    assert "research_domain_daily_limit_exceeded" in create_fn
    assert "created_at >= v_hour_start" in create_fn
    assert "created_at >= v_day_start" in create_fn
    assert create_fn.index("SELECT * INTO v_existing") < create_fn.index("research_hourly_limit_exceeded")
    assert create_fn.index("research_domain_daily_limit_exceeded") < create_fn.index("INSERT INTO public.company_research_jobs")
    assert "lower(COALESCE(payload->>'company_domain', '')) = v_domain" in create_fn
    assert "GRANT EXECUTE ON FUNCTION public.company_research_job_create(jsonb, bigint, bigint, integer, integer) TO service_role" in sql



def test_actual_cost_settlement_is_atomic_with_job_completion():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "actual_cost_microusd bigint CHECK" in sql
    assert "reservation_status IN ('reserved', 'settled')" in sql
    complete_fn = sql.split("CREATE OR REPLACE FUNCTION public.company_research_job_complete", 1)[1]
    complete_fn = complete_fn.split("\n$$;", 1)[0]
    assert "p_actual_cost_microusd bigint DEFAULT NULL" in complete_fn
    assert "SET reserved_cost_microusd = p_actual_cost_microusd" in complete_fn
    assert "reservation_status = 'settled'" in complete_fn
    assert "research_budget_reservation_missing_or_settled" in complete_fn
    assert "'actual_cost_microusd', p_actual_cost_microusd" in complete_fn
    assert "GRANT SELECT, INSERT, UPDATE ON TABLE public.company_research_budget_reservations TO service_role" in sql
    assert "GRANT EXECUTE ON FUNCTION public.company_research_job_complete(text, text, jsonb, bigint) TO service_role" in sql


def test_postgres_worker_integration_suites_cover_quota_lifecycle_and_races():
    root = MIGRATION.parents[2]
    lifecycle = (root / "supabase" / "tests" / "company_research_jobs.test.sql").read_text(encoding="utf-8")
    concurrency = (root / "supabase" / "tests" / "company_research_jobs_concurrency.test.sql").read_text(encoding="utf-8")

    for expected in (
        "research_daily_budget_exceeded",
        "research_hourly_limit_exceeded",
        "research_domain_daily_limit_exceeded",
        "company_research_job_heartbeat",
        "company_research_job_complete",
        "reservation_status = 'settled'",
    ):
        assert expected in lifecycle

    assert "dblink_send_query" in concurrency
    assert "research_worker_a" in concurrency and "research_worker_b" in concurrency
    assert "global active-lease ceiling" in concurrency
    assert "daily budget lock" in concurrency
