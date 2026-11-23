"""Streamlit AppTest coverage for login, chat turns, task approval and email preview."""
from types import SimpleNamespace

from pathlib import Path

from streamlit.testing.v1 import AppTest

import chat_email
import email_utils
import global_lead_research
import jarvis_common
import jarvis_memory


ROOT = Path(__file__).resolve().parents[1]


class _Query:
    def select(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def execute(self):
        return SimpleNamespace(data=[])


class _ReadOnlyDB:
    def table(self, _name):
        return _Query()


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
