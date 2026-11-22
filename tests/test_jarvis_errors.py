"""Tests for centralized, secret-safe error reporting."""
import logging

from jarvis_errors import report_error, sanitize_log_text


class FakeQuery:
    def __init__(self, sink, should_fail=False):
        self.sink = sink
        self.should_fail = should_fail

    def insert(self, payload):
        self.sink.append(payload)
        return self

    def execute(self):
        if self.should_fail:
            raise RuntimeError("password=secondary-secret")
        return self


class FakeDB:
    def __init__(self, should_fail=False):
        self.rows = []
        self.should_fail = should_fail

    def table(self, name):
        assert name == "logs"
        return FakeQuery(self.rows, self.should_fail)


def test_sanitize_log_text_redacts_named_credentials():
    value = "api_key=abc123 password: hunter2 Authorization: Bearer tokenvalue"
    safe = sanitize_log_text(value)
    assert "abc123" not in safe
    assert "hunter2" not in safe
    assert "tokenvalue" not in safe
    assert safe.count("[REDACTED]") >= 3


def test_report_error_writes_timestamp_operation_and_severity():
    db = FakeDB()
    message = report_error(
        RuntimeError("request failed"),
        module="email_sender",
        operation="smtp_send",
        severity="critical",
        db=db,
    )
    assert len(db.rows) == 1
    row = db.rows[0]
    assert row["module"] == "email_sender"
    assert row["level"] == "critical"
    assert "timestamp=" in row["message"]
    assert "operation=smtp_send" in row["message"]
    assert "RuntimeError: request failed" in row["message"]
    assert message == row["message"]


def test_report_error_redacts_exception_secrets():
    db = FakeDB()
    report_error(
        RuntimeError("SMTP failed password=do-not-log-this"),
        module="email_sender",
        operation="connect",
        db=db,
    )
    assert "do-not-log-this" not in db.rows[0]["message"]
    assert "[REDACTED]" in db.rows[0]["message"]


def test_report_error_falls_back_without_raising_when_database_logging_fails(caplog):
    db = FakeDB(should_fail=True)
    with caplog.at_level(logging.ERROR, logger="jarvis"):
        report_error(
            RuntimeError("primary failure"),
            module="dashboard",
            operation="chat_request",
            db=db,
        )
    assert "Supabase error logging failed" in caplog.text
    assert "secondary-secret" not in caplog.text


def test_invalid_severity_defaults_to_error():
    db = FakeDB()
    report_error(RuntimeError("failure"), module="test", operation="run", severity="debug", db=db)
    assert db.rows[0]["level"] == "error"



def test_sanitize_redacts_short_configured_secret_and_json_fields(monkeypatch):
    monkeypatch.setenv("JARVIS_TEST_API_TOKEN", "s3cr")
    safe = sanitize_log_text('{"client_secret":"json-secret","note":"s3cr"}')
    assert "json-secret" not in safe
    assert "s3cr" not in safe


def test_sanitize_redacts_query_credentials_and_common_key_prefixes():
    safe = sanitize_log_text(
        "https://example.test/?access_token=query-secret "
        "key=sk-abcdefghijklmnopqr"
    )
    assert "query-secret" not in safe
    assert "sk-abcdefghijklmnopqr" not in safe
