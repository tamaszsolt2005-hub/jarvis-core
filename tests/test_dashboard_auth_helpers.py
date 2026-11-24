"""Focused tests for the dashboard's opt-in Supabase Auth session helpers."""
import ast
import time
from uuid import uuid4
from contextlib import nullcontext
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

    def error(self, message):
        self.warnings.append(message)

    def markdown(self, *_args, **_kwargs):
        return None

    def title(self, *_args, **_kwargs):
        return None

    def caption(self, *_args, **_kwargs):
        return None

    def form(self, *_args, **_kwargs):
        return nullcontext()

    def text_input(self, *_args, **_kwargs):
        return ""

    def form_submit_button(self, *_args, **_kwargs):
        return False


def load_auth_helpers(monkeypatch, *, state=None, enabled=True, get_user=None, legacy=None):
    names = {"_auth_login_enabled", "_auth_session_kwargs", "_approval_actor", "_stage_pending_action", "_consume_pending_action", "_audit_export_is_valid", "_get_dashboard_supabase", "authenticated"}
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
        "uuid4": uuid4,
        "PENDING_APPROVAL_TTL_SECONDS": 5 * 60,
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
    assert db is not None
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



def test_pending_approval_is_one_time_and_bound_to_authenticated_user(monkeypatch):
    session = {"access_token": "token", "user_id": "user-a"}
    namespace, st, _calls = load_auth_helpers(
        monkeypatch,
        state={"_jarvis_auth_session": session},
        enabled=True,
    )
    action = {"task_action": {"type": "create", "title": "Bound action"}}

    namespace["_stage_pending_action"](action)
    staged = st.session_state["_jarvis_pending_action"]
    assert staged["_approval_actor"] == "auth:user-a"
    assert staged["_approval_nonce"]
    assert isinstance(staged["_approval_created_at"], (int, float))

    consumed = namespace["_consume_pending_action"]()
    assert consumed == action
    assert "_jarvis_pending_action" not in st.session_state
    assert namespace["_consume_pending_action"]() is None


def test_pending_approval_expires_after_five_minutes(monkeypatch):
    namespace, st, _calls = load_auth_helpers(
        monkeypatch,
        state={"_jarvis_auth_session": {"user_id": "user-a"}},
        enabled=True,
    )
    namespace["_stage_pending_action"]({"market": "HU"})
    st.session_state["_jarvis_pending_action"]["_approval_created_at"] = (
        time.time() - namespace["PENDING_APPROVAL_TTL_SECONDS"] - 1
    )

    assert namespace["_consume_pending_action"]() is None
    assert "_jarvis_pending_action" not in st.session_state


def test_pending_approval_cannot_be_consumed_by_a_different_user(monkeypatch):
    namespace, st, _calls = load_auth_helpers(
        monkeypatch,
        state={"_jarvis_auth_session": {"user_id": "user-a"}},
        enabled=True,
    )
    namespace["_stage_pending_action"]({"chat_email": {"recipient": "a@example.com"}})
    st.session_state["_jarvis_auth_session"] = {"user_id": "user-b"}

    assert namespace["_consume_pending_action"]() is None
    assert "_jarvis_pending_action" not in st.session_state


def test_pending_approval_requires_valid_legacy_login_timestamp(monkeypatch):
    namespace, st, _calls = load_auth_helpers(
        monkeypatch,
        state={"authenticated": True},
        enabled=False,
    )
    namespace["_stage_pending_action"]({"market": "HU"})
    assert namespace["_consume_pending_action"]() is None
    assert "_jarvis_pending_action" not in st.session_state



def test_audit_export_approval_is_time_limited_and_bound_to_admin(monkeypatch):
    namespace, _st, _calls = load_auth_helpers(
        monkeypatch,
        state={},
        enabled=True,
    )
    valid = {
        "operation_id": "operation-1",
        "rows": [{"id": "audit-1"}],
        "actor_user_id": "admin-a",
        "created_at": 400.0,
    }
    assert namespace["_audit_export_is_valid"](valid, "admin-a", now=500.0)
    assert not namespace["_audit_export_is_valid"](valid, "admin-b", now=500.0)
    assert not namespace["_audit_export_is_valid"](valid, "admin-a", now=701.0)
    assert not namespace["_audit_export_is_valid"](valid, None, now=500.0)


def test_pending_approval_rejects_malformed_metadata_and_non_dict_actions(monkeypatch):
    namespace, st, _calls = load_auth_helpers(
        monkeypatch, state={"_jarvis_auth_session": {"user_id": "user-a"}}, enabled=True
    )
    with pytest.raises(TypeError):
        namespace["_stage_pending_action"]("not-a-dict")
    for bad_timestamp, bad_nonce in ((True, "nonce"), (time.time() + 60, "nonce"), (time.time(), "")):
        namespace["_stage_pending_action"]({"operation": "write"})
        pending = st.session_state["_jarvis_pending_action"]
        pending["_approval_created_at"] = bad_timestamp
        pending["_approval_nonce"] = bad_nonce
        assert namespace["_consume_pending_action"]() is None
        assert "_jarvis_pending_action" not in st.session_state


def test_pending_approval_legacy_actor_and_valid_consumption(monkeypatch):
    namespace, st, _calls = load_auth_helpers(
        monkeypatch, state={"_jarvis_authenticated_at": 1234.5}, enabled=False
    )
    assert namespace["_approval_actor"]() == "legacy:1234.5"
    namespace["_stage_pending_action"]({"action": "archive"})
    assert namespace["_consume_pending_action"]() == {"action": "archive"}


def test_pending_approval_without_principal_is_rejected(monkeypatch):
    namespace, st, _calls = load_auth_helpers(monkeypatch, state={}, enabled=True)
    namespace["_stage_pending_action"]({"action": "send"})
    assert st.session_state["_jarvis_pending_action"]["_approval_actor"] is None
    assert namespace["_consume_pending_action"]() is None


@pytest.mark.parametrize("pending", [
    None,
    [],
    {"created_at": True, "actor_user_id": "admin", "operation_id": "op", "rows": []},
    {"created_at": 10, "actor_user_id": "admin", "operation_id": "", "rows": []},
    {"created_at": 10, "actor_user_id": "admin", "operation_id": "op", "rows": ()},
    {"created_at": 501, "actor_user_id": "admin", "operation_id": "op", "rows": []},
])
def test_audit_export_rejects_malformed_or_future_approval(monkeypatch, pending):
    namespace, _st, _calls = load_auth_helpers(monkeypatch, state={}, enabled=True)
    assert namespace["_audit_export_is_valid"](pending, "admin", now=500) is False


def test_authenticated_legacy_session_expiry_and_missing_password(monkeypatch):
    namespace, st, _calls = load_auth_helpers(
        monkeypatch,
        state={"authenticated": True, "_jarvis_authenticated_at": time.time() - 9 * 60 * 60},
        enabled=False,
    )
    assert namespace["authenticated"]() is False
    assert "authenticated" not in st.session_state
    assert "_jarvis_db" not in st.session_state

    namespace, st, _calls = load_auth_helpers(monkeypatch, state={}, enabled=False)
    namespace["get_secret"] = lambda _name: None
    assert namespace["authenticated"]() is False


def test_authenticated_legacy_session_within_ttl_is_accepted(monkeypatch):
    namespace, _st, _calls = load_auth_helpers(
        monkeypatch,
        state={"authenticated": True, "_jarvis_authenticated_at": time.time() - 30},
        enabled=False,
    )
    assert namespace["authenticated"]() is True
