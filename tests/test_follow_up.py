import pytest
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
    valid = _lead(consent_confirmed_at=(now - timedelta(seconds=1)).isoformat())
    assert follow_up._eligible_for_follow_up(valid, now)
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
        if self.operation == "update":
            self.returning = True
        else:
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
    monkeypatch.setattr(
        follow_up, "generate_text",
        lambda _prompt: "mock follow-up body" if draft is None else draft(),
    )
    monkeypatch.setattr(follow_up, "send_email", (lambda *_args: "mock-id") if send is None else send)
    monkeypatch.setattr(follow_up, "audit_event", (lambda *_args, **_kwargs: True) if audit is None else audit)
    monkeypatch.setattr(follow_up, "log_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(follow_up, "report_error", lambda *_args, **_kwargs: None)
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
    db = _DB([_lead()])

    def fail_send(*_args):
        raise OSError("mock SMTP outcome unknown")

    _configure_run(monkeypatch, db, send=fail_send)
    follow_up._run()

    assert db.rows[0]["status"] == "followup_unknown"
    assert db.rows[0]["next_follow_up_at"] is None


def test_draft_failure_before_smtp_restores_eligible_status(monkeypatch):
    db = _DB([_lead()])

    def fail_draft():
        raise RuntimeError("mock generation failure")

    _configure_run(monkeypatch, db, draft=fail_draft)
    follow_up._run()

    assert db.rows[0]["status"] == "sent"


def test_pending_audit_failure_prevents_smtp_and_restores_status(monkeypatch):
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


def test_follow_up_feature_gate_skips_database_access(monkeypatch, capsys):
    monkeypatch.setattr(follow_up, "EMAIL_DELIVERY_ENABLED", False)
    monkeypatch.setattr(
        follow_up, "get_supabase",
        lambda: pytest.fail("disabled follow-up must not initialize the database"),
    )
    follow_up._run()
    assert "nem kerül kiküldésre" in capsys.readouterr().out


def test_follow_up_rechecks_opt_out_after_claim_and_blocks_delivery(monkeypatch):
    class RevokingQuery(_Query):
        def execute(self):
            result = super().execute()
            if self.operation == "update" and self.values == {"status": "followup_sending"}:
                self.db.rows[0]["opted_out"] = True
            return result

    class RevokingDB(_DB):
        def table(self, _name):
            return RevokingQuery(self)

    db = RevokingDB([_lead()])
    sent = []
    _configure_run(monkeypatch, db, send=lambda *args: sent.append(args) or "smtp-id")
    follow_up._run()
    assert sent == []
    assert db.rows[0]["status"] == "followup_blocked"
    assert db.rows[0]["next_follow_up_at"] is None


def test_follow_up_unknown_delivery_when_post_smtp_state_update_returns_no_row(monkeypatch):
    class LostCompletionQuery(_Query):
        def execute(self):
            if self.operation == "update" and self.values and self.values.get("status") == "followed_up":
                return _Result([])
            return super().execute()

    class LostCompletionDB(_DB):
        def table(self, _name):
            return LostCompletionQuery(self)

    db = LostCompletionDB([_lead()])
    audits, reports = [], []
    _configure_run(
        monkeypatch, db,
        audit=lambda *args, **kwargs: audits.append(kwargs) or True,
    )
    monkeypatch.setattr(follow_up, "report_error", lambda error, **kwargs: reports.append((error, kwargs)))
    follow_up._run()

    assert db.rows[0]["status"] == "followup_unknown"
    assert [item["status"] for item in audits] == ["pending", "unknown"]
    assert reports[0][1]["operation"] == "send_follow_up"


def test_follow_up_success_audit_failure_keeps_completed_delivery_non_sendable(monkeypatch):
    db = _DB([_lead()])
    statuses = []
    _configure_run(
        monkeypatch, db,
        audit=lambda *args, **kwargs: statuses.append(kwargs["status"]) and False
        if kwargs["status"] == "success" else statuses.append(kwargs["status"]) or True,
    )
    follow_up._run()
    assert db.rows[0]["status"] == "followed_up"
    assert statuses == ["pending", "success", "unknown"]


def test_follow_up_recovery_failure_is_reported_critical(monkeypatch):
    class RecoveryFailureQuery(_Query):
        def execute(self):
            if self.operation == "update" and self.values == {"status": "sent"}:
                raise OSError("mock recovery failure")
            return super().execute()

    class RecoveryFailureDB(_DB):
        def table(self, _name):
            return RecoveryFailureQuery(self)

    db = RecoveryFailureDB([_lead()])
    reports = []
    _configure_run(
        monkeypatch, db,
        audit=lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(follow_up, "report_error", lambda error, **kwargs: reports.append((error, kwargs)))
    follow_up._run()
    assert any(item[1]["operation"] == "restore_lead_after_follow_up_failure"
               and item[1]["severity"] == "critical" for item in reports)


def test_follow_up_run_reports_and_reraises_batch_level_failure(monkeypatch):
    reports = []
    monkeypatch.setattr(
        follow_up, "_run",
        lambda: (_ for _ in ()).throw(ConnectionError("mock batch outage")),
    )
    monkeypatch.setattr(follow_up, "report_error", lambda error, **kwargs: reports.append((error, kwargs)))
    with pytest.raises(ConnectionError, match="mock batch outage"):
        follow_up.run()
    assert reports[0][1]["operation"] == "run_follow_up_batch"
    assert reports[0][1]["severity"] == "critical"
