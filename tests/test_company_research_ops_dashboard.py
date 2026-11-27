from types import SimpleNamespace

import pytest

from company_research_ops_dashboard import (
    load_worker_control_state,
    set_worker_paused,
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
