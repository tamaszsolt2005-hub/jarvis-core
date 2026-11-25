"""Tests for explicit task parsing and atomic, approval-gated database execution."""
import hashlib
from types import SimpleNamespace

import pytest

import task_actions


TASK_ID = "123e4567-e89b-42d3-a456-426614174000"
OPERATION_ID = "223e4567-e89b-42d3-a456-426614174001"
TOKEN = "test-one-use-approval-token-that-is-long-enough"


def _create_action(**changes):
    action = {
        "type": "create", "title": "Teszt feladat", "priority": "normal",
        "due_at": None, "notes": "", "operation_id": OPERATION_ID,
    }
    action.update(changes)
    return action


def _approval():
    return {"token": TOKEN, "principal": "legacy:323e4567-e89b-42d3-a456-426614174002"}


class FakeDB:
    def __init__(self, data=None, error=None):
        self.data = data or {"ok": True, "status": "success", "message": "Feladat létrehozva."}
        self.error = error
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))

        def execute():
            if self.error:
                raise self.error
            return SimpleNamespace(data=self.data)

        return SimpleNamespace(execute=execute)


def test_parse_create_task_with_deadline_and_priority():
    action = task_actions.parse_task_command(
        "Hozz létre feladat: Ajánlat ellenőrzése; határidő=2026-12-01; prioritás=high"
    )
    assert action == {
        "type": "create", "title": "Ajánlat ellenőrzése", "priority": "high",
        "due_at": "2026-12-01T23:59:00+01:00", "notes": "",
    }


def test_reject_invalid_priority_and_date():
    assert "prioritás" in task_actions.parse_task_command(
        "Új feladat: Teszt; prioritás=critical"
    )["error"]
    assert "dátum" in task_actions.parse_task_command(
        "Új feladat: Teszt; határidő=2026-02-30"
    )["error"]


def test_parse_close_and_update():
    assert task_actions.parse_task_command(
        f"Zárd le a feladatot: {TASK_ID}"
    ) == {"type": "close", "id": TASK_ID}
    action = task_actions.parse_task_command(
        f"Módosítsd a feladatot: {TASK_ID}; prioritás=urgent; cím=Fontos"
    )
    assert action["updates"] == {"priority": "urgent", "title": "Fontos"}


def test_non_explicit_command_is_not_action():
    assert task_actions.parse_task_command("Szerintem jó lenne lezárni a feladatot") is None


@pytest.mark.parametrize("action", [
    _create_action(),
    {"type": "close", "id": TASK_ID, "operation_id": OPERATION_ID},
    {"type": "update", "id": TASK_ID, "updates": {"title": "Új cím"}, "operation_id": OPERATION_ID},
])
def test_valid_actions_require_stable_operation_ids(action):
    task_actions._validate_action(action)


@pytest.mark.parametrize("action", [
    [],
    {"type": "create", "title": "", "priority": "normal", "operation_id": OPERATION_ID},
    {"type": "create", "title": "x" * 181, "priority": "normal", "operation_id": OPERATION_ID},
    {"type": "create", "title": "x", "priority": "urgent; DROP", "operation_id": OPERATION_ID},
    {"type": "create", "title": "x", "priority": "normal", "due_at": 123, "operation_id": OPERATION_ID},
    {"type": "create", "title": "x", "priority": "normal", "due_at": "2026-12-01T10:00:00", "operation_id": OPERATION_ID},
    {"type": "create", "title": "x", "priority": "normal", "operation_id": "bad-id"},
    {"type": "close", "id": TASK_ID},
    {"type": "update", "id": TASK_ID, "updates": {} , "operation_id": OPERATION_ID},
    {"type": "update", "id": TASK_ID, "updates": {"extra": "not allowed"}, "operation_id": OPERATION_ID},
])
def test_invalid_payloads_are_rejected(action):
    with pytest.raises(ValueError):
        task_actions._validate_action(action)


def test_task_execution_requires_explicit_approval_and_database_token():
    class ForbiddenDB:
        def rpc(self, *_args, **_kwargs):
            pytest.fail("Database must not be accessed without valid approval")

    with pytest.raises(PermissionError):
        task_actions.execute_task_action(ForbiddenDB(), _create_action())

    with pytest.raises(PermissionError):
        task_actions.execute_task_action(
            ForbiddenDB(), _create_action(), approved=True, approval=None
        )


def test_task_execution_calls_single_atomic_rpc_with_token_hash(monkeypatch):
    db = FakeDB()
    monkeypatch.setattr(task_actions, "get_enforced_user_supabase", lambda *_args, **_kwargs: None)

    result = task_actions.execute_task_action(
        db, _create_action(), approved=True, approval=_approval()
    )

    assert result == "Feladat létrehozva."
    assert len(db.calls) == 1
    name, params = db.calls[0]
    assert name == "execute_approved_task_action"
    assert params["p_token_hash"] == hashlib.sha256(TOKEN.encode()).hexdigest()
    assert params["p_principal"] == _approval()["principal"]
    assert params["p_operation_id"] == OPERATION_ID
    assert params["p_action"] == _create_action()


def test_rpc_error_is_reported_critical_and_original_error_reraised(monkeypatch):
    error = RuntimeError("mock atomic RPC failure")
    db = FakeDB(error=error)
    reports = []
    monkeypatch.setattr(task_actions, "get_enforced_user_supabase", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        task_actions, "report_error",
        lambda caught, **kwargs: reports.append((caught, kwargs)),
    )

    with pytest.raises(RuntimeError, match="mock atomic RPC failure") as caught:
        task_actions.execute_task_action(
            db, _create_action(), approved=True, approval=_approval()
        )

    assert caught.value is error
    assert len(reports) == 1
    assert reports[0][0] is error
    assert reports[0][1]["module"] == "task_actions"
    assert reports[0][1]["severity"] == "critical"
    assert reports[0][1]["operation"] == "execute_atomic:create"


def test_auth_enforcement_uses_verified_user_client_not_legacy_client(monkeypatch):
    legacy_db = FakeDB()
    user_db = FakeDB()
    calls = []
    session = {"user_id": "operator-id", "access_token": "old"}

    def enforce(supplied, permission, *, allowed_roles):
        calls.append((supplied, permission, allowed_roles))
        return user_db, {"user_id": "operator-id", "role": "operator"}

    monkeypatch.setattr(task_actions, "get_enforced_user_supabase", enforce)
    result = task_actions.execute_task_action(
        legacy_db, _create_action(), approved=True, approval=_approval(),
        auth_session=session,
    )

    assert result == "Feladat létrehozva."
    assert legacy_db.calls == []
    assert user_db.calls
    assert calls == [(session, "tasks.write", {"admin", "operator"})]


def test_auth_enforcement_denies_missing_session_before_rpc(monkeypatch):
    class ForbiddenDB:
        def rpc(self, *_args, **_kwargs):
            pytest.fail("No RPC is allowed without a verified Auth session")

    calls = []
    def deny(session, permission, *, allowed_roles):
        calls.append((session, permission, allowed_roles))
        raise PermissionError("verified Supabase Auth session required")

    monkeypatch.setattr(task_actions, "get_enforced_user_supabase", deny)
    with pytest.raises(PermissionError, match="verified Supabase Auth"):
        task_actions.execute_task_action(
            ForbiddenDB(), _create_action(), approved=True, approval=_approval()
        )
    assert calls == [(None, "tasks.write", {"admin", "operator"})]
