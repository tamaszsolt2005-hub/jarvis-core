"""Behavioral tests for schema-tolerant, read-only Supabase retrieval."""
import ast
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "dashboard.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _load_function(name):
    node = next(
        item for item in TREE.body
        if isinstance(item, ast.FunctionDef) and item.name == name
    )
    module = ast.Module(body=[node], type_ignores=[])
    namespace = {"Any": Any, "pd": pd}
    exec(compile(module, str(ROOT / "dashboard.py"), "exec"), namespace)
    return namespace[name]


_safe_rows = _load_function("_safe_rows")
retrieve_context = _load_function("retrieve_context")


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, rows, calls):
        self.rows = rows
        self.calls = calls

    def select(self, columns):
        self.calls.append(("select", columns))
        return self

    def limit(self, count):
        self.calls.append(("limit", count))
        return self

    def execute(self):
        self.calls.append(("execute",))
        return FakeResponse(self.rows)


class FakeDB:
    def __init__(self, tables):
        self.tables = tables
        self.calls = []

    def table(self, name):
        self.calls.append(("table", name))
        return FakeQuery(self.tables.get(name, []), self.calls)


def test_lead_retrieval_handles_legacy_schema_and_filters_personal_fields():
    db = FakeDB({
        "leads": [{
            "id": "lead-1",
            "company_name": "Minta Kft.",
            "status": "new",
            "email": "private@example.com",
            "notes": "Személyes megjegyzés",
        }]
    })

    context, sources = retrieve_context(db, "Mutasd a leadeket")

    assert "Minta Kft." in context
    assert "private@example.com" not in context
    assert "Személyes megjegyzés" not in context
    assert "leadek" in sources
    assert ("select", "*") in db.calls


def test_read_query_is_bounded_and_does_not_call_mutation_methods():
    db = FakeDB({"leads": [{"id": "1", "company_name": "Minta", "status": "new"}]})

    _safe_rows(db, "leads", "*", 37)

    assert ("limit", 37) in db.calls
    assert not any(
        entry[0] in {"insert", "update", "upsert", "delete"}
        for entry in db.calls
    )


def test_empty_lead_table_returns_valid_context():
    db = FakeDB({"leads": []})

    context, sources = retrieve_context(db, "Lead áttekintés")

    assert "Összes lead: 0" in context
    assert sources == ["leadek"]
