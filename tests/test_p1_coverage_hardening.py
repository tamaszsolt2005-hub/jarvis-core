from __future__ import annotations

import math
from types import SimpleNamespace

import pytest


def test_lead_fit_assessment_accepts_only_grounded_and_deduplicated_evidence():
    from lead_fit_assessment import validate_lead_fit_assessment

    raw = {
        "assessment_version": "1.0",
        "fit_score": 82,
        "confidence": 0.75,
        "rationale": "Strong public business fit.",
        "fit_signals": ["B2B SaaS", "  workflow automation  ", 42],
        "risk_signals": ["Limited evidence"],
        "recommended_next_step": "Validate current demand.",
        "evidence": [
            {"source_url": "https://EXAMPLE.com:443/about#team", "claim": "B2B provider", "evidence_type": "fact"},
            {"source_url": "https://example.com/about", "claim": "b2b provider", "evidence_type": "fact"},
            {"source_url": "https://attacker.invalid/fake", "claim": "Forged claim", "evidence_type": "fact"},
            {"source_url": "https://example.com/about", "claim": "Potential pain", "evidence_type": "hypothesis"},
            {"source_url": "https://example.com/about", "claim": "Unsupported type", "evidence_type": "rumour"},
        ],
    }
    sources = [{
        "source_url": "https://example.com/about",
        "title": "Company about",
        "snippet": "Public B2B software provider",
    }]
    result = validate_lead_fit_assessment(raw, sources)
    assert result["status"] == "assessed"
    assert result["fit_score"] == 82
    assert result["fit_signals"] == ["B2B SaaS", "workflow automation"]
    assert len(result["evidence"]) == 2
    assert result["evidence"][0]["title"] == "Company about"
    assert result["evidence"][0]["snippet"] == "Public B2B software provider"


def test_lead_fit_assessment_returns_unscored_when_no_grounded_evidence():
    from lead_fit_assessment import validate_lead_fit_assessment

    raw = {
        "assessment_version": "1.0", "fit_score": None, "confidence": None,
        "rationale": "No verified sources.", "fit_signals": ["unverified"],
        "risk_signals": [], "recommended_next_step": "Collect sources.",
        "evidence": [{"source_url": "https://fake.example", "claim": "Claim", "evidence_type": "fact"}],
    }
    result = validate_lead_fit_assessment(raw, [])
    assert result["status"] == "insufficient_evidence"
    assert result["fit_score"] is None
    assert result["confidence"] is None
    assert result["fit_signals"] == []


@pytest.mark.parametrize("raw, sources, message", [
    (None, [], "unsupported_assessment_version"),
    ({"assessment_version": "2.0"}, [], "unsupported_assessment_version"),
    ({"assessment_version": "1.0", "evidence": "not-a-list"}, [], "invalid_assessment_evidence"),
    ({
        "assessment_version": "1.0", "evidence": [], "rationale": "",
        "recommended_next_step": "Next", "fit_signals": [], "risk_signals": [],
    }, [], "invalid_assessment_narrative"),
])
def test_lead_fit_assessment_rejects_invalid_contract(raw, sources, message):
    from lead_fit_assessment import validate_lead_fit_assessment

    with pytest.raises(ValueError, match=message):
        validate_lead_fit_assessment(raw, sources)


@pytest.mark.parametrize("field, value", [
    ("fit_score", True), ("fit_score", math.nan), ("fit_score", 101),
    ("confidence", False), ("confidence", math.inf), ("confidence", -0.1),
])
def test_lead_fit_assessment_rejects_invalid_numeric_ranges(field, value):
    from lead_fit_assessment import validate_lead_fit_assessment

    raw = {
        "assessment_version": "1.0", "fit_score": 80, "confidence": 0.8,
        "rationale": "Evidence-backed rationale.", "fit_signals": [],
        "risk_signals": [], "recommended_next_step": "Verify.",
        "evidence": [{"source_url": "https://example.com", "claim": "Fact", "evidence_type": "fact"}],
    }
    raw[field] = value
    with pytest.raises(ValueError, match=f"invalid_assessment_{field}"):
        validate_lead_fit_assessment(raw, [{"source_url": "https://example.com"}])


def test_lead_fit_assessment_rejects_malformed_source_urls_and_list_shapes():
    from lead_fit_assessment import validate_lead_fit_assessment

    raw = {
        "assessment_version": "1.0", "fit_score": 80, "confidence": 0.8,
        "rationale": "Evidence-backed rationale.", "fit_signals": "not-a-list",
        "risk_signals": [], "recommended_next_step": "Verify.",
        "evidence": [{"source_url": "https://example.com", "claim": "Fact", "evidence_type": "fact"}],
    }
    with pytest.raises(ValueError, match="invalid_assessment_fit_signals"):
        validate_lead_fit_assessment(raw, [{"source_url": "https://example.com"}])
    raw["fit_signals"] = []
    raw["evidence"] = [{"source_url": "https://user:pass@example.com", "claim": "Fact", "evidence_type": "fact"}]
    result = validate_lead_fit_assessment(raw, [{"source_url": "https://user:pass@example.com"}])
    assert result["status"] == "insufficient_evidence"


class _Query:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []
        self.orders = []

    def select(self, *_args):
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def order(self, field, desc=False):
        self.orders.append((field, desc))
        return self

    def limit(self, _value):
        return self

    def execute(self):
        rows = self.rows
        for field, value in self.filters:
            rows = [row for row in rows if row.get(field) == value]
        return SimpleNamespace(data=rows)


class _ReadDB:
    def __init__(self, tables):
        self.tables = tables
        self.rpc_calls = []

    def table(self, name):
        return _Query(self.tables.get(name, []))

    def rpc(self, name, params):
        self.rpc_calls.append((name, params))
        return SimpleNamespace(execute=lambda: SimpleNamespace(data={
            "recent_jobs": [
                {"lead_id": "lead-1", "status": "queued"},
                {"lead_id": "lead-1", "status": "running"},
                {"lead_id": "lead-2", "status": "succeeded"},
            ]
        }))


def test_lead_review_snapshot_assessment_scoring_and_fail_closed_paths():
    from lead_review_dashboard import _score_snapshot_assessment

    valid = {
        "lead_fit_assessment": {
            "assessment_version": "1.0", "status": "assessed",
            "fit_score": 80, "confidence": 0.8,
            "evidence": [
                {"claim": "Grounded fact", "source_url": "https://example.com/about"},
                {"claim": "Another fact", "source_url": "https://example.com/team"},
            ],
        }
    }
    scored = _score_snapshot_assessment(valid)
    assert scored["scored"] is True
    assert scored["evidence_count"] == 2
    assert scored["interpretation"].startswith("Kutatási prioritás")
    assert _score_snapshot_assessment({})["status"] == "missing_assessment"
    assert _score_snapshot_assessment({"lead_fit_assessment": {"status": "insufficient_evidence"}})["priority_score"] is None
    invalid = {"lead_fit_assessment": {**valid["lead_fit_assessment"], "fit_score": True}}
    assert _score_snapshot_assessment(invalid)["status"] == "invalid_assessment"
    invalid_url = {"lead_fit_assessment": {
        **valid["lead_fit_assessment"],
        "evidence": [{"claim": "Private host", "source_url": "http://127.0.0.1/admin"}],
    }}
    assert _score_snapshot_assessment(invalid_url)["scored"] is False


@pytest.mark.parametrize("url", [
    "javascript:alert(1)", "https://user:pw@example.com", "http://localhost/admin",
    "http://192.168.1.1/private", "https://example.com:bad/path", "https://host.internal/path",
])
def test_lead_review_rejects_unsafe_source_urls(url):
    from lead_review_dashboard import _safe_source_url

    assert _safe_source_url(url) is None


def test_lead_review_loads_latest_snapshot_jobs_and_records_audit_events():
    from lead_review_dashboard import (
        _company_context, _latest_research_jobs, _latest_snapshot_dossiers,
        _record_event,
    )

    db = _ReadDB({
        "company_research_snapshots": [
            {"lead_id": "lead-1", "researched_at": "2026-11-27", "dossier": {"facts": [{"fact": "New"}]}},
            {"lead_id": "lead-1", "researched_at": "2026-11-26", "dossier": {"facts": [{"fact": "Old"}]}},
            {"lead_id": "lead-2", "researched_at": "2026-11-27", "dossier": "invalid"},
        ]
    })
    snapshots = _latest_snapshot_dossiers(db)
    assert snapshots["lead-1"]["facts"][0]["fact"] == "New"
    jobs = _latest_research_jobs(db)
    assert jobs["lead-1"]["status"] == "running"
    assert jobs["lead-2"]["status"] == "succeeded"
    _record_event(db, lead_id="lead-1", event_type="approved", note="Reviewed")
    assert db.rpc_calls[-1][0] == "record_lead_review_event"
    context = _company_context(
        {"company_name": "Example Ltd", "website": "https://example.com", "notes": "Cégprofil: SaaS"},
        {"facts": [{"category": "model", "fact": "B2B platform", "source_url": "https://example.com"}],
         "decision_maker": {"name": "Public Person", "role": "CEO"}},
    )
    assert "Example Ltd" in context
    assert "B2B platform" in context
    assert "Public Person" in context


def test_lead_review_rejects_invalid_snapshot_and_job_rpc_shapes():
    from lead_review_dashboard import _latest_research_jobs, _latest_snapshot_dossiers

    class BadDB:
        def table(self, _name):
            return SimpleNamespace(
                select=lambda *_: SimpleNamespace(
                    order=lambda *_args, **_kwargs: SimpleNamespace(
                        order=lambda *_a, **_k: SimpleNamespace(
                            limit=lambda *_a: SimpleNamespace(
                                execute=lambda: SimpleNamespace(data="bad")
                            )
                        )
                    )
                )
            )
        def rpc(self, *_args):
            return SimpleNamespace(execute=lambda: SimpleNamespace(data=[]))

    with pytest.raises(RuntimeError, match="Invalid company research snapshot"):
        _latest_snapshot_dossiers(BadDB())
    with pytest.raises(RuntimeError, match="invalid job projection"):
        _latest_research_jobs(BadDB())
    with pytest.raises(RuntimeError, match="unavailable"):
        _latest_research_jobs(None)


def test_lead_review_page_handles_empty_lead_table_without_claiming_db_error(monkeypatch):
    import lead_review_dashboard as page

    messages = []
    class UI:
        def markdown(self, *_args, **_kwargs): pass
        def title(self, value): messages.append(("title", value))
        def caption(self, value): messages.append(("caption", value))
        def info(self, value): messages.append(("info", value))
    monkeypatch.setattr(page, "st", UI())
    page.render_lead_review_page(
        _ReadDB({"leads": []}), auth_enabled=True, role="reader",
        generate_text_fn=None, model_name_fn=None,
    )
    assert any(kind == "info" and "Még nincs megjeleníthető lead" in value for kind, value in messages)


class _ActionQuery:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []

    def select(self, *_args):
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, _value):
        return self

    def execute(self):
        rows = self.rows
        for field, value in self.filters:
            rows = [row for row in rows if row.get(field) == value]
        return SimpleNamespace(data=rows)


class _ActionDB:
    def __init__(self, lead_rows, job_rows):
        self.lead_rows = lead_rows
        self.job_rows = job_rows

    def table(self, name):
        return _ActionQuery(self.lead_rows if name == "leads" else self.job_rows)


def test_lead_research_actions_validate_id_and_authorize_before_service_client():
    from lead_research_actions import LeadResearchRequestError, enqueue_single_lead_research

    factory_calls = []
    with pytest.raises(LeadResearchRequestError, match="invalid_lead_id"):
        enqueue_single_lead_research(
            " " * 2, auth_session=None, authorize_user=lambda _: True,
            service_client_factory=lambda: factory_calls.append(True),
        )
    with pytest.raises(LeadResearchRequestError, match="invalid_lead_id"):
        enqueue_single_lead_research(
            "x" * 65, auth_session=None, authorize_user=lambda _: True,
            service_client_factory=lambda: factory_calls.append(True),
        )
    with pytest.raises(PermissionError, match="research_manage_permission_required"):
        enqueue_single_lead_research(
            "lead-1", auth_session=None, authorize_user=lambda _: None,
            service_client_factory=lambda: factory_calls.append(True),
        )
    assert factory_calls == []


def test_lead_research_actions_returns_existing_active_job_without_new_provider_config(monkeypatch):
    import lead_research_actions as actions

    db = _ActionDB(
        [{"id": "lead-1", "company_name": "Example Ltd"}],
        [{"operation_id": "op-existing", "status": "running", "created_at": "2026-11-27T10:00:00Z"}],
    )
    monkeypatch.setattr(
        actions.CompanyResearchRuntimeConfig, "from_env",
        classmethod(lambda cls: (_ for _ in ()).throw(AssertionError("active jobs do not need new pricing config"))),
    )
    result = actions.enqueue_single_lead_research(
        "lead-1", auth_session={"token": "fresh"},
        authorize_user=lambda session: {"role": "admin"} if session else None,
        service_client_factory=lambda: db,
    )
    assert result["status"] == "running"
    assert result["operation_id"] == "op-existing"
    assert result["reason"] == "existing_research_job"


def test_lead_research_actions_fails_closed_when_lead_or_job_projection_is_invalid():
    from lead_research_actions import LeadResearchRequestError, enqueue_single_lead_research

    with pytest.raises(LeadResearchRequestError, match="lead_not_found"):
        enqueue_single_lead_research(
            "lead-1", auth_session={}, authorize_user=lambda _: True,
            service_client_factory=lambda: _ActionDB([], []),
        )
    db = _ActionDB([{"id": "lead-1", "company_name": "Example Ltd"}], [{"operation_id": None, "status": "queued"}])
    with pytest.raises(LeadResearchRequestError, match="latest_job_state_invalid"):
        enqueue_single_lead_research(
            "lead-1", auth_session={}, authorize_user=lambda _: True,
            service_client_factory=lambda: db,
        )


def test_company_research_worker_cli_paused_path_does_not_initialize_gemini(monkeypatch):
    import company_research_config as config_module
    import jarvis_common
    import company_research_worker_cli as cli

    class Config:
        @classmethod
        def from_env(cls): return cls()
        def validate_model(self, model): assert model == "gemini-test"

    class DB:
        def table(self, _name):
            return self
        def select(self, *_args): return self
        def eq(self, *_args): return self
        def limit(self, *_args): return self
        def execute(self): return SimpleNamespace(data=[{"paused": True}])

    monkeypatch.setattr(config_module, "CompanyResearchRuntimeConfig", Config)
    monkeypatch.setattr(jarvis_common, "get_model_name", lambda: "gemini-test")
    monkeypatch.setattr(jarvis_common, "get_service_supabase", lambda: DB())
    monkeypatch.setattr(
        jarvis_common, "get_gemini_client",
        lambda: (_ for _ in ()).throw(AssertionError("paused worker must not initialize Gemini")),
    )
    assert cli.run_once() == {"status": "paused"}


def test_company_research_worker_cli_fails_closed_on_missing_control(monkeypatch):
    import company_research_config as config_module
    import jarvis_common
    import company_research_worker_cli as cli

    class Config:
        @classmethod
        def from_env(cls): return cls()
        def validate_model(self, _model): pass

    class DB:
        def table(self, _name): return self
        def select(self, *_args): return self
        def eq(self, *_args): return self
        def limit(self, *_args): return self
        def execute(self): return SimpleNamespace(data=[])

    monkeypatch.setattr(config_module, "CompanyResearchRuntimeConfig", Config)
    monkeypatch.setattr(jarvis_common, "get_model_name", lambda: "gemini-test")
    monkeypatch.setattr(jarvis_common, "get_service_supabase", lambda: DB())
    with pytest.raises(RuntimeError, match="research_runtime_control_unavailable"):
        cli.run_once()


def test_company_research_worker_cli_main_prints_only_safe_error_type(monkeypatch, capsys):
    import company_research_worker_cli as cli

    monkeypatch.setattr(cli, "run_once", lambda: (_ for _ in ()).throw(RuntimeError("secret details")))
    assert cli.main() == 1
    output = capsys.readouterr().out
    assert '"error_type": "RuntimeError"' in output
    assert "secret details" not in output
