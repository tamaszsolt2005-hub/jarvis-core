"""Critical workflow regressions; all persistence and external transports are mocked.

These tests deliberately avoid live Supabase, IMAP, SMTP, and production records.
"""
from datetime import datetime, timezone

import pytest

import email_sender
import jarvis_common
import lead_gen
import task_actions


class Result:
    def __init__(self, data=None):
        self.data = data or []


class SenderQuery:
    def __init__(self, db):
        self.db = db
        self.operation = None
        self.payload = None
        self.filters = {}

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def select(self, _fields):
        if self.operation is None:
            self.operation = "select"
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def execute(self):
        if self.operation == "select":
            return Result([{
                "id": "lead-1",
                "status": "sending",
                "consent_basis": "consent",
                "approved_to_contact": True,
                "opted_out": False,
                "last_inbound_message_id": None,
            }])
        self.db.updates.append(self.payload)
        if self.payload and self.payload.get("status") == "sending":
            return Result([{"id": "lead-1"}])
        return Result([])


class SenderDB:
    def __init__(self):
        self.updates = []

    def table(self, name):
        assert name == "leads"
        return SenderQuery(self)


def _approved_lead():
    return {
        "id": "lead-1",
        "email": "person@example.test",
        "company_name": "Example Ltd",
        "status": "new",
        "consent_basis": "consent",
        "approved_to_contact": True,
        "opted_out": False,
    }


def test_sender_does_not_call_smtp_when_pending_audit_cannot_be_saved(monkeypatch):
    db = SenderDB()
    sent = []
    reported = []

    monkeypatch.setattr(email_sender, "_draft", lambda *_args, **_kwargs: ("Subject", "Body"))
    monkeypatch.setattr(email_sender, "audit_event", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(email_sender, "send_email", lambda *args: sent.append(args))
    monkeypatch.setattr(
        email_sender, "report_error",
        lambda error, **kwargs: reported.append((error, kwargs)),
    )

    result = email_sender._send_one(db, _approved_lead(), False, datetime.now(timezone.utc))

    assert result is False
    assert sent == []
    assert any(update and update.get("status") == "send_error" for update in db.updates)
    assert reported
    assert reported[0][1]["module"] == "email_sender"


def test_sender_does_not_draft_or_send_when_atomic_claim_is_lost(monkeypatch):
    class LostClaimQuery(SenderQuery):
        def execute(self):
            return Result([])

    class LostClaimDB:
        def table(self, name):
            assert name == "leads"
            return LostClaimQuery(self)

    monkeypatch.setattr(
        email_sender, "_draft",
        lambda *_args, **_kwargs: pytest.fail("Draft must not be generated without a claim"),
    )
    monkeypatch.setattr(
        email_sender, "send_email",
        lambda *_args: pytest.fail("SMTP must not be called without a claim"),
    )
    monkeypatch.setattr(email_sender, "audit_event", lambda *_args, **_kwargs: True)

    assert email_sender._send_one(
        LostClaimDB(), _approved_lead(), False, datetime.now(timezone.utc)
    ) is False


def test_task_database_write_failure_is_reported_and_original_error_reraised(monkeypatch):
    database_error = RuntimeError("mock database write failure")
    reports = []

    class BrokenQuery:
        def insert(self, _payload):
            return self

        def execute(self):
            raise database_error

    class BrokenDB:
        def table(self, name):
            assert name == "tasks"
            return BrokenQuery()

    monkeypatch.setattr(task_actions, "audit_event", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        task_actions, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )

    with pytest.raises(RuntimeError) as caught:
        task_actions.execute_task_action(
            BrokenDB(),
            {"type": "create", "title": "Mock task", "priority": "normal"},
            approved=True,
        )

    assert caught.value is database_error
    assert len(reports) == 1
    assert reports[0][0] is database_error
    assert reports[0][1]["module"] == "task_actions"
    assert reports[0][1]["severity"] == "critical"


def test_database_read_failure_does_not_break_independent_lead_and_task_logic(monkeypatch):
    reports = []

    class BrokenDB:
        def table(self, _name):
            raise RuntimeError("mock database unavailable")

    monkeypatch.setattr(
        jarvis_common, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )

    assert jarvis_common.get_setting(BrokenDB(), "theme", default="light") == "light"
    assert len(reports) == 1
    assert reports[0][1]["operation"] == "read_setting:theme"

    valid_row = {
        "company_name": "Example Ltd",
        "email": "contact@example.test",
        "consent_basis": "consent",
        "approved_to_contact": "yes",
        "consent_confirmed_at": "2026-11-20T10:00:00+00:00",
    }
    assert lead_gen._validated_import_row(valid_row)["email"] == "contact@example.test"
    assert task_actions.parse_task_command("Új feladat: Regressziós ellenőrzés")["type"] == "create"
