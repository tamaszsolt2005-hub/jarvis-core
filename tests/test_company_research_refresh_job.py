from copy import deepcopy
from types import SimpleNamespace

import pytest

from company_research_refresh_job import load_company_research_refresh_inputs


class Query:
    def __init__(self, db, table):
        self.db = db
        self.table_name = table
        self.filters = []
        self.orders = []
        self.bounds = (0, 999)

    def select(self, _columns):
        return self

    def order(self, field, desc=False):
        self.orders.append((field, desc))
        return self

    def in_(self, field, values):
        self.filters.append((field, set(values)))
        return self

    def range(self, start, end):
        self.bounds = (start, end)
        return self

    def execute(self):
        rows = deepcopy(self.db.tables[self.table_name])
        for field, values in self.filters:
            rows = [row for row in rows if row.get(field) in values]
        for field, desc in reversed(self.orders):
            rows.sort(key=lambda row: row.get(field) or "", reverse=desc)
        start, end = self.bounds
        return SimpleNamespace(data=rows[start:end + 1])


class FakeDB:
    def __init__(self):
        self.tables = {
            "leads": [
                {"id": "lead-a", "company_name": "Alpha"},
                {"id": "lead-b", "company_name": "Beta"},
                {"id": "lead-c", "company_name": "Gamma"},
            ],
            "company_research_snapshots": [
                {"lead_id": "lead-a", "snapshot_id": "a1", "researched_at": "2026-01-01", "dossier": {"version": 1}},
                {"lead_id": "lead-a", "snapshot_id": "a2", "researched_at": "2026-02-01", "dossier": {"version": 2}},
                {"lead_id": "lead-b", "snapshot_id": "b1", "researched_at": "2026-01-15", "dossier": {"version": 1}},
            ],
        }

    def table(self, name):
        return Query(self, name)


def test_loader_paginates_leads_and_selects_newest_snapshot_per_lead():
    leads, latest = load_company_research_refresh_inputs(
        FakeDB(), lead_page_size=2, snapshot_page_size=1, lead_chunk_size=1
    )
    assert [lead["id"] for lead in leads] == ["lead-a", "lead-b", "lead-c"]
    assert latest["lead-a"]["snapshot_id"] == "a2"
    assert latest["lead-b"]["snapshot_id"] == "b1"
    assert "lead-c" not in latest


@pytest.mark.parametrize("kwargs", [
    {"lead_page_size": 0},
    {"snapshot_page_size": 1001},
    {"lead_chunk_size": True},
])
def test_loader_validates_pagination_limits(kwargs):
    with pytest.raises(ValueError):
        load_company_research_refresh_inputs(FakeDB(), **kwargs)


def test_loader_fails_closed_on_unexpected_database_shape():
    class BadDB:
        def table(self, _name):
            return self

        def select(self, _columns):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def range(self, *_args):
            return self

        def execute(self):
            return SimpleNamespace(data=None)

    with pytest.raises(RuntimeError, match="Unexpected database response"):
        load_company_research_refresh_inputs(BadDB())
