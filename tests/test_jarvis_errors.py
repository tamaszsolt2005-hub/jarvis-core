"""Tests for centralized, secret-safe error reporting."""
import logging
import pytest

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


def test_report_error_populates_structured_error_and_timestamp_columns():
    db = FakeDB()
    report_error(
        RuntimeError("database unavailable password=do-not-store-this"),
        module="stats",
        operation="load_statistics",
        severity="critical",
        db=db,
    )
    row = db.rows[0]
    assert row["created_at"].endswith("+00:00")
    assert row["error"].startswith("RuntimeError: database unavailable")
    assert "do-not-store-this" not in row["error"]
    assert "operation=load_statistics" in row["message"]


def test_sanitizer_redacts_quoted_password_with_spaces_and_basic_auth():
    safe = sanitize_log_text(
        'request failed password="two words are secret" '
        'Authorization: Basic dXNlcjpwYXNzd29yZA=='
    )
    assert "two words are secret" not in safe
    assert "dXNlcjpwYXNzd29yZA==" not in safe
    assert "[REDACTED]" in safe


def test_only_credential_named_streamlit_values_are_registered():
    from jarvis_errors import register_secret_value

    register_secret_value("visible-model-name", name="GEMINI_MODEL")
    register_secret_value("private-config-token", name="GEMINI_API_KEY")
    safe = sanitize_log_text("model=visible-model-name key=private-config-token")
    assert "visible-model-name" in safe
    assert "private-config-token" not in safe

def test_report_error_falls_back_to_legacy_logs_columns_when_error_column_is_missing():
    class LegacySchemaQuery:
        def __init__(self, rows, payload):
            self.rows = rows
            self.payload = payload

        def execute(self):
            if "error" in self.payload:
                raise RuntimeError("PGRST204: Could not find the 'error' column of 'logs' in the schema cache")
            self.rows.append(self.payload)
            return self

    class LegacySchemaDB:
        def __init__(self):
            self.rows = []

        def table(self, _name):
            class Table:
                def __init__(self, rows):
                    self.rows = rows

                def insert(self, payload):
                    return LegacySchemaQuery(self.rows, payload)

            return Table(self.rows)

    db = LegacySchemaDB()
    message = report_error(
        RuntimeError("lead research failed"),
        module="global_lead_research_job",
        operation="daily_global_research",
        severity="critical",
        db=db,
    )

    assert len(db.rows) == 1
    row = db.rows[0]
    assert set(row) == {"module", "level", "message", "created_at"}
    assert row["module"] == "global_lead_research_job"
    assert row["level"] == "critical"
    assert "operation=daily_global_research" in row["message"]
    assert "RuntimeError: lead research failed" in row["message"]
    assert row["message"] == message



from jarvis_errors import classify_error, user_facing_error


@pytest.mark.parametrize(
    ("error", "category", "retryable"),
    [
        (RuntimeError("Hiányzó beállítás: GEMINI_API_KEY"), "missing_configuration", False),
        (ValueError("Invalid URL scheme"), "invalid_configuration", False),
        (PermissionError("RLS denied"), "permission_denied", False),
        (type("Unauthorized", (Exception,), {"code": 401})("invalid credentials"), "authentication_failed", False),
        (type("Quota", (Exception,), {"code": 429})("RESOURCE_EXHAUSTED"), "rate_limited", True),
        (ConnectionError("connection reset"), "network_error", True),
        (TimeoutError("request timed out"), "timeout", True),
        (type("Unavailable", (Exception,), {"code": 503})("unavailable"), "service_unavailable", True),
        (type("BadRequest", (Exception,), {"code": 400, "status": "INVALID_ARGUMENT"})("bad request"), "invalid_request", False),
        (type("GeminiQuotaError", (Exception,), {"code": 429, "status": "RESOURCE_EXHAUSTED"})("quota"), "rate_limited", True),
        (type("GeminiUnavailableError", (Exception,), {"code": 503, "status": "UNAVAILABLE"})("temporarily unavailable"), "service_unavailable", True),
        (type("GeminiDeadlineError", (Exception,), {"code": 504, "status": "DEADLINE_EXCEEDED"})("deadline exceeded"), "timeout", True),
        (type("GeminiPermissionError", (Exception,), {"code": 403, "status": "PERMISSION_DENIED"})("denied"), "permission_denied", False),
        (type("GeminiAPIKeyError", (Exception,), {"code": 400, "status": "INVALID_ARGUMENT"})("API_KEY_INVALID: API key not valid"), "authentication_failed", False),
        (type("GeminiInternalError", (Exception,), {"code": 500, "status": "INTERNAL"})("internal server error"), "service_unavailable", True),
    ],
)
def test_classify_error_categories(error, category, retryable):
    result = classify_error(error)
    assert result["category"] == category
    assert result["retryable"] is retryable
    assert result["user_message"]


def test_user_facing_error_never_exposes_provider_secret():
    error = RuntimeError("request failed api_key=super-secret")
    message = user_facing_error(error)
    assert "super-secret" not in message
    assert "Váratlan hiba" in message



def test_classify_audit_log_write_failure_as_fail_closed():
    error = RuntimeError("Az e-mailt nem küldtem el: az auditnapló nem írható.")
    result = classify_error(error)
    assert result["category"] == "audit_unavailable"
    assert result["retryable"] is False
    assert "auditnapló nem írható" in user_facing_error(error)



def test_provider_error_code_is_not_echoed_when_it_is_not_a_safe_status():
    error = type("ProviderError", (Exception,), {"code": "secret=do-not-show"})("provider failed")
    result = classify_error(error)
    assert result["code"] is None
    assert "do-not-show" not in user_facing_error(error)


def test_provider_api_key_error_body_is_sanitized_before_logging(caplog):
    error = RuntimeError("API_KEY_INVALID: x-goog-api-key: private-provider-key")
    with caplog.at_level(logging.ERROR, logger="jarvis"):
        report_error(error, module="gemini", operation="generate_content")
    assert "private-provider-key" not in caplog.text
