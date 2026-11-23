from types import SimpleNamespace

import pytest

import audit_admin
import jarvis_common


class InsertQuery:
    def __init__(self, db):
        self.db = db

    def insert(self, row):
        self.db.rows.append(row)
        return self

    def execute(self):
        return SimpleNamespace(data=[])


class InsertDB:
    def __init__(self):
        self.rows = []

    def table(self, _name):
        return InsertQuery(self)


def test_audit_event_records_verified_actor_user_id():
    db = InsertDB()
    ok = jarvis_common.audit_event(
        db,
        module="audit_admin",
        action="export_csv",
        status="pending",
        actor_user_id="10000000-0000-0000-0000-000000000001",
    )
    assert ok is True
    assert db.rows[0]["actor_user_id"] == "10000000-0000-0000-0000-000000000001"


def test_audit_event_rejects_invalid_actor_id_without_writing(monkeypatch):
    db = InsertDB()
    errors = []
    monkeypatch.setattr(jarvis_common, "report_error", lambda *args, **kwargs: errors.append(args))
    ok = jarvis_common.audit_event(
        db,
        module="audit_admin",
        action="export_csv",
        status="pending",
        actor_user_id="not-a-uuid",
    )
    assert ok is False
    assert db.rows == []
    assert errors


def test_fetch_audit_page_uses_bounded_composite_cursor(monkeypatch):
    calls = []
    expected = {"events": [{"id": "event-1"}], "next_cursor": {"created_at": "2026-11-23T00:00:00+00:00", "id": "event-1"}}
    monkeypatch.setattr(audit_admin, "get_audit_events_page", lambda client, **kwargs: calls.append(kwargs) or expected)
    result = audit_admin.fetch_audit_page(
        object(),
        module="email_sender",
        status="failed",
        operation_id="10000000-0000-0000-0000-000000000001",
        cursor={"created_at": "2026-11-22T00:00:00+00:00", "id": "10000000-0000-0000-0000-000000000001"},
        page_size=5000,
    )
    assert result == expected
    assert calls[0]["page_size"] == 100
    assert calls[0]["module"] == "email_sender"
    assert calls[0]["status"] == "failed"
