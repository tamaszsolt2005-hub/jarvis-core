from __future__ import annotations

import pytest

from jarvis_common import get_audit_events, get_audit_events_page


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, rows):
        self.rows = rows
        self.operations = []
        self.limit_value = None
        self.filters = []

    @property
    def not_(self):
        self.operations.append(("not",))
        return self

    def is_(self, field, value):
        self.operations.append(("is", field, value))
        return self

    def select(self, fields):
        self.operations.append(("select", fields))
        return self

    def order(self, field, desc=False):
        self.operations.append(("order", field, desc))
        return self

    def or_(self, expression):
        self.operations.append(("or", expression))
        return self

    def limit(self, value):
        self.limit_value = value
        self.operations.append(("limit", value))
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def execute(self):
        return _Result(self.rows[:self.limit_value])


class _DB:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def table(self, name):
        assert name == "logs"
        query = _Query(self.rows)
        self.queries.append(query)
        return query


def _row(index, timestamp="2026-11-23T08:00:00+00:00"):
    return {
        "id": f"00000000-0000-0000-0000-{index:012d}",
        "operation_id": "11111111-1111-1111-1111-111111111111",
        "created_at": timestamp,
        "module": "email_sender",
        "action": "send_email",
        "status": "success",
        "result": None,
        "error": None,
        "approved": True,
        "recipient": None,
        "subject": None,
        "delivery_id": None,
        "level": "info",
    }


def test_audit_page_returns_bounded_rows_and_stable_next_cursor():
    rows = [_row(5), _row(4), _row(3)]
    db = _DB(rows)

    page = get_audit_events_page(db, page_size=2, module="email_sender", status="success")

    assert page["events"] == rows[:2]
    assert page["next_cursor"] == {"created_at": rows[1]["created_at"], "id": rows[1]["id"]}
    query = db.queries[0]
    assert query.limit_value == 3
    assert ("order", "created_at", True) in query.operations
    assert ("order", "id", True) in query.operations
    assert query.filters == [("module", "email_sender"), ("status", "success")]


def test_audit_page_uses_composite_cursor_to_avoid_skipping_equal_timestamps():
    rows = [_row(5), _row(4), _row(3)]
    db = _DB(rows)
    cursor = {"created_at": rows[1]["created_at"], "id": rows[1]["id"]}

    get_audit_events(db, before_created_at=cursor["created_at"], before_id=cursor["id"])

    query_filter = next(item[1] for item in db.queries[0].operations if item[0] == "or")
    assert f"created_at.lt.{rows[1]['created_at']}" in query_filter
    assert f"id.lt.{rows[1]['id']}" in query_filter
    assert "created_at.eq." in query_filter


@pytest.mark.parametrize(
    ("created_at", "event_id"),
    [
        ("2026-11-23T08:00:00", "00000000-0000-0000-0000-000000000001"),
        ("not-a-timestamp", "00000000-0000-0000-0000-000000000001"),
        ("2026-11-23T08:00:00+00:00", "not-a-uuid"),
        (None, "00000000-0000-0000-0000-000000000001"),
        ("2026-11-23T08:00:00+00:00", None),
    ],
)
def test_audit_cursor_rejects_incomplete_or_invalid_values(created_at, event_id):
    db = _DB([])
    with pytest.raises(ValueError, match="cursor"):
        get_audit_events(db, before_created_at=created_at, before_id=event_id)
    assert db.queries == []


def test_audit_page_has_no_next_cursor_when_there_are_no_more_rows():
    rows = [_row(2), _row(1)]
    db = _DB(rows)

    page = get_audit_events_page(db, page_size=2)

    assert page == {"events": rows, "next_cursor": None}


def test_audit_page_caps_requested_page_size():
    db = _DB([_row(1)])

    get_audit_events_page(db, page_size=10000)

    assert db.queries[0].limit_value == 501
