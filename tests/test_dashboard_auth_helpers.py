"""Focused tests for the dashboard's opt-in Supabase Auth session helpers."""
import ast
import time
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
TREE = ast.parse((ROOT / "dashboard.py").read_text(encoding="utf-8"))


class FakeStreamlit:
    def __init__(self, state=None):
        self.session_state = dict(state or {})
        self.warnings = []

    def warning(self, message):
        self.warnings.append(message)


def load_auth_helpers(monkeypatch, *, state=None, enabled=True, get_user=None, legacy=None):
    names = {"_auth_login_enabled", "_auth_session_kwargs", "_get_dashboard_supabase", "authenticated"}
    selected = [
        node for node in TREE.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    assert {node.name for node in selected} == names
    st = FakeStreamlit(state)
    calls = {"user": [], "legacy": 0, "errors": []}

    def fake_get_user(session, *, allowed_roles):
        calls["user"].append((session, allowed_roles))
        if get_user:
            return get_user(session, allowed_roles=allowed_roles)
        return object(), {"access_token": "refreshed", "role": "operator"}

    namespace = {
        "Any": Any,
        "time": time,
        "AUTH_SESSION_TTL_SECONDS": 8 * 60 * 60,
        "st": st,
        "env_bool": lambda name, default=False: enabled if name == "JARVIS_SUPABASE_AUTH_LOGIN_ENABLED" else default,
        "get_user_supabase": fake_get_user,
        "get_legacy_dashboard_supabase": lambda: (calls.update(legacy=calls["legacy"] + 1) or legacy or object()),
        "get_secret": lambda _name: "configured-password",
        "sign_in_user": lambda *_args: {"access_token": "token", "role": "admin"},
        "report_error": lambda error, **kwargs: calls["errors"].append((error, kwargs)),
    }
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(ROOT / "dashboard.py"), "exec"), namespace)
    return namespace, st, calls


def test_auth_login_flag_and_session_kwargs_are_opt_in(monkeypatch):
    namespace, st, _calls = load_auth_helpers(monkeypatch, enabled=False)
    assert namespace["_auth_login_enabled"]() is False
    assert namespace["_auth_session_kwargs"]() == {}

    namespace, st, _calls = load_auth_helpers(
        monkeypatch,
        enabled=True,
        state={"_jarvis_auth_session": {"access_token": "secret-token"}},
    )
    assert namespace["_auth_login_enabled"]() is True
    assert namespace["_auth_session_kwargs"]() == {
        "auth_session": {"access_token": "secret-token"}
    }


def test_get_dashboard_supabase_refreshes_session_and_uses_allowed_roles(monkeypatch):
    session = {"access_token": "old-token", "role": "reader"}
    namespace, st, calls = load_auth_helpers(
        monkeypatch, state={"_jarvis_auth_session": session}, enabled=True
    )

    db = namespace["_get_dashboard_supabase"]()

    assert calls["legacy"] == 0
    assert calls["user"] == [(session, {"admin", "operator", "reader"})]
    assert db is st.session_state["_jarvis_db"] if "_jarvis_db" in st.session_state else db
    assert session == {"access_token": "refreshed", "role": "operator"}
    assert st.session_state["_jarvis_user_role"] == "operator"


def test_get_dashboard_supabase_fails_closed_without_auth_session(monkeypatch):
    namespace, _st, calls = load_auth_helpers(monkeypatch, state={}, enabled=True)

    def fail_missing(session, *, allowed_roles):
        assert session is None
        raise PermissionError("missing user session")

    namespace["get_user_supabase"] = fail_missing
    with pytest.raises(PermissionError):
        namespace["_get_dashboard_supabase"]()
    assert calls["legacy"] == 0


def test_get_dashboard_supabase_uses_legacy_client_only_when_auth_disabled(monkeypatch):
    legacy_db = object()
    namespace, _st, calls = load_auth_helpers(
        monkeypatch, enabled=False, legacy=legacy_db
    )
    assert namespace["_get_dashboard_supabase"]() is legacy_db
    assert calls["legacy"] == 1
    assert calls["user"] == []


def test_authenticated_accepts_only_a_verified_auth_session(monkeypatch):
    session = {"access_token": "valid", "role": "reader"}
    namespace, st, calls = load_auth_helpers(
        monkeypatch,
        state={"_jarvis_auth_session": session, "_jarvis_pending_action": {"unsafe": True}},
        enabled=True,
    )

    assert namespace["authenticated"]() is True
    assert st.session_state["authenticated"] is True
    assert st.session_state["_jarvis_db"] is not None
    assert calls["legacy"] == 0


def test_authenticated_clears_stale_session_and_pending_action_on_verification_error(monkeypatch):
    namespace, st, calls = load_auth_helpers(
        monkeypatch,
        state={
            "_jarvis_auth_session": {"access_token": "expired"},
            "_jarvis_user_role": "admin",
            "_jarvis_db": object(),
            "_jarvis_pending_action": {"task_action": {"type": "delete"}},
        },
        enabled=True,
        get_user=lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("revoked")),
    )

    assert namespace["authenticated"]() is False
    assert "_jarvis_auth_session" not in st.session_state
    assert "_jarvis_user_role" not in st.session_state
    assert "_jarvis_db" not in st.session_state
    assert "_jarvis_pending_action" not in st.session_state
    assert st.session_state["authenticated"] is False
    assert st.warnings
    assert calls["legacy"] == 0
