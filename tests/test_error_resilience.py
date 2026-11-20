"""Cross-module resilience regressions; all external services are mocked."""
import logging

import pytest

import email_inbox
import email_utils
import jarvis_common


class FakeResult:
    data = []


class FakeInsert:
    def __init__(self, captured):
        self.captured = captured

    def insert(self, payload):
        self.captured.append(payload)
        return self

    def execute(self):
        return FakeResult()


class FakeDB:
    def __init__(self):
        self.rows = []

    def table(self, name):
        assert name == "logs"
        return FakeInsert(self.rows)


def test_log_event_redacts_credentials_before_database_write():
    db = FakeDB()
    jarvis_common.log_event(
        db, "test", "SMTP failed: password=top-secret-value; bearer abcdefghijklmnop", "error"
    )
    assert len(db.rows) == 1
    message = db.rows[0]["message"]
    assert "top-secret-value" not in message
    assert "abcdefghijklmnop" not in message
    assert "[REDACTED]" in message


def test_log_event_uses_supported_severity_and_sanitizes_module():
    db = FakeDB()
    jarvis_common.log_event(db, "module api_key=secret123", "operation completed", "critical")
    assert db.rows[0]["level"] == "critical"
    assert "secret123" not in db.rows[0]["module"]


def test_log_event_database_failure_falls_back_to_local_logger(caplog):
    class BrokenDB:
        def table(self, _name):
            raise RuntimeError("password=hidden-secondary")

    with caplog.at_level(logging.ERROR, logger="jarvis"):
        jarvis_common.log_event(BrokenDB(), "test", "event")
    assert "Supabase error logging failed" in caplog.text
    assert "hidden-secondary" not in caplog.text


def test_email_delivery_disabled_fails_closed_without_smtp(monkeypatch):
    monkeypatch.setattr(email_utils, "EMAIL_DELIVERY_ENABLED", False)

    def forbidden_smtp(*args, **kwargs):
        pytest.fail("SMTP must not be opened when delivery is disabled")

    monkeypatch.setattr(email_utils.smtplib, "SMTP", forbidden_smtp)
    with pytest.raises(RuntimeError, match="letiltva"):
        email_utils.send_email("test@example.com", "Test", "Body")


def test_inbox_failure_is_reported_and_original_exception_is_reraised(monkeypatch):
    original = RuntimeError("IMAP unavailable")
    reports = []

    def fail():
        raise original

    monkeypatch.setattr(email_inbox, "_run", fail)
    monkeypatch.setattr(
        email_inbox, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )

    with pytest.raises(RuntimeError, match="IMAP unavailable") as caught:
        email_inbox.run()

    assert caught.value is original
    assert len(reports) == 1
    assert reports[0][0] is original
    assert reports[0][1]["module"] == "email_inbox"
    assert reports[0][1]["operation"] == "process_inbox"
    assert reports[0][1]["severity"] == "error"


def test_inbox_uid_checkpoint_rejects_non_numeric_uid_without_advancing():
    with pytest.raises(ValueError):
        email_inbox._uids_to_process(
            [b"100", b"not-a-number"],
            {"uidvalidity": "77", "last_uid": 99},
            "77",
        )
