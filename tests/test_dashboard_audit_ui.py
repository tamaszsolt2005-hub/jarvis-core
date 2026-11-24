"""Authenticated audit-page UI branches, isolated from Supabase and SMTP."""
from __future__ import annotations

import time
from pathlib import Path

from streamlit.testing.v1 import AppTest

import audit_admin
import jarvis_common


ROOT = Path(__file__).resolve().parents[1]
_ADMIN_SESSION = {
    "access_token": "admin-access",
    "refresh_token": "admin-refresh",
    "user_id": "admin-1",
    "email": "admin@example.test",
}
_REFRESHED_SESSION = {
    **_ADMIN_SESSION,
    "access_token": "refreshed-access",
    "refresh_token": "refreshed-refresh",
}


class _RowsDB:
    def table(self, _name):
        raise AssertionError("The audit UI must use its verified admin client.")


def _prepare_audit_app(monkeypatch, *, admin_session=True):
    """Seed the legacy dashboard gate and route straight to the audit screen."""
    monkeypatch.setattr(
        jarvis_common, "get_secret",
        lambda _name, default=None: default,
    )
    monkeypatch.setattr(jarvis_common, "get_legacy_dashboard_supabase", _RowsDB)
    monkeypatch.setattr(jarvis_common, "env_bool", lambda _name, default=False: default)
    monkeypatch.setattr(jarvis_common, "get_model_name", lambda: "test-model")
    monkeypatch.setattr(jarvis_common, "estimate_response_tokens", lambda _prompt: 128)
    monkeypatch.setattr(jarvis_common, "generate_text", lambda *_args, **_kwargs: "unused")
    monkeypatch.setattr(jarvis_common, "log_event", lambda *_args, **_kwargs: True)

    app = AppTest.from_file(str(ROOT / "dashboard.py"), default_timeout=20)
    app.session_state["authenticated"] = True
    app.session_state["_jarvis_authenticated_at"] = time.time()
    app.session_state["jarvis_page"] = "audit"
    if admin_session:
        app.session_state["_jarvis_audit_admin_session"] = dict(_ADMIN_SESSION)
    return app


def _patch_verified_admin(monkeypatch, *, page=None):
    client = object()
    monkeypatch.setattr(
        audit_admin, "verified_admin_client",
        lambda _session: (client, dict(_REFRESHED_SESSION)),
    )
    monkeypatch.setattr(
        audit_admin, "fetch_audit_page",
        lambda _client, **_kwargs: page or {"events": [], "next_cursor": None},
    )
    return client


def _events():
    return [{
        "id": "event-1",
        "created_at": "2026-11-24T18:00:00Z",
        "module": "dashboard",
        "message": "chat_response",
        "status": "success",
        "operation_id": "operation-1",
    }]


def test_audit_admin_login_permission_error_is_user_friendly(monkeypatch):
    app = _prepare_audit_app(monkeypatch, admin_session=False)
    monkeypatch.setattr(
        audit_admin, "sign_in_audit_admin",
        lambda *_args: (_ for _ in ()).throw(PermissionError("denied")),
    )
    app.run()
    assert not app.exception
    app.text_input[0].set_value("reader@example.test")
    app.text_input[1].set_value("not-admin")
    app.button[-1].click().run()

    assert not app.exception
    assert any("Admin szerepkör szükséges" in item.value for item in app.error)
    assert "_jarvis_audit_admin_session" not in app.session_state


def test_audit_admin_login_validation_error_is_shown_without_reporter(monkeypatch):
    app = _prepare_audit_app(monkeypatch, admin_session=False)
    monkeypatch.setattr(
        audit_admin, "sign_in_audit_admin",
        lambda *_args: (_ for _ in ()).throw(ValueError("missing credentials")),
    )
    app.run()
    app.text_input[0].set_value("")
    app.text_input[1].set_value("")
    app.button[-1].click().run()

    assert not app.exception
    assert any("missing credentials" in item.value for item in app.error)


def test_audit_admin_login_unexpected_error_is_reported(monkeypatch):
    import jarvis_errors

    reports = []
    app = _prepare_audit_app(monkeypatch, admin_session=False)
    monkeypatch.setattr(
        audit_admin, "sign_in_audit_admin",
        lambda *_args: (_ for _ in ()).throw(OSError("mock auth transport")),
    )
    monkeypatch.setattr(
        jarvis_errors, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )
    app.run()
    app.text_input[0].set_value("admin@example.test")
    app.text_input[1].set_value("secret")
    app.button[-1].click().run()

    assert not app.exception
    assert reports and reports[0][1]["operation"] == "audit_admin_sign_in"
    assert any("biztonságos audit-belépés" in item.value for item in app.error)


def test_audit_admin_successful_login_opens_verified_read_only_view(monkeypatch):
    app = _prepare_audit_app(monkeypatch, admin_session=False)
    monkeypatch.setattr(audit_admin, "sign_in_audit_admin", lambda *_args: dict(_ADMIN_SESSION))
    _patch_verified_admin(monkeypatch, page={"events": _events(), "next_cursor": None})
    app.run()
    app.text_input[0].set_value("admin@example.test")
    app.text_input[1].set_value("secret")
    app.button[-1].click().run()

    assert not app.exception
    assert app.session_state["_jarvis_audit_admin_session"]["user_id"] == "admin-1"
    assert any("Hitelesített admin" in item.value for item in app.caption)
    assert any("CSV export előkészítése" in item.label for item in app.button)


def test_audit_admin_expired_session_is_cleared_and_reported(monkeypatch):
    import jarvis_errors

    reports = []
    app = _prepare_audit_app(monkeypatch)
    monkeypatch.setattr(
        audit_admin, "verified_admin_client",
        lambda *_args: (_ for _ in ()).throw(PermissionError("expired")),
    )
    monkeypatch.setattr(
        jarvis_errors, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )
    app.session_state["_jarvis_audit_export_pending"] = {"operation_id": "old"}
    app.session_state["_jarvis_audit_cursor_stack"] = [None, {"id": "old"}]
    app.run()

    assert not app.exception
    assert "_jarvis_audit_admin_session" not in app.session_state
    assert "_jarvis_audit_export_pending" not in app.session_state
    assert "_jarvis_audit_cursor_stack" not in app.session_state
    assert reports and reports[0][1]["operation"] == "audit_admin_session_validation"
    assert any("érvénytelen vagy lejárt" in item.value for item in app.error)


def test_audit_page_pagination_filters_integrity_and_empty_state(monkeypatch):
    calls = []
    cursor = {"created_at": "2026-11-24T17:00:00Z", "id": "event-0"}
    pages = {
        None: {"events": _events(), "next_cursor": cursor},
        str(cursor): {"events": _events(), "next_cursor": None},
    }

    def fetch(_client, **kwargs):
        calls.append(kwargs)
        key = str(kwargs["cursor"]) if kwargs["cursor"] else None
        return pages[key]

    app = _prepare_audit_app(monkeypatch)
    _patch_verified_admin(monkeypatch)
    monkeypatch.setattr(audit_admin, "fetch_audit_page", fetch)
    monkeypatch.setattr(
        audit_admin, "verify_audit_integrity",
        lambda _client: {"ok": True, "total_entries": 1},
    )
    app.run()
    assert not app.exception
    assert app.dataframe
    assert calls[-1]["page_size"] == 100
    assert calls[-1]["module"] is None
    assert calls[-1]["operation_id"] is None

    app.button(key="jarvis_audit_next").click().run()
    assert app.session_state["_jarvis_audit_cursor_stack"] == [None, cursor]
    assert calls[-1]["cursor"] == cursor

    app.button(key="jarvis_audit_prev").click().run()
    assert app.session_state["_jarvis_audit_cursor_stack"] == [None]
    assert calls[-1]["cursor"] is None

    app.button(key="jarvis_audit_integrity_check").click().run()
    assert any("ellenőrzése sikeres" in item.value for item in app.success)

    app.text_input(key="jarvis_audit_module_filter").set_value(" dashboard ")
    app.text_input(key="jarvis_audit_operation_filter").set_value(" operation-1 ")
    app.run()
    assert calls[-1]["module"] == "dashboard"
    assert calls[-1]["operation_id"] == "operation-1"

    monkeypatch.setattr(
        audit_admin, "fetch_audit_page",
        lambda *_args, **_kwargs: {"events": [], "next_cursor": None},
    )
    app.run()
    assert any("nem található" in item.value for item in app.info)


def test_audit_page_database_failure_and_integrity_failure_are_reported(monkeypatch):
    import jarvis_errors

    reports = []
    app = _prepare_audit_app(monkeypatch)
    _patch_verified_admin(monkeypatch)
    monkeypatch.setattr(
        audit_admin, "fetch_audit_page",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("schema missing")),
    )
    monkeypatch.setattr(
        jarvis_errors, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )
    app.run()

    assert not app.exception
    assert any("auditnapló nem olvasható" in item.value for item in app.error)
    assert reports[-1][1]["operation"] == "audit_admin_read"

    monkeypatch.setattr(
        audit_admin, "fetch_audit_page",
        lambda *_args, **_kwargs: {"events": _events(), "next_cursor": None},
    )
    monkeypatch.setattr(
        audit_admin, "verify_audit_integrity",
        lambda *_args: {"ok": False, "invalid_hashes": 1, "missing_predecessors": 0,
                        "forks": 0, "disconnected_entries": 0},
    )
    app.run()
    app.button(key="jarvis_audit_integrity_check").click().run()
    assert any("nem igazolható" in item.value for item in app.error)

    monkeypatch.setattr(
        audit_admin, "verify_audit_integrity",
        lambda *_args: (_ for _ in ()).throw(OSError("rpc unavailable")),
    )
    app.button(key="jarvis_audit_integrity_check").click().run()
    assert any("nem futtatható le" in item.value for item in app.error)
    assert reports[-1][1]["operation"] == "audit_integrity_check"


def test_audit_csv_export_pending_and_success_are_audited(monkeypatch):
    import streamlit

    statuses = []
    app = _prepare_audit_app(monkeypatch)
    _patch_verified_admin(monkeypatch, page={"events": _events(), "next_cursor": None})
    monkeypatch.setattr(
        jarvis_common, "audit_event",
        lambda *_args, **kwargs: (statuses.append(kwargs["status"]) or True),
    )
    app.run()
    app.button(key="jarvis_audit_export_prepare").click().run()

    pending = app.session_state["_jarvis_audit_export_pending"]
    assert pending["actor_user_id"] == "admin-1"
    assert pending["rows"] == _events()
    assert statuses == ["pending"]

    monkeypatch.setattr(streamlit, "download_button", lambda *_args, **_kwargs: True)
    app.run()
    assert "_jarvis_audit_export_pending" not in app.session_state
    assert statuses == ["pending", "success"]


def test_audit_csv_export_fail_closed_when_pending_or_completion_audit_fails(monkeypatch):
    import streamlit
    import jarvis_errors

    reports = []
    statuses = []
    app = _prepare_audit_app(monkeypatch)
    _patch_verified_admin(monkeypatch, page={"events": _events(), "next_cursor": None})

    def audit(_client, **kwargs):
        statuses.append(kwargs["status"])
        return kwargs["status"] == "pending"

    monkeypatch.setattr(jarvis_common, "audit_event", audit)
    monkeypatch.setattr(
        jarvis_errors, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )
    app.run()
    app.button(key="jarvis_audit_export_prepare").click().run()
    assert statuses == ["pending"]

    monkeypatch.setattr(streamlit, "download_button", lambda *_args, **_kwargs: True)
    app.run()
    assert statuses == ["pending", "success", "unknown"]
    assert any("lezáró audit bizonytalan" in item.value for item in app.error)
    assert reports[-1][1]["operation"] == "audit_export_completion"


def test_audit_csv_export_expiry_is_blocked_and_pending_audit_failure_is_reported(monkeypatch):
    import jarvis_errors

    reports = []
    statuses = []
    app = _prepare_audit_app(monkeypatch)
    _patch_verified_admin(monkeypatch, page={"events": _events(), "next_cursor": None})
    monkeypatch.setattr(
        jarvis_common, "audit_event",
        lambda _client, **kwargs: (statuses.append(kwargs["status"]) or True),
    )
    monkeypatch.setattr(
        jarvis_errors, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )
    app.session_state["_jarvis_audit_export_pending"] = {
        "operation_id": "expired-op",
        "rows": _events(),
        "actor_user_id": "other-admin",
        "created_at": time.time() - 600,
        "page": 1,
    }
    app.run()

    assert "_jarvis_audit_export_pending" not in app.session_state
    assert statuses == ["blocked"]
    assert any("jóváhagyása lejárt" in item.value for item in app.warning)

    # A pending audit write failure must not create an export authorization.
    statuses.clear()
    monkeypatch.setattr(
        jarvis_common, "audit_event",
        lambda _client, **kwargs: (statuses.append(kwargs["status"]) or False),
    )
    app.run()
    app.button(key="jarvis_audit_export_prepare").click().run()
    assert statuses == ["pending"]
    assert "_jarvis_audit_export_pending" not in app.session_state
    assert any("pending auditbejegyzés nem menthető" in item.value for item in app.error)


def test_audit_admin_logout_cancels_pending_export_and_clears_admin_state(monkeypatch):
    statuses = []
    signed_out = []
    app = _prepare_audit_app(monkeypatch)
    _patch_verified_admin(monkeypatch, page={"events": _events(), "next_cursor": None})
    monkeypatch.setattr(
        jarvis_common, "audit_event",
        lambda _client, **kwargs: (statuses.append(kwargs["status"]) or True),
    )
    monkeypatch.setattr(
        audit_admin, "sign_out_audit_admin",
        lambda session: signed_out.append(session["user_id"]),
    )
    app.session_state["_jarvis_audit_export_pending"] = {
        "operation_id": "pending-op",
        "actor_user_id": "admin-1",
    }
    app.session_state["_jarvis_audit_cursor_stack"] = [None, {"id": "cursor"}]
    app.run()
    app.button(key="jarvis_audit_admin_logout").click().run()

    assert statuses == ["blocked"]
    assert signed_out == ["admin-1"]
    assert "_jarvis_audit_admin_session" not in app.session_state
    assert "_jarvis_audit_export_pending" not in app.session_state
    assert "_jarvis_audit_cursor_stack" not in app.session_state


def test_audit_admin_logout_reports_sign_out_failure_but_still_clears_session(monkeypatch):
    import jarvis_errors

    reports = []
    app = _prepare_audit_app(monkeypatch)
    _patch_verified_admin(monkeypatch)
    monkeypatch.setattr(
        audit_admin, "sign_out_audit_admin",
        lambda *_args: (_ for _ in ()).throw(OSError("sign out failed")),
    )
    monkeypatch.setattr(
        jarvis_errors, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )
    app.run()
    app.button(key="jarvis_audit_admin_logout").click().run()

    assert "_jarvis_audit_admin_session" not in app.session_state
    assert reports and reports[-1][1]["operation"] == "audit_admin_sign_out"
