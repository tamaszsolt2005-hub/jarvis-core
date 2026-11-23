"""Streamlit AppTest coverage for login, normal chat, email preview and mocked SMTP approval."""
from types import SimpleNamespace

from pathlib import Path

from streamlit.testing.v1 import AppTest

import chat_email
import email_utils
import global_lead_research
import jarvis_common
import jarvis_memory
import task_actions
import health_check


ROOT = Path(__file__).resolve().parents[1]


class _Query:
    def __init__(self, rows=None):
        self.rows = rows or []

    def select(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def gte(self, *_args, **_kwargs):
        return self

    def lte(self, *_args, **_kwargs):
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


class _ReadOnlyDB:
    def __init__(self, rows=None):
        self.rows = rows or []

    def table(self, _name):
        return _Query(self.rows)


def _prepare_dashboard(monkeypatch):
    smtp_calls = []
    email_switch = {"enabled": False}
    db = _ReadOnlyDB()

    monkeypatch.setattr(
        jarvis_common, "get_secret",
        lambda key, default=None: "app-test-password" if key == "JARVIS_DASHBOARD_PASSWORD" else default,
    )
    monkeypatch.setattr(jarvis_common, "get_supabase", lambda: db)
    monkeypatch.setattr(jarvis_common, "get_model_name", lambda: "test-model")
    monkeypatch.setattr(jarvis_common, "estimate_response_tokens", lambda _prompt: 256)
    monkeypatch.setattr(jarvis_common, "generate_text", lambda *_args, **_kwargs: "APPT_CHAT_RESPONSE")
    monkeypatch.setattr(jarvis_common, "log_event", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(jarvis_common, "audit_event", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(jarvis_common, "env_bool", lambda *_args, **_kwargs: email_switch["enabled"])
    monkeypatch.setattr(global_lead_research, "get_research_market", lambda _db: "Hungary")
    monkeypatch.setattr(jarvis_memory, "memory_command", lambda _prompt: ("", None))
    monkeypatch.setattr(jarvis_memory, "get_memories", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        chat_email, "build_chat_email_draft",
        lambda *_args, **_kwargs: ("APPT tárgy", "APPT levéltörzs"),
    )
    monkeypatch.setattr(email_utils, "EMAIL_DELIVERY_ENABLED", True)
    monkeypatch.setattr(
        email_utils, "send_email",
        lambda *args, **kwargs: (smtp_calls.append((args, kwargs)) or "mock-smtp-id"),
    )

    app = AppTest.from_file(str(ROOT / "dashboard.py"), default_timeout=20)
    return app, smtp_calls, email_switch


def _submit_chat(app, prompt):
    assert len(app.chat_input) == 1
    app.chat_input[0].set_value(prompt).run()
    assert not app.exception


def _markdown_values(app):
    return [element.value for element in app.markdown]


def test_streamlit_login_chat_and_email_preview_are_isolated(monkeypatch):
    app, smtp_calls, email_switch = _prepare_dashboard(monkeypatch)
    app.run()
    assert not app.exception
    assert len(app.text_input) == 1
    assert len(app.button) == 1

    app.text_input[0].set_value("hibás-jelszó")
    app.button[0].click().run()
    assert any("Hibás jelszó" in item.value for item in app.error)
    assert "authenticated" not in app.session_state

    app.text_input[0].set_value("app-test-password")
    app.button[0].click().run()
    assert not app.exception
    assert app.session_state["authenticated"] is True
    assert len(app.chat_input) == 1

    _submit_chat(app, "Szia JARVIS, válaszolj röviden.")
    assert any("APPT_CHAT_RESPONSE" in value for value in _markdown_values(app))

    _submit_chat(app, "Küldj emailt a teszt@example.com címre a szolgáltatásunkról")
    assert smtp_calls == []
    assert any("APPT levéltörzs" in value for value in _markdown_values(app))
    assert any("A levél nem ment ki." in value for value in _markdown_values(app))

    _submit_chat(app, "Jóváhagyom")
    assert smtp_calls == []
    assert any("CHAT_EMAIL_ENABLED" in value for value in _markdown_values(app))

    _submit_chat(app, "Küldj emailt a teszt@example.com címre a szolgáltatásunkról")
    assert smtp_calls == []
    email_switch["enabled"] = True
    _submit_chat(app, "Jóváhagyom")
    assert len(smtp_calls) == 1
    assert smtp_calls[0][0] == ("teszt@example.com", "APPT tárgy", "APPT levéltörzs")
    assert any("SMTP-szerver átvette" in value for value in _markdown_values(app))



def test_streamlit_analytics_navigation_renders_empty_state_and_returns_to_chat(monkeypatch):
    app, _smtp_calls, _email_switch = _prepare_dashboard(monkeypatch)
    app.run()
    app.text_input[0].set_value("app-test-password")
    app.button[0].click().run()
    assert not app.exception

    app.button(key="jarvis_nav_analytics").click().run()
    assert not app.exception
    assert app.session_state["jarvis_page"] == "analytics"
    assert any("Analitika" in item.value for item in app.markdown)
    assert any("Ebben az időszakban még nincs naplózott aktivitás" in item.value for item in app.markdown)

    app.button(key="jarvis_nav_chat").click().run()
    assert not app.exception
    assert app.session_state["jarvis_page"] == "chat"
    assert any("Üdvözöllek!" in item.value for item in app.markdown)


def test_streamlit_analytics_period_selector_renders_populated_charts(monkeypatch):
    from datetime import datetime, timedelta, timezone

    records = [
        {"module": "chat", "level": "info", "message": "chat_request", "created_at": (datetime.now(timezone.utc) - timedelta(minutes=4)).isoformat()},
        {"module": "chat", "level": "info", "message": "chat_response", "created_at": (datetime.now(timezone.utc) - timedelta(minutes=3)).isoformat()},
        {"module": "email_sender", "level": "error", "message": "delivery_failure", "created_at": (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()},
        {"module": "follow_up", "level": "warning", "message": "followup_pending", "created_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()},
    ]
    app, _smtp_calls, _email_switch = _prepare_dashboard(monkeypatch)
    db = _ReadOnlyDB(records)
    monkeypatch.setattr(jarvis_common, "get_supabase", lambda: db)
    app.run()
    app.text_input[0].set_value("app-test-password")
    app.button[0].click().run()
    app.button(key="jarvis_nav_analytics").click().run()

    assert not app.exception
    assert app.session_state["jarvis_page"] == "analytics"
    assert len(app.get("plotly_chart")) == 4
    assert any("Naplózott események" in item.value for item in app.markdown)
    assert len(app.radio) == 1
    app.radio[0].set_value("7 nap").run()
    assert not app.exception
    assert app.session_state["jarvis_analytics_range"] == "7 nap"
    assert len(app.get("plotly_chart")) == 4


def test_streamlit_analytics_database_failure_is_isolated_from_chat(monkeypatch):
    class BrokenDB:
        def table(self, _name):
            raise RuntimeError("mock analytics database outage")

    app, _smtp_calls, _email_switch = _prepare_dashboard(monkeypatch)
    monkeypatch.setattr(jarvis_common, "get_supabase", lambda: BrokenDB())
    app.run()
    app.text_input[0].set_value("app-test-password")
    app.button[0].click().run()
    app.button(key="jarvis_nav_analytics").click().run()

    assert not app.exception
    assert any("Az analitikai naplók most nem tölthetők be." in item.value for item in app.error)
    assert app.session_state["jarvis_page"] == "analytics"
    app.button(key="jarvis_nav_chat").click().run()
    assert not app.exception
    assert app.session_state["jarvis_page"] == "chat"



def test_streamlit_task_approval_executes_only_after_explicit_confirmation(monkeypatch):
    task_calls = []
    monkeypatch.setattr(
        task_actions, "execute_task_action",
        lambda _db, action, *, approved=False: (
            task_calls.append((action, approved)) or "APPT_TASK_EXECUTED"
        ),
    )
    app, _smtp_calls, _email_switch = _prepare_dashboard(monkeypatch)
    app.run()
    app.text_input[0].set_value("app-test-password")
    app.button[0].click().run()

    _submit_chat(app, "Hozz létre feladat: AppTest ellenőrzés; határidő=2026-12-01; prioritás=high")
    assert task_calls == []
    assert app.session_state["_jarvis_pending_action"]["task_action"]["type"] == "create"

    _submit_chat(app, "Jóváhagyom")
    assert len(task_calls) == 1
    assert task_calls[0][1] is True
    assert "_jarvis_pending_action" not in app.session_state


def test_streamlit_task_rejection_clears_pending_action_without_execution(monkeypatch):
    task_calls = []
    monkeypatch.setattr(
        task_actions, "execute_task_action",
        lambda *args, **kwargs: task_calls.append((args, kwargs)),
    )
    app, _smtp_calls, _email_switch = _prepare_dashboard(monkeypatch)
    app.run()
    app.text_input[0].set_value("app-test-password")
    app.button[0].click().run()

    _submit_chat(app, "Hozz létre feladat: Elutasítandó AppTest; prioritás=normal")
    assert "_jarvis_pending_action" in app.session_state
    _submit_chat(app, "Elutasítom")
    assert task_calls == []
    assert "_jarvis_pending_action" not in app.session_state


def test_streamlit_system_diagnostics_chat_command_renders_report(monkeypatch):
    monkeypatch.setattr(health_check, "run_self_diagnostics", lambda: "APPT_DIAGNOSTICS_OK")
    app, _smtp_calls, _email_switch = _prepare_dashboard(monkeypatch)
    app.run()
    app.text_input[0].set_value("app-test-password")
    app.button[0].click().run()

    _submit_chat(app, "rendszerdiagnosztika")
    assert any("APPT_DIAGNOSTICS_OK" in value for value in _markdown_values(app))
    assert not app.exception


def test_streamlit_executive_analytics_report_chat_branch_uses_log_facts(monkeypatch):
    from datetime import datetime, timezone

    records = [
        {"module": "chat", "level": "info", "message": "chat_request", "created_at": datetime.now(timezone.utc).isoformat()},
        {"module": "email_sender", "level": "error", "message": "mock_failure", "created_at": datetime.now(timezone.utc).isoformat()},
    ]
    app, _smtp_calls, _email_switch = _prepare_dashboard(monkeypatch)
    monkeypatch.setattr(jarvis_common, "get_supabase", lambda: _ReadOnlyDB(records))
    app.run()
    app.text_input[0].set_value("app-test-password")
    app.button[0].click().run()

    _submit_chat(app, "Készíts 30 napos vezetői analitikai jelentést")
    values = _markdown_values(app)
    assert any("Összes naplózott esemény a 30 napos ablakban: **2**" in value for value in values)
    assert any("Hibaszintű esemény (error/critical/fatal): **1**" in value for value in values)
    assert not app.exception
