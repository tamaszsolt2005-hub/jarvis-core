from copy import deepcopy
from types import SimpleNamespace

import pytest

from company_research_config import CompanyResearchRuntimeConfig
from company_research_refresh_job import (
    load_company_research_refresh_inputs,
    run_company_research_refresh_cycle,
)


class Query:
    def __init__(self, db, table):
        self.db = db
        self.table_name = table
        self.filters = []
        self.orders = []
        self.bounds = (0, 999)

    def select(self, _columns):
        return self

    def order(self, field, desc=False):
        self.orders.append((field, desc))
        return self

    def in_(self, field, values):
        self.filters.append((field, set(values)))
        return self

    def range(self, start, end):
        self.bounds = (start, end)
        return self

    def eq(self, field, value):
        self.filters.append((field, {value}))
        return self

    def limit(self, value):
        self.bounds = (self.bounds[0], min(self.bounds[1], self.bounds[0] + value - 1))
        return self

    def execute(self):
        rows = deepcopy(self.db.tables[self.table_name])
        for field, values in self.filters:
            rows = [row for row in rows if row.get(field) in values]
        for field, desc in reversed(self.orders):
            rows.sort(key=lambda row: row.get(field) or "", reverse=desc)
        start, end = self.bounds
        return SimpleNamespace(data=rows[start:end + 1])


class FakeDB:
    def __init__(self):
        self.tables = {
            "leads": [
                {"id": "lead-a", "company_name": "Alpha"},
                {"id": "lead-b", "company_name": "Beta"},
                {"id": "lead-c", "company_name": "Gamma"},
            ],
            "company_research_runtime_control": [
                {"singleton": True, "paused": False, "note": "Initial operating state"}
            ],
            "company_research_snapshots": [
                {"lead_id": "lead-a", "snapshot_id": "a1", "researched_at": "2026-01-01", "dossier": {"version": 1}},
                {"lead_id": "lead-a", "snapshot_id": "a2", "researched_at": "2026-02-01", "dossier": {"version": 2}},
                {"lead_id": "lead-b", "snapshot_id": "b1", "researched_at": "2026-01-15", "dossier": {"version": 1}},
            ],
        }

    def table(self, name):
        return Query(self, name)


def test_loader_paginates_leads_and_selects_newest_snapshot_per_lead():
    leads, latest = load_company_research_refresh_inputs(
        FakeDB(), lead_page_size=2, snapshot_page_size=1, lead_chunk_size=1
    )
    assert [lead["id"] for lead in leads] == ["lead-a", "lead-b", "lead-c"]
    assert latest["lead-a"]["snapshot_id"] == "a2"
    assert latest["lead-b"]["snapshot_id"] == "b1"
    assert "lead-c" not in latest


@pytest.mark.parametrize("kwargs", [
    {"lead_page_size": 0},
    {"snapshot_page_size": 1001},
    {"lead_chunk_size": True},
])
def test_loader_validates_pagination_limits(kwargs):
    with pytest.raises(ValueError):
        load_company_research_refresh_inputs(FakeDB(), **kwargs)


def test_loader_fails_closed_on_unexpected_database_shape():
    class BadDB:
        def table(self, _name):
            return self

        def select(self, _columns):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def range(self, *_args):
            return self

        def execute(self):
            return SimpleNamespace(data=None)

    with pytest.raises(RuntimeError, match="Unexpected database response"):
        load_company_research_refresh_inputs(BadDB())


def _runtime_config():
    return CompanyResearchRuntimeConfig(
        input_price_microusd_per_million_tokens=1_000_000,
        output_price_microusd_per_million_tokens=1_000_000,
        pricing_model="gemini-test",
        search_price_microusd_per_thousand_queries=0,
        max_daily_cost_microusd=100_000,
        max_jobs_per_hour=10,
        max_jobs_per_domain_per_day=2,
        max_concurrent_jobs=1,
    )


def test_refresh_cycle_rejects_model_pricing_mismatch_before_database_access():
    with pytest.raises(ValueError, match="does not match"):
        run_company_research_refresh_cycle(
            object(), client=object(), model="different-model", config=_runtime_config()
        )


def test_refresh_cycle_rejects_unbounded_client_before_database_access():
    client = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **_: None))
    with pytest.raises(ValueError, match="token counting"):
        run_company_research_refresh_cycle(
            object(), client=client, model="gemini-test", config=_runtime_config()
        )


def test_refresh_cycle_does_not_enqueue_or_call_provider_when_paused():
    db = FakeDB()
    db.tables["company_research_runtime_control"][0]["paused"] = True
    db.tables["company_research_runtime_control"][0]["note"] = "Scheduled maintenance"
    result = run_company_research_refresh_cycle(
        db,
        client=SimpleNamespace(models=SimpleNamespace(count_tokens=lambda **_: 1, generate_content=lambda **_: None)),
        model="gemini-test", config=_runtime_config()
    )
    assert result["status"] == "paused"
    assert result["queued"] == 0
    assert result["processed"] == 0
    assert result["pause_note"] == "Scheduled maintenance"


def test_refresh_cycle_requires_exactly_one_runtime_control_row():
    db = FakeDB()
    db.tables["company_research_runtime_control"] = []
    client = SimpleNamespace(models=SimpleNamespace(
        count_tokens=lambda **_: 1, generate_content=lambda **_: None
    ))
    with pytest.raises(RuntimeError, match="control state is missing"):
        run_company_research_refresh_cycle(
            db, client=client, model="gemini-test", config=_runtime_config()
        )


def test_refresh_cycle_enqueues_and_processes_only_until_idle(monkeypatch):
    import company_research_refresh_job as refresh

    db = FakeDB()
    client = SimpleNamespace(models=SimpleNamespace(
        count_tokens=lambda **_: 1, generate_content=lambda **_: None
    ))
    monkeypatch.setattr(refresh, "_repository", lambda database: database)
    monkeypatch.setattr(
        refresh, "enqueue_company_research_refreshes_with_config",
        lambda repository, leads, snapshots, *, config: [{"id": "job-1"}, {"id": "job-2"}],
    )
    outcomes = iter([
        {"status": "succeeded"},
        {"status": "retry_wait"},
        {"status": "idle"},
    ])
    calls = []

    def run_worker(repository, **kwargs):
        calls.append((repository, kwargs))
        return next(outcomes)

    monkeypatch.setattr(refresh, "run_company_research_worker_with_config", run_worker)
    result = run_company_research_refresh_cycle(
        db, client=client, model="gemini-test", config=_runtime_config(),
        worker_id="test-worker",
    )
    assert result["scanned_leads"] == 3
    assert result["queued"] == 2
    assert result["processed"] == 2
    assert result["worker_outcomes"] == {"succeeded": 1, "retry_wait": 1}
    assert result["contact_permission"] == "unchanged"
    assert result["outreach"] == "disabled"
    assert len(calls) == 3
    assert all(call[1]["worker_id"] == "test-worker" for call in calls)


def test_refresh_cycle_uses_generated_worker_identity_when_not_supplied(monkeypatch):
    import company_research_refresh_job as refresh

    db = FakeDB()
    client = SimpleNamespace(models=SimpleNamespace(
        count_tokens=lambda **_: 1, generate_content=lambda **_: None
    ))
    monkeypatch.setattr(refresh, "_repository", lambda database: database)
    monkeypatch.setattr(refresh, "enqueue_company_research_refreshes_with_config", lambda *a, **k: [])
    seen = []

    def run_worker(_repository, **kwargs):
        seen.append(kwargs["worker_id"])
        return {"status": "idle"}

    monkeypatch.setattr(refresh, "run_company_research_worker_with_config", run_worker)
    run_company_research_refresh_cycle(
        db, client=client, model="gemini-test", config=_runtime_config()
    )
    assert len(seen) == 1
    assert seen[0].startswith("company-research-")


def test_refresh_cycle_rejects_malformed_runtime_control_response():
    db = FakeDB()
    db.tables["company_research_runtime_control"] = [{"singleton": True, "paused": False}, "bad"]
    client = SimpleNamespace(models=SimpleNamespace(
        count_tokens=lambda **_: 1, generate_content=lambda **_: None
    ))
    with pytest.raises(RuntimeError, match="Unexpected database response"):
        run_company_research_refresh_cycle(
            db, client=client, model="gemini-test", config=_runtime_config()
        )
