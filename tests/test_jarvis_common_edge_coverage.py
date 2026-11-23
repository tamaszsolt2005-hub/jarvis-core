"""Edge coverage for shared logging, audit and settings helpers; database is in-memory."""
from types import SimpleNamespace

import jarvis_common


class _Query:
    def __init__(self, db, table):
        self.db = db
        self.table_name = table
        self.filters = []
        self.payload = None
        self.limit_value = None
        self.descending = None

    @property
    def not_(self):
        return self

    def select(self, *_args, **_kwargs):
        return self

    def insert(self, payload):
        self.payload = payload
        return self

    def upsert(self, payload):
        self.payload = payload
        return self

    def is_(self, key, value):
        # This is invoked through .not_.is_("action", "null"); all fake rows
        # represent non-null audit actions.
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def order(self, _key, desc=False):
        self.descending = desc
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def execute(self):
        if self.db.failure:
            raise OSError("mock database unavailable")
        if self.payload is not None:
            self.db.writes.append((self.table_name, self.payload))
            return SimpleNamespace(data=[])
        rows = self.db.rows.get(self.table_name, [])
        return SimpleNamespace(data=[
            row for row in rows
            if all(row.get(key) == value for key, value in self.filters)
        ][:self.limit_value])


class _DB:
    def __init__(self, rows=None, failure=False):
        self.rows = rows or {}
        self.failure = failure
        self.writes = []

    def table(self, name):
        return _Query(self, name)


def test_log_event_sanitizes_fields_and_normalizes_unknown_level():
    db = _DB()
    jarvis_common.log_event(db, "module\nwith-control", "token=super-secret", "nonsense")
    table, row = db.writes[0]
    assert table == "logs"
    assert row["level"] == "info"
    assert "\n" not in row["module"]
    assert "super-secret" not in row["message"]


def test_log_event_reports_persistence_failure_without_masking_caller(monkeypatch):
    reports = []
    monkeypatch.setattr(jarvis_common, "report_error", lambda error, **kwargs: reports.append((error, kwargs)))
    jarvis_common.log_event(_DB(failure=True), "module", "event")
    assert len(reports) == 1
    assert reports[0][1]["operation"] == "write_application_log"
    assert reports[0][1]["severity"] == "error"


def test_audit_event_sanitizes_metadata_and_nested_secrets():
    db = _DB()
    assert jarvis_common.audit_event(
        db, module="mailer", action="send", status="unexpected",
        operation_id="not-a-uuid", recipient="person@example.test",
        subject="Subject", delivery_id="smtp-1", approved=True,
        error=OSError("token=private"),
        result={"api_token": "private", "nested": [{"password": "secret", "count": 3}]},
        level="verbose",
    )
    row = db.writes[0][1]
    assert row["status"] == "unknown"
    assert row["level"] == "info"
    assert row["operation_id"]
    assert row["approved"] is True
    assert row["recipient"] == "person@example.test"
    assert row["result"]["api_token"] == "[REDACTED]"
    assert row["result"]["nested"][0]["password"] == "[REDACTED]"
    assert "private" not in str(row)


def test_audit_event_truncates_oversized_result_and_reports_write_failure(monkeypatch):
    db = _DB()
    assert jarvis_common.audit_event(
        db, module="test", action="large", status="success",
        result={"payloads": ["x" * 500 for _ in range(6)]},
    )
    assert db.writes[-1][1]["result"] == {"truncated": True}

    reports = []
    monkeypatch.setattr(jarvis_common, "report_error", lambda error, **kwargs: reports.append((error, kwargs)))
    assert not jarvis_common.audit_event(
        _DB(failure=True), module="test", action="failed", status="success",
    )
    assert reports[0][1]["severity"] == "critical"
    assert reports[0][1]["operation"] == "audit_persist:test:failed"


def test_get_audit_events_applies_filters_and_bounds_limit():
    db = _DB(rows={"logs": [
        {"action": "send", "module": "mailer", "status": "success"},
        {"action": "other", "module": "mailer", "status": "success"},
    ]})
    result = jarvis_common.get_audit_events(
        db, limit=5000, module="mailer", action="send", status="success",
    )
    assert result == [{"action": "send", "module": "mailer", "status": "success"}]


def test_get_audit_events_reports_read_failure_and_returns_empty(monkeypatch):
    reports = []
    monkeypatch.setattr(jarvis_common, "report_error", lambda error, **kwargs: reports.append((error, kwargs)))
    assert jarvis_common.get_audit_events(_DB(failure=True), module="mailer") == []
    assert reports[0][1]["operation"] == "query_audit_events"
    assert reports[0][1]["severity"] == "warning"


def test_settings_helpers_handle_missing_and_persist_values():
    db = _DB(rows={"settings": [{"key": "theme", "value": "dark"}]})
    assert jarvis_common.get_setting(db, "theme") == "dark"
    assert jarvis_common.get_setting(db, "missing", default="light") == "light"
    jarvis_common.set_setting(db, "theme", "light")
    assert db.writes[-1] == ("settings", {"key": "theme", "value": "light"})


def test_supabase_client_uses_service_role_then_anon_fallback(monkeypatch):
    captured = []
    monkeypatch.setattr(jarvis_common, "required_secret", lambda name: {
        "SUPABASE_URL": "https://example.supabase.test"
    }[name])
    monkeypatch.setattr(jarvis_common, "get_secret", lambda name: "service-role" if name == "SUPABASE_SERVICE_ROLE_KEY" else None)
    monkeypatch.setattr(jarvis_common, "create_client", lambda url, key: captured.append((url, key)) or "client")
    assert jarvis_common.get_supabase() == "client"
    assert captured == [("https://example.supabase.test", "service-role")]

    monkeypatch.setattr(jarvis_common, "get_secret", lambda _name: None)
    monkeypatch.setattr(
        jarvis_common, "required_secret",
        lambda name: {"SUPABASE_URL": "https://example.supabase.test", "SUPABASE_KEY": "anon-key"}[name],
    )
    assert jarvis_common.get_supabase() == "client"
    assert captured[-1] == ("https://example.supabase.test", "anon-key")


def test_gemini_client_and_legacy_model_names_use_supported_configuration(monkeypatch):
    captured = []
    monkeypatch.setattr(jarvis_common, "required_secret", lambda name: "gemini-test-key")
    monkeypatch.setattr(jarvis_common.genai, "Client", lambda **kwargs: captured.append(kwargs) or "gemini-client")
    assert jarvis_common.get_gemini_client() == "gemini-client"
    assert captured == [{"api_key": "gemini-test-key"}]

    monkeypatch.setattr(jarvis_common, "get_secret", lambda *_args: "gemini-2.5-pro")
    assert jarvis_common.get_model_name() == "gemini-3.8-flash"


def test_generate_text_swallows_status_callback_failure_and_uses_second_fallback(monkeypatch):
    monkeypatch.setattr(jarvis_common, "get_model_name", lambda: "gemini-3.5-flash")
    monkeypatch.setattr(jarvis_common, "env_int", lambda *_args, **_kwargs: 1)
    class Overloaded(Exception):
        code = 503
        status = "UNAVAILABLE"
    client = FakeClient([
        Overloaded("503 primary"), Overloaded("503 first fallback"), "recovered on second fallback",
    ])
    assert jarvis_common.generate_text(
        "hello", client, on_status=lambda _message: (_ for _ in ()).throw(RuntimeError("UI callback failed")),
        max_output_tokens=64,
    ) == "recovered on second fallback"
    assert client.models.model_calls == [
        "gemini-3.5-flash", "gemini-3.8-flash", "gemini-3.5-flash-lite"
    ]
    assert all(config.max_output_tokens == 128 for config in client.models.configs)


def test_generate_text_reraises_last_overload_when_all_fallbacks_fail(monkeypatch):
    monkeypatch.setattr(jarvis_common, "get_model_name", lambda: "gemini-3.5-flash")
    monkeypatch.setattr(jarvis_common, "env_int", lambda *_args, **_kwargs: 1)
    class Overloaded(Exception):
        code = 503
        status = "UNAVAILABLE"
    errors = [Overloaded("503 primary"), Overloaded("503 first fallback"), Overloaded("503 last fallback")]
    client = FakeClient(errors)
    with pytest.raises(Overloaded, match="last fallback"):
        jarvis_common.generate_text("hello", client)
    assert client.models.calls == 3


def test_conversation_history_stops_when_newest_turn_fills_exact_character_budget():
    line = "assistant: newest"
    result = jarvis_common.format_conversation_history(
        [("user", "older"), ("assistant", "newest")],
        max_chars=len(line), max_message_chars=100,
    )
    assert result == line
