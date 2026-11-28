from types import SimpleNamespace

import pytest

from company_research_ops_dashboard import (
    load_worker_control_state,
    set_worker_paused,
    _nonnegative_int,
)


class FakeRPC:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=self.response))


def test_load_worker_control_state_uses_authenticated_rpc_payload():
    db = FakeRPC({"paused": True, "counts": {"queued": 3}})
    assert load_worker_control_state(db)["paused"] is True
    assert db.calls == [("company_research_worker_control_state", {})]


def test_set_worker_paused_requires_reason_and_uses_guarded_rpc():
    db = FakeRPC({"paused": True})
    with pytest.raises(ValueError, match="reason"):
        set_worker_paused(db, paused=True, note="no")
    result = set_worker_paused(db, paused=True, note="Scheduled maintenance")
    assert result["paused"] is True
    assert db.calls == [(
        "company_research_worker_set_paused",
        {"p_paused": True, "p_note": "Scheduled maintenance"},
    )]


def test_ops_dashboard_rpc_fails_closed_on_unexpected_shape():
    db = FakeRPC([])
    with pytest.raises(RuntimeError, match="unexpected response"):
        load_worker_control_state(db)


class FakeColumn:
    def __init__(self, ui):
        self.ui = ui

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def metric(self, label, value):
        self.ui.metrics.append((label, value))


class FakeUI:
    def __init__(self, clicked=None):
        self.clicked = set(clicked or [])
        self.metrics = []
        self.messages = []
        self.tables = []

    def __getattr__(self, name):
        if name in {"title", "caption", "error", "warning", "success", "info", "markdown", "write"}:
            return lambda *args, **kwargs: self.messages.append((name, args))
        if name == "columns":
            return lambda count: [FakeColumn(self) for _ in range(count)]
        if name == "text_area":
            return lambda *args, **kwargs: "Planned maintenance"
        if name == "button":
            return lambda *args, **kwargs: kwargs.get("key") in self.clicked
        if name == "dataframe":
            return lambda frame, **kwargs: self.tables.append(frame)
        if name == "rerun":
            return lambda: None
        raise AttributeError(name)


class RenderDB(FakeRPC):
    def __init__(self, state, update_result=None):
        super().__init__(state)
        self.update_result = update_result or {"paused": True}

    def rpc(self, name, params):
        self.calls.append((name, params))
        payload = self.response if name == "company_research_worker_control_state" else self.update_result
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=payload))


def _ops_state(paused=False):
    return {
        "paused": paused,
        "updated_at": "2026-11-27T20:00:00+00:00",
        "note": "Scheduled maintenance" if paused else "Initial operating state",
        "counts": {"queued": 2, "running": 1, "retry_wait": 1, "succeeded": 8, "dead_letter": 0},
        "budget_today": {"reserved_microusd": 1500000, "actual_microusd": 900000, "jobs_today": 4},
        "recent_jobs": [{"operation_id": "job-00000001", "status": "queued"}],
        "recent_events": [{"event_id": 1, "paused": paused, "note": "maintenance"}],
    }


def test_render_worker_ops_page_is_read_only_for_reader(monkeypatch):
    import company_research_ops_dashboard as page

    ui = FakeUI()
    monkeypatch.setattr(page, "st", ui)
    db = RenderDB(_ops_state(paused=True))
    page.render_company_research_ops_page(db, auth_enabled=True, role="reader")
    assert len(ui.metrics) == 5
    assert any("Olvasási mód" in args[0] for name, args in ui.messages if name == "info")
    assert [call[0] for call in db.calls] == ["company_research_worker_control_state"]


def test_render_worker_ops_page_admin_can_pause_worker(monkeypatch):
    import company_research_ops_dashboard as page

    ui = FakeUI(clicked={"research_worker_pause"})
    monkeypatch.setattr(page, "st", ui)
    db = RenderDB(_ops_state(paused=False), {"paused": True})
    page.render_company_research_ops_page(db, auth_enabled=True, role="admin")
    assert db.calls[-1] == (
        "company_research_worker_set_paused",
        {"p_paused": True, "p_note": "Planned maintenance"},
    )
    assert any("szüneteltetése rögzítve" in args[0] for name, args in ui.messages if name == "success")


def test_render_worker_ops_page_operator_can_resume_worker(monkeypatch):
    import company_research_ops_dashboard as page

    ui = FakeUI(clicked={"research_worker_resume"})
    monkeypatch.setattr(page, "st", ui)
    db = RenderDB(_ops_state(paused=True), {"paused": False})
    page.render_company_research_ops_page(db, auth_enabled=True, role="operator")
    assert db.calls[-1] == (
        "company_research_worker_set_paused",
        {"p_paused": False, "p_note": "Planned maintenance"},
    )


def test_render_worker_ops_page_requires_verified_auth(monkeypatch):
    import company_research_ops_dashboard as page

    ui = FakeUI()
    monkeypatch.setattr(page, "st", ui)
    page.render_company_research_ops_page(RenderDB(_ops_state()), auth_enabled=False, role="admin")
    assert any("ellenőrzött Supabase Auth" in args[0] for name, args in ui.messages if name == "error")


def test_nonnegative_int_handles_malformed_rpc_values():
    assert _nonnegative_int(12) == 12
    assert _nonnegative_int("7") == 7
    assert _nonnegative_int(-4) == 0
    assert _nonnegative_int(True) == 0
    assert _nonnegative_int("not-a-number") == 0
    assert _nonnegative_int(None) == 0


def test_zero_committed_budget_is_not_replaced_by_reserved_amount(monkeypatch):
    import company_research_ops_dashboard as page

    ui = FakeUI()
    monkeypatch.setattr(page, "st", ui)
    state = _ops_state()
    state["budget_today"]["committed_microusd"] = 0
    page.render_company_research_ops_page(RenderDB(state), auth_enabled=True, role="reader")
    cost_lines = [str(args[0]) for name, args in ui.messages if name == "write"]
    assert any("napi keretből lekötött összeg: **$0.0000**" in line for line in cost_lines)



def test_ops_alerts_cover_dead_letters_budget_and_expired_leases():
    from datetime import datetime, timezone
    from company_research_ops_dashboard import _build_ops_alerts

    state = {
        "counts": {"dead_letter": 2},
        "budget_today": {
            "over_budget": False,
            "committed_microusd": 8500000,
            "limit_microusd": 10000000,
        },
        "recent_jobs": [
            {"status": "running", "lease_expires_at": "2026-11-28T14:00:00Z"},
            {"status": "running", "lease_expires_at": None},
            {"status": "succeeded", "lease_expires_at": "2020-01-01T00:00:00Z"},
        ],
    }
    alerts = _build_ops_alerts(state, now=datetime(2026, 11, 28, 15, 0, tzinfo=timezone.utc))
    messages = [alert["message"] for alert in alerts]
    assert any("2 kutatási feladat" in message for message in messages)
    assert any("80%-a lekötve" in message for message in messages)
    assert any("2 futó job lease-e" in message for message in messages)


def test_ops_alerts_fail_safe_on_over_budget_and_ignore_malformed_counters():
    from company_research_ops_dashboard import _build_ops_alerts

    alerts = _build_ops_alerts({
        "counts": {"dead_letter": "bad"},
        "budget_today": {"over_budget": True, "limit_microusd": "bad"},
        "recent_jobs": "invalid",
    })
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "error"
    assert "túllépte" in alerts[0]["message"]
