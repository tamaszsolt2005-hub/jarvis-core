"""Isolated branch tests for consent-checked email delivery state transitions."""
from datetime import datetime, timezone

import pytest

import email_sender


def _lead(**changes):
    row = {
        "id": "lead-1", "email": "contact@example.test", "company_name": "Example Ltd",
        "website": "https://example.test", "status": "new", "consent_basis": "consent",
        "consent_confirmed_at": datetime.now(timezone.utc).isoformat(),
        "approved_to_contact": True, "opted_out": False, "reply_category": None,
        "last_inbound_message_id": None, "follow_up_count": 0,
    }
    row.update(changes)
    return row


class _Query:
    def __init__(self, db):
        self.db = db
        self.filters = []
        self.operation = "select"
        self.values = None
        self.returning = False

    def select(self, *_args, **_kwargs):
        self.returning = True
        return self

    def update(self, values):
        self.operation = "update"
        self.values = values
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def limit(self, _value):
        return self

    def execute(self):
        matches = [
            row for row in self.db.rows
            if all(row.get(key) == value for key, value in self.filters)
        ]
        if self.operation == "update":
            if self.db.lose_claim and self.values == {"status": "sending"}:
                return type("Result", (), {"data": []})()
            for row in matches:
                row.update(self.values)
            data = [{"id": row["id"]} for row in matches] if self.returning else []
            return type("Result", (), {"data": data})()
        return type("Result", (), {"data": [dict(row) for row in matches]})()


class _DB:
    def __init__(self, rows):
        self.rows = rows
        self.lose_claim = False

    def table(self, _name):
        return _Query(self)


def _configure(monkeypatch, db, *, send=None, audit=None):
    monkeypatch.setattr(email_sender, "_draft", lambda *_args, **_kwargs: ("Subject", "Body"))
    monkeypatch.setattr(email_sender, "send_email", send or (lambda *_args: "smtp-id"))
    monkeypatch.setattr(email_sender, "audit_event", audit or (lambda *_args, **_kwargs: True))
    monkeypatch.setattr(email_sender, "log_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(email_sender, "report_error", lambda *_args, **_kwargs: None)


def test_email_draft_uses_safe_fallbacks_for_empty_and_subject_only_generation(monkeypatch):
    monkeypatch.setattr(email_sender, "audit_company_website", lambda _url: "mock website facts")
    monkeypatch.setattr(email_sender, "get_secret", lambda _name, default=None: default)
    monkeypatch.setattr(email_sender, "generate_text", lambda _prompt: "")
    subject, body = email_sender._draft(_lead(), follow_up=False)
    assert subject == "Rövid szakmai bemutatkozás"
    assert "LEIRATKOZOM" in body

    monkeypatch.setattr(email_sender, "generate_text", lambda _prompt: "Egyedi tárgy")
    subject, body = email_sender._draft(_lead(), follow_up=True)
    assert subject == "Egyedi tárgy"
    assert body.startswith("Egyedi tárgy")
    assert "LEIRATKOZOM" in body


def test_email_sender_rejects_invalid_lead_and_lost_atomic_claim(monkeypatch):
    db = _DB([_lead(email="invalid")])
    _configure(monkeypatch, db, send=lambda *_args: pytest.fail("must not send"))
    assert email_sender._send_one(db, db.rows[0], False, datetime.now(timezone.utc)) is False
    assert db.rows[0]["status"] == "new"

    db = _DB([_lead()])
    db.lose_claim = True
    audits = []
    _configure(
        monkeypatch, db, send=lambda *_args: pytest.fail("must not send"),
        audit=lambda *args, **kwargs: audits.append(kwargs) or True,
    )
    assert email_sender._send_one(db, db.rows[0], False, datetime.now(timezone.utc)) is False
    assert db.rows[0]["status"] == "new"
    assert audits[0]["status"] == "blocked"


def test_email_sender_rechecks_consent_immediately_before_smtp(monkeypatch):
    db = _DB([_lead()])
    sent = []
    def revoke_during_draft(_lead, **_kwargs):
        db.rows[0]["opted_out"] = True
        return "Subject", "Body"
    monkeypatch.setattr(email_sender, "_draft", revoke_during_draft)
    _configure(monkeypatch, db, send=lambda *args: sent.append(args) or "smtp-id")

    assert email_sender._send_one(db, db.rows[0], False, datetime.now(timezone.utc)) is False
    assert sent == []
    assert db.rows[0]["status"] == "send_blocked"
    assert db.rows[0]["next_follow_up_at"] is None


def test_email_sender_pending_audit_failure_prevents_smtp_and_marks_error(monkeypatch):
    db = _DB([_lead()])
    sent = []
    statuses = []
    def audit(*_args, **kwargs):
        statuses.append(kwargs["status"])
        return False
    _configure(monkeypatch, db, send=lambda *args: sent.append(args), audit=audit)

    assert email_sender._send_one(db, db.rows[0], False, datetime.now(timezone.utc)) is False
    assert sent == []
    assert db.rows[0]["status"] == "send_error"
    assert statuses == ["pending", "failed"]


def test_email_sender_smtp_failure_is_reported_and_not_marked_as_sent(monkeypatch):
    db = _DB([_lead()])
    reports, audit_statuses = [], []
    def audit(*_args, **kwargs):
        audit_statuses.append(kwargs["status"])
        return True
    def fail_send(*_args):
        raise OSError("mock SMTP failure")
    monkeypatch.setattr(email_sender, "report_error", lambda error, **kwargs: reports.append((error, kwargs)))
    _configure(monkeypatch, db, send=fail_send, audit=audit)

    assert email_sender._send_one(db, db.rows[0], False, datetime.now(timezone.utc)) is False
    assert db.rows[0]["status"] == "send_error"
    assert audit_statuses == ["pending", "failed"]
    assert isinstance(reports[0][0], OSError)


def test_email_sender_success_records_delivery_and_followup_schedule(monkeypatch):
    db = _DB([_lead()])
    sent, audits = [], []
    _configure(
        monkeypatch, db,
        send=lambda *args: sent.append(args) or "smtp-id",
        audit=lambda *args, **kwargs: audits.append(kwargs) or True,
    )
    now = datetime.now(timezone.utc)

    assert email_sender._send_one(db, db.rows[0], False, now) is True
    assert sent == [("contact@example.test", "Subject", "Body")]
    assert db.rows[0]["status"] == "sent"
    assert db.rows[0]["last_message_id"] == "smtp-id"
    assert db.rows[0]["next_follow_up_at"] is not None
    assert [item["status"] for item in audits] == ["pending", "success"]


def test_email_sender_followup_limit_disables_next_schedule(monkeypatch):
    db = _DB([_lead(status="follow_up_sent", follow_up_count=1)])
    audits = []
    monkeypatch.setattr(email_sender, "env_int", lambda name, default, *_args: 1 if name == "MAX_FOLLOW_UPS" else default)
    _configure(
        monkeypatch, db,
        audit=lambda *args, **kwargs: audits.append(kwargs) or True,
    )
    now = datetime.now(timezone.utc)

    assert email_sender._send_one(db, db.rows[0], True, now) is True
    assert db.rows[0]["status"] == "follow_up_sent"
    assert db.rows[0]["follow_up_count"] == 2
    assert db.rows[0]["next_follow_up_at"] is None
