"""Structured audit-log tests; no live Supabase or email access."""
import uuid

import jarvis_common


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class InsertQuery:
    def __init__(self, db):
        self.db = db

    def insert(self, row):
        self.db.inserted.append(row)
        return self

    def execute(self):
        if self.db.fail:
            raise RuntimeError("password=do-not-log-this")
        return FakeResult()


class FilterNamespace:
    def __init__(self, query):
        self.query = query

    def is_(self, field, value):
        self.query.filters.append(("not_is", field, value))
        return self.query


class SelectQuery:
    def __init__(self, db):
        self.db = db
        self.filters = []
        self.selection = None
        self.sorting = None
        self.sortings = []
        self.limit_value = None
        self.not_ = FilterNamespace(self)

    def select(self, fields):
        self.selection = fields
        return self

    def order(self, field, desc=False):
        self.sorting = (field, desc)
        self.sortings.append((field, desc))
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def eq(self, field, value):
        self.filters.append(("eq", field, value))
        return self

    def execute(self):
        self.db.last_query = self
        return FakeResult(self.db.rows)


class FakeDB:
    def __init__(self, fail=False, rows=None):
        self.fail = fail
        self.inserted = []
        self.rows = rows
        self.last_query = None

    def table(self, name):
        assert name == "logs"
        return InsertQuery(self) if self.rows is None else SelectQuery(self)


def test_audit_event_writes_structured_fields_and_uuid():
    db = FakeDB(rows=None)
    ok = jarvis_common.audit_event(
        db,
        module="chat_email",
        action="send_approved_email",
        status="success",
        approved=True,
        recipient="customer@example.com",
        subject="Project update",
        delivery_id="<message-123@example.com>",
        result={"smtp_accepted": True},
    )
    assert ok is True
    row = db.inserted[0]
    assert str(uuid.UUID(row["operation_id"])) == row["operation_id"]
    assert row["module"] == "chat_email"
    assert row["action"] == "send_approved_email"
    assert row["status"] == "success"
    assert row["approved"] is True
    assert row["recipient"] == "customer@example.com"
    assert row["subject"] == "Project update"
    assert row["delivery_id"] == "<message-123@example.com>"
    assert row["result"] == {"smtp_accepted": True}
    assert row["created_at"].endswith("+00:00")


def test_audit_event_reuses_valid_operation_id_and_redacts_secrets():
    db = FakeDB(rows=None)
    operation_id = str(uuid.uuid4())
    assert jarvis_common.audit_event(
        db,
        module="email_sender",
        action="send_first_contact_email",
        status="failed",
        operation_id=operation_id,
        error="SMTP failed password=super-secret-value",
        subject="token=secret-subject",
    )
    row = db.inserted[0]
    assert row["operation_id"] == operation_id
    assert "super-secret-value" not in row["error"]
    assert "secret-subject" not in row["subject"]


def test_audit_event_sanitizes_result_values():
    db = FakeDB(rows=None)
    assert jarvis_common.audit_event(
        db, module="test", action="test_result", status="success",
        result={"details": "api_key=hidden-value", "api_key": "hidden-by-field-name", "count": 2},
    )
    assert db.inserted[0]["result"]["details"] != "api_key=hidden-value"
    assert "hidden-value" not in str(db.inserted[0]["result"])
    assert db.inserted[0]["result"]["api_key"] == "[REDACTED]"
    assert "hidden-by-field-name" not in str(db.inserted[0]["result"])


def test_audit_event_returns_false_when_persistence_fails(caplog):
    db = FakeDB(fail=True, rows=None)
    assert jarvis_common.audit_event(
        db, module="tasks", action="task_create", status="pending"
    ) is False
    assert "do-not-log-this" not in caplog.text


def test_get_audit_events_filters_and_returns_newest_first():
    rows = [{"operation_id": "op-1", "action": "send_approved_email"}]
    db = FakeDB(rows=rows)
    result = jarvis_common.get_audit_events(
        db, limit=5000, module="chat_email",
        action="send_approved_email", status="success",
        operation_id="op-1",
    )
    assert result == rows
    query = db.last_query
    assert query.sortings == [("created_at", True), ("id", True)]
    assert query.limit_value == 1000
    assert ("not_is", "action", "null") in query.filters
    assert ("eq", "module", "chat_email") in query.filters
    assert ("eq", "action", "send_approved_email") in query.filters
    assert ("eq", "status", "success") in query.filters
    assert ("eq", "operation_id", "op-1") in query.filters


def test_get_audit_events_clamps_small_limit():
    db = FakeDB(rows=[])
    jarvis_common.get_audit_events(db, limit=0)
    assert db.last_query.limit_value == 1
