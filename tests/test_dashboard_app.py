"""Streamlit AppTest coverage for login, chat turns, task approval and email preview."""
import time
from types import SimpleNamespace

from pathlib import Path

from streamlit.testing.v1 import AppTest

import chat_email
import email_utils
import global_lead_research
import jarvis_common
import jarvis_memory
import task_actions


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
    task_calls = []
    smtp_calls = []
    db = _ReadOnlyDB()

    monkeypatch.setattr(
        jarvis_common, "get_secret",
        lambda key, default=None: "app-test-password" if key == "JARVIS_DASHBOARD_PASSWORD" else default,
    )
    monkeypatch.setattr(jarvis_common, "get_supabase", lambda: db)
    monkeypatch.setattr(jarvis_common, "get_model_name", lambda: "test-model")
    monkeypatch.setattr(jarvis_common, "estimate_response_tokens", lambda _prompt: 256)
    monkeypatch.setattr(jarvis_common, "generate_text", lambda prompt, **_kwargs: ("APPT_TASK_EXECUTED" if "APPT_TASK_EXECUTED" in prompt else "APPT_CHAT_RESPONSE"))
    monkeypatch.setattr(jarvis_common, "log_event", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(jarvis_common, "audit_event", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(jarvis_common, "env_bool", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(global_lead_research, "get_research_market", lambda _db: "Hungary")
    monkeypatch.setattr(jarvis_memory, "memory_command", lambda _prompt: ("", None))
    monkeypatch.setattr(jarvis_memory, "get_memories", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        task_actions, "execute_task_action",
        lambda _db, action, *, approved=False: (
            task_calls.append((action, approved)) or "APPT_TASK_EXECUTED"
        ),
    )
    monkeypatch.setattr(
        chat_email, "build_chat_email_draft",
        lambda *_args, **_kwargs: ("APPT tárgy", "APPT levéltörzs"),
    )
    monkeypatch.setattr(email_utils, "EMAIL_DELIVERY_ENABLED", False)
    monkeypatch.setattr(
        email_utils, "send_email",
        lambda *args, **kwargs: smtp_calls.append((args, kwargs)),
    )

    app = AppTest.from_file(str(ROOT / "dashboard.py"), default_timeout=20)
    return app, task_calls, smtp_calls


def _submit_chat(app, prompt):
    assert len(app.chat_input) == 1
    app.chat_input[0].set_value(prompt).run()
    assert not app.exception


def _markdown_values(app):
    return [element.value for element in app.markdown]


def test_streamlit_login_chat_task_approval_and_email_preview_are_isolated(monkeypatch):
    app, task_calls, smtp_calls = _prepare_dashboard(monkeypatch)
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

    _submit_chat(app, "Hozz létre feladat: AppTest ellenőrzés; prioritás=high")
    assert task_calls == []
    assert any("Jóváhagyásra váró feladatművelet" in value for value in _markdown_values(app))

    _submit_chat(app, "Jóváhagyom")
    assert len(task_calls) == 1
    assert task_calls[0][1] is True
    assert any("APPT_TASK_EXECUTED" in value for value in _markdown_values(app))

    _submit_chat(app, "Küldj emailt a teszt@example.com címre a szolgáltatásunkról")
    assert smtp_calls == []
    assert any("APPT levéltörzs" in value for value in _markdown_values(app))
    assert any("A levél nem ment ki." in value for value in _markdown_values(app))

    _submit_chat(app, "Jóváhagyom")
    assert smtp_calls == []
    assert any("CHAT_EMAIL_ENABLED" in value for value in _markdown_values(app))
