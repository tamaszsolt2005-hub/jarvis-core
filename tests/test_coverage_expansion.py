from __future__ import annotations

from types import SimpleNamespace

import pytest


class _FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []

    def select(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def execute(self):
        rows = self.rows
        for field, value in self.filters:
            rows = [row for row in rows if row.get(field) == value]
        return SimpleNamespace(data=rows)


class _FakeDB:
    def __init__(self, tables=None, rpc_data=None, rpc_error=None):
        self.tables = tables or {}
        self.rpc_data = rpc_data
        self.rpc_error = rpc_error
        self.rpc_calls = []

    def table(self, name):
        return _FakeQuery(self.tables.get(name, []))

    def rpc(self, name, payload):
        self.rpc_calls.append((name, payload))
        if self.rpc_error:
            raise self.rpc_error
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=self.rpc_data))


class _Column:
    def __init__(self):
        self.metrics = []

    def metric(self, *args, **kwargs):
        self.metrics.append((args, kwargs))

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _UI:
    def __init__(self):
        self.session_state = {}
        self.messages = []
        self.columns_created = []

    def __getattr__(self, name):
        if name in {
            "title", "caption", "info", "error", "warning", "success",
            "markdown", "write", "divider",
        }:
            return lambda *args, **kwargs: self.messages.append((name, args))
        raise AttributeError(name)

    def columns(self, spec, **_kwargs):
        count = spec if isinstance(spec, int) else len(spec)
        result = [_Column() for _ in range(count)]
        self.columns_created.append(result)
        return result

    def selectbox(self, _label, *, options, index=0, **_kwargs):
        return options[index]

    def expander(self, *_args, **_kwargs):
        return _Column()

    def dataframe(self, *_args, **_kwargs):
        self.messages.append(("dataframe", _args))

    def text_area(self, *_args, **_kwargs):
        return ""

    def text_input(self, *_args, **_kwargs):
        return ""

    def button(self, *_args, **_kwargs):
        return False

    def form(self, *_args, **_kwargs):
        return _Column()

    def form_submit_button(self, *_args, **_kwargs):
        return False

    def rerun(self):
        self.messages.append(("rerun", ()))


def test_email_helpers_reject_private_urls_and_malformed_addresses():
    from lead_email_dashboard import _email, _safe_public_source

    assert _safe_public_source("https://example.com/path") == "https://example.com/path"
    for value in (
        "javascript:alert(1)", "http://localhost/admin",
        "http://192.168.1.1/private", "https://user:pass@example.com",
        "https://host.local/path", "https://example.com:bad/path",
    ):
        assert _safe_public_source(value) is None
    assert _email("sales@example.com") is True
    for value in ("", "not-an-email", "a@@example.com", "x@example", "a b@example.com"):
        assert _email(value) is False


def test_email_source_facts_and_company_context_use_only_safe_grounded_facts():
    from lead_email_dashboard import _company_context, _source_facts

    snapshot = {
        "dossier": {
            "facts": [
                {"category": "Hiring", "fact": "Hiring operations staff", "source_url": "https://example.com/jobs"},
                {"category": "Private", "fact": "Do not include", "source_url": "http://127.0.0.1/admin"},
                "malformed",
                {"fact": "No source URL"},
            ],
            "decision_maker": {"role": "COO", "professional_background": "Operations"},
        }
    }
    facts = _source_facts(snapshot)
    assert len(facts) == 1
    assert facts[0]["category"] == "Hiring"
    context = _company_context(
        {"company_name": "Example Ltd", "website": "https://example.com", "notes": "Public notes"},
        snapshot,
    )
    assert "Example Ltd" in context
    assert "Hiring operations staff" in context
    assert "Do not include" not in context
    assert "COO" in context
    assert "nincs adat" in _company_context({"company_name": "No dossier"}, None)


def test_email_rows_and_rpc_event_are_bounded_and_explicit():
    from lead_email_dashboard import _rows, _rpc_event

    db = _FakeDB({"leads": [{"id": "lead-1"}, None, {"id": "lead-2"}]})
    assert _rows(db, "leads", "id") == [{"id": "lead-1"}, {"id": "lead-2"}]
    _rpc_event(db, "draft-1", "approved", "Reviewed", "other")
    assert db.rpc_calls == [(
        "record_lead_email_event",
        {
            "p_draft_id": "draft-1", "p_event_type": "approved",
            "p_note": "Reviewed", "p_feedback_category": "other",
        },
    )]


def test_crm_helpers_validate_database_shapes_and_record_only_explicit_events():
    from lead_customer_dashboard import _record, _rows

    with pytest.raises(RuntimeError, match="Unexpected leads response"):
        _rows(_FakeDB({"leads": [{"id": "ok"}, None]}), "leads", "id")
    db = _FakeDB(rpc_data={"ok": True})
    _record(db, p_lead_id="lead-1", p_event_type="interaction_logged")
    assert db.rpc_calls[0][0] == "record_lead_customer_lifecycle_event"
    assert db.rpc_calls[0][1]["p_event_type"] == "interaction_logged"


def test_crm_page_shows_empty_approved_lead_state(monkeypatch):
    import lead_customer_dashboard as crm

    ui = _UI()
    monkeypatch.setattr(crm, "st", ui)
    db = _FakeDB({
        "leads": [{"id": "lead-1", "company_name": "Example"}],
        "lead_review_states": [{"lead_id": "lead-1", "review_status": "pending"}],
        "lead_customer_lifecycle": [],
        "lead_customer_lifecycle_events": [],
    })
    crm.render_lead_customer_page(db, auth_enabled=True, role="reader")
    assert any(
        name == "info" and "Még nincs jóváhagyott lead" in args[0]
        for name, args in ui.messages
    )


def test_crm_page_renders_read_only_approved_pipeline_and_history(monkeypatch):
    import lead_customer_dashboard as crm

    ui = _UI()
    monkeypatch.setattr(crm, "st", ui)
    db = _FakeDB({
        "leads": [{"id": "lead-1", "company_name": "Example Ltd", "website": "https://example.com"}],
        "lead_review_states": [{"lead_id": "lead-1", "review_status": "approved"}],
        "lead_customer_lifecycle": [{
            "lead_id": "lead-1", "stage": "qualified", "next_action": "Discovery call",
            "next_action_due": "2026-12-01", "last_interaction_at": "2026-11-27",
        }],
        "lead_customer_lifecycle_events": [{
            "id": "event-1", "lead_id": "lead-1", "event_type": "interaction_logged",
            "channel": "meeting", "summary": "Discovery completed",
            "created_at": "2026-11-27T10:00:00Z", "to_stage": "qualified",
        }],
    })
    crm.render_lead_customer_page(db, auth_enabled=True, role="reader")
    rendered = " ".join(str(args) for _, args in ui.messages)
    assert "Example Ltd" in rendered
    assert "Discovery call" in rendered
    assert "Discovery completed" in rendered
    assert "Olvasási jogosultságod van" in rendered
    assert db.rpc_calls == []


def test_research_ops_rpc_helpers_validate_payloads_and_wrap_errors():
    from company_research_ops_dashboard import (
        _rpc_payload, load_worker_control_state, set_worker_paused,
    )

    assert _rpc_payload(SimpleNamespace(data={"paused": True}), operation="state") == {"paused": True}
    assert _rpc_payload(SimpleNamespace(data=[{"paused": False}]), operation="state") == {"paused": False}
    with pytest.raises(RuntimeError, match="unexpected response shape"):
        _rpc_payload(SimpleNamespace(data=[]), operation="state")
    with pytest.raises(ValueError, match="authenticated Supabase"):
        load_worker_control_state(None)
    with pytest.raises(RuntimeError, match="Could not load"):
        load_worker_control_state(_FakeDB(rpc_error=OSError("private detail")))
    db = _FakeDB(rpc_data={"paused": True})
    assert set_worker_paused(db, paused=True, note="  maintenance  ") == {"paused": True}
    assert db.rpc_calls[0][1] == {"p_paused": True, "p_note": "maintenance"}
    with pytest.raises(ValueError, match="paused must be boolean"):
        set_worker_paused(db, paused=1, note="valid note")
    with pytest.raises(ValueError, match="5–500"):
        set_worker_paused(db, paused=False, note="no")


def test_research_ops_page_denies_unauthenticated_access(monkeypatch):
    import company_research_ops_dashboard as ops

    ui = _UI()
    monkeypatch.setattr(ops, "st", ui)
    ops.render_company_research_ops_page(_FakeDB(), auth_enabled=False, role="admin")
    assert any(name == "error" for name, _ in ui.messages)


def test_research_ops_page_fails_closed_on_incomplete_control_state(monkeypatch):
    import company_research_ops_dashboard as ops

    ui = _UI()
    monkeypatch.setattr(ops, "st", ui)
    ops.render_company_research_ops_page(
        _FakeDB(rpc_data={"paused": False}), auth_enabled=True, role="reader"
    )
    assert any(
        name == "error" and "állapota hiányos" in args[0]
        for name, args in ui.messages
    )


def test_research_ops_page_renders_reader_state_without_mutation(monkeypatch):
    import company_research_ops_dashboard as ops

    ui = _UI()
    monkeypatch.setattr(ops, "st", ui)
    state = {
        "paused": True, "updated_at": "2026-11-27T10:00:00Z",
        "note": "Maintenance", "counts": {"queued": 2, "running": 1},
        "budget_today": {
            "reserved_microusd": 100000, "committed_microusd": 150000,
            "actual_microusd": 90000, "jobs_today": 3,
            "limit_microusd": 120000, "over_budget": True,
        },
        "recent_jobs": [], "recent_events": [], "recent_job_events": [],
    }
    db = _FakeDB(rpc_data=state)
    ops.render_company_research_ops_page(db, auth_enabled=True, role="reader")
    assert any(name == "warning" for name, _ in ui.messages)
    assert any(name == "error" for name, _ in ui.messages)
    assert any(name == "info" and "Olvasási mód" in args[0] for name, args in ui.messages)
    assert db.rpc_calls == [("company_research_worker_control_state", {})]


def test_lead_review_assessment_and_context_edge_cases():
    from lead_review_dashboard import (
        _company_context, _load_rows, _safe_source_url, _score_snapshot_assessment,
    )

    assert _safe_source_url("https://example.com/a") == "https://example.com/a"
    assert _safe_source_url("http://[::1]/private") is None
    assert _safe_source_url("https://example.com:bad") is None
    assert _score_snapshot_assessment({"lead_fit_assessment": {"status": "insufficient_evidence"}})["scored"] is False
    assert _score_snapshot_assessment({"lead_fit_assessment": {
        "assessment_version": "1.0", "status": "assessed", "fit_score": 80,
        "confidence": 0.8, "evidence": [{"claim": "Fact", "source_url": "https://example.com"}],
    }})["scored"] is True
    assert _score_snapshot_assessment({"lead_fit_assessment": {
        "assessment_version": "1.0", "status": "assessed", "fit_score": 80,
        "confidence": 1.5, "evidence": [{"claim": "Fact", "source_url": "https://example.com"}],
    }})["status"] == "invalid_assessment"
    context = _company_context({"company_name": "No facts"}, {"facts": "invalid"})
    assert "nincs mentett forrásolt tény" in context
    assert _load_rows(_FakeDB({"leads": [{"id": "1"}, "bad"]}), "leads", "id") == [{"id": "1"}]
