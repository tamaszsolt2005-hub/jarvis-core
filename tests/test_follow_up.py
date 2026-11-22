from datetime import datetime, timedelta, timezone

import follow_up


def _lead(**overrides):
    now = datetime.now(timezone.utc)
    lead = {
        "id": "lead-1",
        "email": "contact@example.test",
        "company_name": "Példa Kft.",
        "status": "sent",
        "consent_basis": "consent",
        "approved_to_contact": True,
        "consent_confirmed_at": now.isoformat(),
        "opted_out": False,
        "reply_category": None,
        "last_inbound_message_id": None,
        "next_follow_up_at": (now - timedelta(days=1)).isoformat(),
        "follow_up_count": 0,
    }
    lead.update(overrides)
    return lead


def test_follow_up_requires_explicit_timestamped_consent_and_due_unreplied_lead():
    now = datetime.now(timezone.utc)
    assert follow_up._eligible_for_follow_up(_lead(), now)
    assert not follow_up._eligible_for_follow_up(_lead(consent_basis="legitimate_interest"), now)
    assert not follow_up._eligible_for_follow_up(_lead(approved_to_contact=False), now)
    assert not follow_up._eligible_for_follow_up(_lead(opted_out=True), now)
    assert not follow_up._eligible_for_follow_up(_lead(reply_category="reply"), now)
    assert not follow_up._eligible_for_follow_up(_lead(last_inbound_message_id="<reply>"), now)
    assert not follow_up._eligible_for_follow_up(_lead(consent_confirmed_at="invalid"), now)
    assert not follow_up._eligible_for_follow_up(_lead(next_follow_up_at="invalid"), now)
    assert not follow_up._eligible_for_follow_up(_lead(follow_up_count=1), now)
    assert not follow_up._eligible_for_follow_up(
        _lead(next_follow_up_at=(now + timedelta(days=1)).isoformat()), now
    )


class _Result:
    def __init__(self, data=None):
        self.data = data or []


class _Query:
    def __init__(self, db):
        self.db = db
        self.filters = []
        self.operation = "select"
        self.values = None
        self.returning = False

    def select(self, _columns):
        self.operation = "select"
        return self

    def limit(self, _limit):
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def update(self, values):
        self.operation = "update"
        self.values = values
        return self

    def execute(self):
        matches = [
            row for row in self.db.rows
            if all(row.get(key) == value for key, value in self.filters)
        ]
        if self.operation == "update":
            for row in matches:
                row.update(self.values)
            return _Result([{"id": row["id"]} for row in matches] if self.returning else [])
        return _Result([dict(row) for row in matches])

    def __getattribute__(self, name):
        if name == "select":
            return object.__getattribute__(self, name)
        return object.__getattribute__(self, name)


# Mark update(...).select(...) as a returning update without changing select reads.
_original_query_select = _Query.select
def _select(self, columns):
    if self.operation == "update":
        self.returning = True
    return _original_query_select(self, columns)
_Query.select = _select


class _DB:
    def __init__(self, rows):
        self.rows = rows

    def table(self, _name):
        return _Query(self)


def _configure_run(monkeypatch, db, *, send=None, draft=None, audit=None):
    monkeypatch.setattr(follow_up, "EMAIL_DELIVERY_ENABLED", True)
    monkeypatch.setattr(follow_up, "env_bool", lambda _name, default=False: True)
    monkeypatch.setattr(follow_up, "env_int", lambda _name, default, *_args: default)
    monkeypatch.setattr(follow_up, "get_supabase", lambda: db)
    monkeypatch.setattr(follow_up, "generate_text", lambda _prompt: "mock follow-up body" if draft is None else draft())
    monkeypatch.setattr(follow_up, "send_email", (lambda *_args: "mock-id") if send is None else send)
    monkeypatch.setattr(follow_up, "audit_event", (lambda *_args, **_kwargs: True) if audit is None else audit)
    monkeypatch.setattr(follow_up, "log_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(follow_up.time, "sleep", lambda *_args: None)


def test_follow_up_success_claims_once_and_records_completion(monkeypatch):
    db = _DB([_lead()])
    sent = []
    _configure_run(monkeypatch, db, send=lambda *args: sent.append(args) or "smtp-id")

    follow_up._run()

    assert len(sent) == 1
    assert db.rows[0]["status"] == "followed_up"
    assert db.rows[0]["follow_up_count"] == 1
    assert db.rows[0]["next_follow_up_at"] is None


def test_follow_up_does_not_send_without_consent(monkeypatch):
    db = _DB([_lead(approved_to_contact=False)])
    _configure_run(monkeypatch, db, send=lambda *_args: pytest.fail("must not send"))
    follow_up._run()
    assert db.rows[0]["status"] == "sent"


def test_uncertain_smtp_failure_is_not_reset_to_sendable_status(monkeypatch):
    import pytest

    db = _DB([_lead()])
    def fail_send(*_args):
        raise OSError("mock SMTP outcome unknown")
    _configure_run(monkeypatch, db, send=fail_send)

    follow_up._run()

    assert db.rows[0]["status"] == "followup_unknown"
    assert db.rows[0]["next_follow_up_at"] is None


def test_draft_failure_before_smtp_restores_eligible_status(monkeypatch):
    import pytest

    db = _DB([_lead()])
    def fail_draft():
        raise RuntimeError("mock generation failure")
    _configure_run(monkeypatch, db, draft=fail_draft)

    follow_up._run()

    assert db.rows[0]["status"] == "sent"


def test_pending_audit_failure_prevents_smtp_and_restores_status(monkeypatch):
    import pytest

    db = _DB([_lead()])
    sent = []
    _configure_run(
        monkeypatch, db,
        send=lambda *args: sent.append(args),
        audit=lambda *_args, **_kwargs: False,
    )

    follow_up._run()

    assert sent == []
    assert db.rows[0]["status"] == "sent"
