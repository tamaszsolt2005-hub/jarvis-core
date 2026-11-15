from task_actions import execute_task_action, parse_task_command


TASK_ID = "123e4567-e89b-42d3-a456-426614174000"


def test_parse_create_task_with_deadline_and_priority():
    action = parse_task_command("Hozz létre feladat: Ajánlat ellenőrzése; határidő=2026-12-01; prioritás=high")
    assert action == {
        "type": "create", "title": "Ajánlat ellenőrzése", "priority": "high",
        "due_at": "2026-12-01T23:59:00+01:00", "notes": "",
    }


def test_reject_invalid_priority_and_date():
    assert "prioritás" in parse_task_command("Új feladat: Teszt; prioritás=critical")["error"]
    assert "dátum" in parse_task_command("Új feladat: Teszt; határidő=2026-02-30")["error"]


def test_parse_close_and_update():
    assert parse_task_command(f"Zárd le a feladatot: {TASK_ID}") == {"type": "close", "id": TASK_ID}
    action = parse_task_command(f"Módosítsd a feladatot: {TASK_ID}; prioritás=urgent; cím=Fontos")
    assert action["updates"] == {"priority": "urgent", "title": "Fontos"}


def test_non_explicit_command_is_not_action():
    assert parse_task_command("Szerintem jó lenne lezárni a feladatot") is None


class Result:
    def __init__(self, data=None):
        self.data = data or []


class Query:
    def __init__(self, db):
        self.db = db
        self.filters = {}
        self.payload = None

    def select(self, _fields):
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def limit(self, _limit):
        return self

    def insert(self, payload):
        self.payload = payload
        return self

    def update(self, payload):
        self.payload = payload
        return self

    def execute(self):
        if self.payload and "status" in self.payload and self.payload["status"] == "open":
            self.db.created = self.payload
            return Result([{"id": TASK_ID}])
        if self.filters.get("id") == TASK_ID:
            self.db.updated = self.payload
            return Result([{"id": TASK_ID, "title": "Teszt", "status": "open"}])
        return Result([{"id": TASK_ID, "title": "Teszt", "status": "open"}])


class FakeDB:
    def __init__(self):
        self.created = None
        self.updated = None

    def table(self, _name):
        return Query(self)


def test_execute_create_and_close():
    db = FakeDB()
    assert "létrehozva" in execute_task_action(db, {"type": "create", "title": "Teszt", "priority": "normal"})
    assert db.created["title"] == "Teszt"
    assert "lezárva" in execute_task_action(db, {"type": "close", "id": TASK_ID})
    assert db.updated["status"] == "done"



def test_completed_task_is_not_mutated_again():
    class CompletedQuery(Query):
        def execute(self):
            if self.payload is not None:
                self.db.updated = self.payload
                return Result([])
            return Result([{"id": TASK_ID, "title": "Teszt", "status": "done"}])

    class CompletedDB(FakeDB):
        def table(self, _name):
            return CompletedQuery(self)

    db = CompletedDB()
    message = execute_task_action(db, {"type": "close", "id": TASK_ID})
    assert "már nem nyitott" in message
    assert db.updated is None
