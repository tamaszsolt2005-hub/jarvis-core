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
        self.status = "open"

    def table(self, _name):
        return Query(self)


def test_execute_create_and_close():
    db = FakeDB()
    assert "létrehozva" in execute_task_action(db, {"type": "create", "title": "Teszt", "priority": "normal"}, approved=True)
    assert db.created["title"] == "Teszt"
    assert "lezárva" in execute_task_action(db, {"type": "close", "id": TASK_ID}, approved=True)
    assert db.updated["status"] == "done"



def test_completed_task_is_not_mutated_again():
    class CompletedQuery(Query):
        def execute(self):
            if self.payload is not None:
                self.db.updated = self.payload
                return Result([])
            return Result([{"id": TASK_ID, "title": "Teszt", "status": "done"}])

    class AuditQuery:
        def insert(self, _payload):
            return self

        def execute(self):
            return Result([])

    class CompletedDB(FakeDB):
        def table(self, name):
            return AuditQuery() if name == "logs" else CompletedQuery(self)

    db = CompletedDB()
    message = execute_task_action(db, {"type": "close", "id": TASK_ID}, approved=True)
    assert "már nem nyitott" in message
    assert db.updated is None


def test_task_action_fails_closed_when_audit_log_is_unavailable(monkeypatch):
    import task_actions

    db = FakeDB()
    monkeypatch.setattr(task_actions, "audit_event", lambda *args, **kwargs: False)

    import pytest
    with pytest.raises(RuntimeError, match="auditnapló"):
        execute_task_action(
            db, {"type": "create", "title": "Ne jöjjön létre", "priority": "normal"}, approved=True
        )
    assert db.created is None


def test_task_action_requires_explicit_approval_before_database_access():
    import pytest

    class ForbiddenDB:
        def table(self, _name):
            pytest.fail("Database must not be accessed without explicit approval")

    with pytest.raises(PermissionError, match="jóváhagyás"):
        execute_task_action(
            ForbiddenDB(),
            {"type": "create", "title": "Tiltott művelet", "priority": "normal"},
        )


def test_invalid_task_payload_is_rejected_before_database_or_audit_access(monkeypatch):
    import pytest
    import task_actions

    class ForbiddenDB:
        def table(self, _name):
            pytest.fail("Invalid task payload must not access the database")

    monkeypatch.setattr(
        task_actions, "audit_event",
        lambda *_args, **_kwargs: pytest.fail("Invalid task payload must not write an audit event"),
    )
    invalid_actions = [
        {"type": "create", "title": "", "priority": "normal"},
        {"type": "create", "title": "Test", "priority": "urgent; DROP"},
        {"type": "create", "title": "Test", "priority": []},
        {"type": "create", "title": "Test", "priority": "normal", "notes": "x" * 1001},
        {"type": "close", "id": "not-a-uuid"},
        {"type": "update", "id": TASK_ID, "updates": {"admin": True}},
        {"type": "update", "id": TASK_ID, "updates": {"priority": []}},
        {"type": "delete", "id": TASK_ID},
        {"type": ["create"]},
    ]

    for action in invalid_actions:
        with pytest.raises(ValueError):
            execute_task_action(ForbiddenDB(), action, approved=True)


def test_truthy_non_boolean_approval_does_not_authorize_task_mutation():
    import pytest

    class ForbiddenDB:
        def table(self, _name):
            pytest.fail("Non-boolean approval must not access the database")

    with pytest.raises(PermissionError):
        execute_task_action(
            ForbiddenDB(),
            {"type": "create", "title": "Test", "priority": "normal"},
            approved="yes",
        )


def test_execute_update_task_changes_only_validated_fields():
    db = FakeDB()
    message = execute_task_action(
        db,
        {
            "type": "update",
            "id": TASK_ID,
            "updates": {"title": "Frissített cím", "priority": "high"},
        },
        approved=True,
    )
    assert "Feladat módosítva" in message
    assert db.updated["title"] == "Frissített cím"
    assert db.updated["priority"] == "high"
    assert "updated_at" in db.updated


def test_task_update_conflict_does_not_report_success_or_mutate():
    import task_actions

    class ConflictQuery(Query):
        def execute(self):
            if self.payload is not None:
                self.db.attempted_update = self.payload
                return Result([])
            return Result([{"id": TASK_ID, "title": "Teszt", "status": "open"}])

    class ConflictDB(FakeDB):
        def table(self, _name):
            return ConflictQuery(self)

    db = ConflictDB()
    audit_statuses = []
    original = task_actions.audit_event
    task_actions.audit_event = lambda _db, **kwargs: audit_statuses.append(kwargs["status"]) or True
    try:
        message = execute_task_action(
            db,
            {"type": "update", "id": TASK_ID, "updates": {"title": "Race"}},
            approved=True,
        )
    finally:
        task_actions.audit_event = original

    assert "időközben megváltozott" in message
    assert audit_statuses == ["pending", "blocked"]
    assert db.updated is None
    assert db.attempted_update is not None


def test_missing_task_is_not_mutated_and_is_audited_as_blocked():
    import task_actions

    class MissingQuery(Query):
        def execute(self):
            if self.payload is not None:
                self.db.attempted_update = self.payload
                return Result([])
            return Result([])

    class MissingDB(FakeDB):
        def table(self, _name):
            return MissingQuery(self)

    db = MissingDB()
    audit_statuses = []
    original = task_actions.audit_event
    task_actions.audit_event = lambda _db, **kwargs: audit_statuses.append(kwargs["status"]) or True
    try:
        message = execute_task_action(
            db, {"type": "close", "id": TASK_ID}, approved=True
        )
    finally:
        task_actions.audit_event = original

    assert "nem található" in message
    assert audit_statuses == ["pending", "blocked"]
    assert db.updated is None


@pytest.mark.parametrize(
    "command",
    [
        "Új feladat:",
        "Új feladat: Cím; hiányzó-egyenlőség",
        "Új feladat: Cím; ismeretlen=érték",
        "Új feladat: Cím; prioritás=",
        "Új feladat: " + "x" * 181,
        "Új feladat: Cím; prioritás=invalid",
        "Új feladat: Cím; határidő=2026-1-01",
        "Új feladat: Cím; határidő=2026-02-30",
        "Zárd le feladatot: 00000000-0000-0000-0000-000000000000",
        "Módosítsd feladatot: 00000000-0000-0000-0000-000000000000;cím=Új",
        f"Módosítsd feladatot: {TASK_ID}; hibás mező",
        f"Módosítsd feladatot: {TASK_ID}; határidő=2026-02-30",
        f"Módosítsd feladatot: {TASK_ID}; egyéb=érték",
    ],
)
def test_task_command_parser_rejects_malformed_commands(command):
    result = parse_task_command(command)
    assert result is None or "error" in result


def test_task_payload_validator_rejects_invalid_types_lengths_and_timezones():
    import pytest
    from task_actions import _validate_action

    invalid_actions = [
        [],
        {"type": "create", "title": "x" * 181, "priority": "normal"},
        {"type": "create", "title": "Title", "priority": "normal", "extra": "field"},
        {"type": "create", "title": "Title", "priority": "normal", "due_at": 123},
        {"type": "create", "title": "Title", "priority": "normal", "due_at": "invalid"},
        {"type": "create", "title": "Title", "priority": "normal", "due_at": "2026-12-01T10:00:00"},
        {"type": "close", "id": TASK_ID, "notes": "not allowed"},
        {"type": "update", "id": TASK_ID, "updates": {}},
        {"type": "update", "id": TASK_ID, "updates": {"title": "x" * 181}},
        {"type": "update", "id": TASK_ID, "updates": {"due_at": 123}},
        {"type": "update", "id": TASK_ID, "updates": {"due_at": "invalid"}},
        {"type": "update", "id": TASK_ID, "updates": {"due_at": "2026-12-01T10:00:00"}},
        {"type": "unknown"},
    ]
    for action in invalid_actions:
        with pytest.raises(ValueError):
            _validate_action(action)


def test_task_close_concurrency_conflict_is_audited_and_not_reported_as_success():
    import task_actions

    class ConflictCloseQuery(Query):
        def execute(self):
            if self.payload is not None:
                self.db.attempted_update = self.payload
                return Result([])
            return Result([{"id": TASK_ID, "title": "Teszt", "status": "open"}])

    class ConflictCloseDB(FakeDB):
        def table(self, _name):
            return ConflictCloseQuery(self)

    db = ConflictCloseDB()
    audit_statuses = []
    original = task_actions.audit_event
    task_actions.audit_event = lambda _db, **kwargs: audit_statuses.append(kwargs["status"]) or True
    try:
        message = execute_task_action(
            db, {"type": "close", "id": TASK_ID}, approved=True
        )
    finally:
        task_actions.audit_event = original

    assert "időközben megváltozott" in message
    assert audit_statuses == ["pending", "blocked"]
    assert db.updated is None
    assert db.attempted_update is not None
