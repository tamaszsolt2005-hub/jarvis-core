from datetime import date

from proactive_monitor import run_proactive_monitor


class Result:
    def __init__(self, data):
        self.data = data


class Query:
    def __init__(self, db, table):
        self.db, self.table_name = db, table
        self.key = None
        self.payload = None

    def select(self, _columns):
        return self

    def eq(self, field, value):
        if field == "key":
            self.key = value
        return self

    def limit(self, _limit):
        return self

    def execute(self):
        if self.table_name == "jarvis_proactive_state":
            row = self.db.state.get(self.key)
            return Result([row] if row else [])
        return Result(self.db.rows.get(self.table_name, []))

    def upsert(self, payload):
        self.db.state[payload["key"]] = payload
        return self


class FakeDB:
    def __init__(self):
        self.state = {}
        self.rows = {
            "leads": [{"id": "l1", "company_name": "Példa Kft.", "status": "research"}],
            "tasks": [{"id": "t1", "title": "Ajánlat", "status": "open",
                       "priority": "high", "due_at": "2026-11-14T10:00:00Z"}],
        }

    def table(self, name):
        return Query(self, name)


def test_monitor_records_baseline_and_detects_changes():
    db = FakeDB()
    first = run_proactive_monitor(db, today=date(2026, 11, 15))
    assert "Új cégek: 0" in first
    assert "első futás csak alapállapotot rögzít" in first
    assert "Lejárt, nyitott feladatok: 1" in first

    db.rows["leads"].append({"id": "l2", "company_name": "Másik Kft.", "status": "research"})
    db.rows["tasks"][0]["status"] = "done"
    second = run_proactive_monitor(db, today=date(2026, 11, 15))
    assert "Új cégek: 1" in second
    assert "Másik Kft." in second
    assert "Feladatstátusz-változások: 1" in second
