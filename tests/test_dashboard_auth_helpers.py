"""Focused tests for dashboard authentication and database-backed approvals."""
import hashlib
import json
import time
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest


ROOT = Path(__file__).resolve().parents[1]


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


class FakeDB:
    def __init__(self):
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=True))


def load_helpers(monkeypatch, *, state=None, enabled=True, get_user=None):
    import ast

    source = (ROOT / "dashboard.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {
        "_auth_login_enabled", "_auth_session_kwargs", "_approval_actor",
        "_approval_rpc_bool", "_approval_database_payload", "_stage_pending_action",
        "_revoke_pending_action", "_consume_pending_action", "_audit_export_is_valid",
        "_get_dashboard_supabase", "authenticated",
    }
    selected = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    assert {node.name for node in selected} == names

    st = FakeStreamlit(state)
    db = FakeDB()
    calls = {"user": [], "enforced": [], "errors": [], "db": db}

    def fake_get_user(session, *, allowed_roles):
        calls["user"].append((session, allowed_roles))
        if get_user:
            return get_user(session, allowed_roles=allowed_roles)
        return object(), {
            "access_token": "refreshed", "refresh_token": "new-refresh",
            "user_id": session["user_id"], "role": "operator",
        }

    def fake_enforced(session, permission, *, allowed_roles):
        calls["enforced"].append((session, permission, allowed_roles))
        if not isinstance(session, dict):
            raise PermissionError("missing user session")
        return object(), {"user_id": session["user_id"], "role": session.get("role", "operator")}

    namespace = {
        "Any": object,
        "ast": ast,
        "hashlib": hashlib,
        "hmac": __import__("hmac"),
        "json": json,
        "secrets": __import__("secrets"),
        "time": time,
        "uuid4": uuid4,
        "PENDING_APPROVAL_TTL_SECONDS": 300,
        "AUTH_SESSION_TTL_SECONDS": 8 * 60 * 60,
        "st": st,
        "env_bool": lambda name, default=False: enabled if name in {
            "JARVIS_SUPABASE_AUTH_LOGIN_ENABLED", "JARVIS_AUTH_RBAC_ENFORCED"
        } else default,
        "get_user_supabase": fake_get_user,
        "get_enforced_user_supabase": fake_enforced,
        "get_service_supabase": lambda: db,
        "get_legacy_dashboard_supabase": lambda: object(),
        "get_secret": lambda _name: "configured-password",
        "sign_in_user": lambda *_args: {"access_token": "token", "role": "admin"},
        "report_error": lambda error, **kwargs: calls["errors"].append((error, kwargs)),
    }
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(ROOT / "dashboard.py"), "exec"), namespace)
    return namespace, st, calls


def _task_action():
    return {"task_action": {"type": "create", "title": "Approved task", "priority": "normal", "due_at": None, "notes": ""}}


def test_auth_login_flag_and_session_kwargs_are_opt_in(monkeypatch):
    namespace, _st, _calls = load_helpers(monkeypatch, enabled=False)
    assert namespace["_auth_login_enabled"]() is False
    assert namespace["_auth_session_kwargs"]() == {}

    namespace, _st, _calls = load_helpers(
        monkeypatch, enabled=True,
        state={"_jarvis_auth_session": {"access_token": "secret-token", "user_id": "user-a"}},
    )
    assert namespace["_auth_login_enabled"]() is True
    assert namespace["_auth_session_kwargs"]() == {
        "auth_session": {"access_token": "secret-token", "user_id": "user-a"}
    }


def test_get_dashboard_supabase_refreshes_session_and_uses_allowed_roles(monkeypatch):
    session = {"access_token": "old-token", "user_id": "user-a", "role": "reader"}
    namespace, st, calls = load_helpers(
        monkeypatch, state={"_jarvis_auth_session": session}, enabled=True
    )
    db = namespace["_get_dashboard_supabase"]()
    assert calls["user"] == [(session, {"admin", "operator", "reader"})]
    assert session["access_token"] == "refreshed"
    assert st.session_state["_jarvis_user_role"] == "operator"
    assert db is not None


def test_get_dashboard_supabase_fails_closed_without_auth_session(monkeypatch):
    namespace, _st, calls = load_helpers(monkeypatch, enabled=True)
    with pytest.raises(PermissionError):
        namespace["_get_dashboard_supabase"]()
    assert calls["user"] == []


def test_authenticated_clears_stale_session_and_pending_action_on_verification_error(monkeypatch):
    namespace, st, calls = load_helpers(
        monkeypatch,
        state={
            "_jarvis_auth_session": {"access_token": "expired", "user_id": "user-a"},
            "_jarvis_user_role": "admin",
            "_jarvis_db": object(),
            "_jarvis_pending_action": {"task_action": {"type": "create"}},
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
    assert calls["errors"] == []


def test_task_approval_is_persisted_and_bound_to_the_authenticated_principal(monkeypatch):
    session = {"access_token": "token", "user_id": "10000000-0000-4000-8000-000000000001", "role": "operator"}
    namespace, st, calls = load_helpers(
        monkeypatch, state={"_jarvis_auth_session": session}, enabled=True
    )
    namespace["_stage_pending_action"](_task_action(), calls["db"])
    staged = st.session_state["_jarvis_pending_action"]
    assert staged["_approval_actor"] == "auth:" + session["user_id"]
    assert staged["_approval_token"]
    assert len(staged["_approval_token_hash"]) == 64
    assert staged["task_action"]["operation_id"]
    assert calls["db"].calls[0][0] == "issue_pending_approval"
    assert calls["enforced"][0][1:] == ("tasks.write", {"admin", "operator"})

    consumed = namespace["_consume_pending_action"](calls["db"])
    assert consumed["task_action"]["operation_id"] == staged["task_action"]["operation_id"]
    assert consumed["_approval"]["principal"] == staged["_approval_actor"]
    assert consumed["_approval"]["token"] == staged["_approval_token"]
    # Task approvals remain locally available until the atomic task RPC commits.
    assert "_jarvis_pending_action" in st.session_state


def test_generic_approval_is_consumed_once_in_the_database(monkeypatch):
    namespace, st, calls = load_helpers(
        monkeypatch,
        state={"_jarvis_auth_session": {"user_id": "10000000-0000-4000-8000-000000000001", "role": "operator"}},
        enabled=True,
    )
    action = {"chat_email": {"recipient": "person@example.test", "subject": "Hello", "body": "Body"}}
    namespace["_stage_pending_action"](action, calls["db"])
    consumed = namespace["_consume_pending_action"](calls["db"])
    assert consumed["chat_email"]["recipient"] == "person@example.test"
    assert [name for name, _params in calls["db"].calls] == [
        "issue_pending_approval", "consume_pending_approval"
    ]
    assert "_jarvis_pending_action" not in st.session_state
    assert namespace["_consume_pending_action"](calls["db"]) is None


def test_tampered_or_expired_task_approval_is_revoked(monkeypatch):
    namespace, st, calls = load_helpers(
        monkeypatch,
        state={"_jarvis_auth_session": {"user_id": "10000000-0000-4000-8000-000000000001", "role": "operator"}},
        enabled=True,
    )
    namespace["_stage_pending_action"](_task_action(), calls["db"])
    st.session_state["_jarvis_pending_action"]["task_action"]["title"] = "Tampered"
    assert namespace["_consume_pending_action"](calls["db"]) is None
    assert calls["db"].calls[-1][0] == "revoke_pending_approval"
    assert "_jarvis_pending_action" not in st.session_state

    namespace["_stage_pending_action"](_task_action(), calls["db"])
    st.session_state["_jarvis_pending_action"]["_approval_created_at"] = time.time() - 301
    assert namespace["_consume_pending_action"](calls["db"]) is None
    assert calls["db"].calls[-1][0] == "revoke_pending_approval"


def test_approval_cannot_be_consumed_by_a_different_user(monkeypatch):
    namespace, st, calls = load_helpers(
        monkeypatch,
        state={"_jarvis_auth_session": {"user_id": "10000000-0000-4000-8000-000000000001", "role": "operator"}},
        enabled=True,
    )
    namespace["_stage_pending_action"]({"chat_email": {"recipient": "a@example.test"}}, calls["db"])
    st.session_state["_jarvis_auth_session"] = {
        "user_id": "20000000-0000-4000-8000-000000000002", "role": "operator"
    }
    assert namespace["_consume_pending_action"](calls["db"]) is None
    assert "_jarvis_pending_action" not in st.session_state


def test_legacy_approval_uses_a_session_principal_and_database_token(monkeypatch):
    namespace, st, calls = load_helpers(
        monkeypatch, state={"authenticated": True}, enabled=False
    )
    namespace["_stage_pending_action"]({"market": "HU"}, calls["db"])
    principal = st.session_state["_jarvis_pending_action"]["_approval_actor"]
    assert principal.startswith("legacy:")
    assert namespace["_consume_pending_action"](calls["db"]) == {"market": "HU"}
    assert [name for name, _params in calls["db"].calls] == [
        "issue_pending_approval", "consume_pending_approval"
    ]


def test_staging_without_authenticated_principal_fails_closed(monkeypatch):
    namespace, st, calls = load_helpers(monkeypatch, enabled=True)
    with pytest.raises(PermissionError):
        namespace["_stage_pending_action"]({"chat_email": {"recipient": "a@example.test"}}, calls["db"])
    assert "_jarvis_pending_action" not in st.session_state
    assert calls["db"].calls == []


def test_approval_rpc_boolean_parser_is_strict(monkeypatch):
    namespace, _st, _calls = load_helpers(monkeypatch, enabled=False)
    assert namespace["_approval_rpc_bool"](SimpleNamespace(data=True))
    assert not namespace["_approval_rpc_bool"](SimpleNamespace(data="true"))
    assert not namespace["_approval_rpc_bool"](SimpleNamespace(data=[True, False]))


def test_audit_export_approval_is_time_limited_and_bound_to_admin(monkeypatch):
    namespace, _st, _calls = load_helpers(monkeypatch, enabled=True)
    valid = {
        "operation_id": "operation-1", "rows": [{"id": "audit-1"}],
        "actor_user_id": "admin-a", "created_at": 400.0,
    }
    assert namespace["_audit_export_is_valid"](valid, "admin-a", now=500.0)
    assert not namespace["_audit_export_is_valid"](valid, "admin-b", now=500.0)
    assert not namespace["_audit_export_is_valid"](valid, "admin-a", now=701.0)
    assert not namespace["_audit_export_is_valid"](valid, None, now=500.0)


def test_authenticated_legacy_session_expiry_and_within_ttl(monkeypatch):
    namespace, st, _calls = load_helpers(
        monkeypatch,
        state={"authenticated": True, "_jarvis_authenticated_at": time.time() - 9 * 60 * 60},
        enabled=False,
    )
    assert namespace["authenticated"]() is False
    assert "authenticated" not in st.session_state
    assert "_jarvis_db" not in st.session_state

    namespace, st, _calls = load_helpers(
        monkeypatch,
        state={"authenticated": True, "_jarvis_authenticated_at": time.time() - 30},
        enabled=False,
    )
    assert namespace["authenticated"]() is True
