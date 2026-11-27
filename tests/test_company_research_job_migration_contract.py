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

    assert "SELECT plan(15)" in lifecycle
    assert "dblink_send_query" in concurrency
    assert "SELECT plan(14)" in concurrency
    assert "research_worker_a" in concurrency and "research_worker_b" in concurrency
    assert "pg_advisory_lock(742026, 2)" in concurrency
    assert "pg_advisory_lock(742026, 1)" in concurrency
    assert "v_waiting >= 2" in concurrency
    assert "global active-lease ceiling" in concurrency
    assert "daily budget lock" in concurrency


def test_postgres_worker_lifecycle_edge_suite_is_wired_into_ci():
    root = MIGRATION.parents[2]
    lifecycle_edges = (
        root / "supabase" / "tests" / "company_research_jobs_lifecycle_edges.test.sql"
    ).read_text(encoding="utf-8")
    workflow = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "SELECT plan(20)" in lifecycle_edges
    for expected in (
        "lease-owner-old",
        "lease-owner-new",
        "retry_wait",
        "dead_letter",
        "lease_expired",
        "budget_date = (now() AT TIME ZONE 'UTC')::date - 1",
    ):
        assert expected in lifecycle_edges
    assert "company_research_jobs_lifecycle_edges.test.sql" in workflow
    assert "grep -q '1..20' <<< \"$lifecycle_edges_output\"" in workflow


def test_worker_security_pg_tap_suite_is_wired_into_ci():
    root = MIGRATION.parents[2]
    security = (
        root / "supabase" / "tests" / "company_research_jobs_security.test.sql"
    ).read_text(encoding="utf-8")
    workflow = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "SELECT plan(12)" in security
    assert "has_table_privilege('anon'" in security
    assert "has_table_privilege('authenticated'" in security
    assert "has_function_privilege('service_role'" in security
    assert "company_research_snapshots" in security
    assert "public API roles cannot access snapshot history" in security
    assert "NOT has_table_privilege('service_role', 'public.company_research_job_audit', 'UPDATE')" in security
    assert "company_research_jobs_security.test.sql" in workflow
    assert "grep -q '1..12' <<< \"$security_output\"" in workflow



def test_daily_hard_budget_cap_is_persisted_and_enforced_at_settlement():
    root = MIGRATION.parents[2]
    hard_cap_migration = (
        root / "supabase" / "migrations"
        / "20261126170000_company_research_daily_hard_budget_cap.sql"
    ).read_text(encoding="utf-8")
    hard_cap_test = (
        root / "supabase" / "tests"
        / "company_research_daily_hard_budget_cap.test.sql"
    ).read_text(encoding="utf-8")
    workflow = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "ADD COLUMN IF NOT EXISTS daily_budget_microusd" in hard_cap_migration
    assert "pg_advisory_xact_lock(742026, 2)" in hard_cap_migration
    assert "v_other_reserved + p_actual_cost_microusd > v_effective_budget" in hard_cap_migration
    assert "SET reserved_cost_microusd = p_actual_cost_microusd" in hard_cap_migration
    assert "v_final_status := 'dead_letter'" in hard_cap_migration
    assert "actual_cost_missing" in hard_cap_migration
    assert "daily_budget_overrun" in hard_cap_migration
    assert "SELECT plan(8)" in hard_cap_test
    assert "research_daily_budget_exceeded" in hard_cap_test
    assert "company_research_daily_hard_budget_cap.test.sql" in workflow
    assert "grep -q '1..8' <<< \"$hard_budget_output\"" in workflow
