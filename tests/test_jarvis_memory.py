from jarvis_memory import memory_command, _valid_memory


def test_explicit_save_command():
    assert memory_command("Jegyezd meg, hogy Magyarország az elsődleges piacunk") == (
        "save", "Magyarország az elsődleges piacunk"
    )


def test_memory_list_and_forget_commands():
    assert memory_command("Mutasd a memóriádat")[0] == "list"
    assert memory_command("Felejtsd el a régi árstratégiát") == ("forget", "a régi árstratégiát")


def test_ordinary_chat_does_not_write_memory():
    assert memory_command("Milyen lehetőségek vannak Németországban?") == ("none", "")


def test_rejects_secrets_and_contact_details():
    assert not _valid_memory("A jelszó: supersecret123")
    assert not _valid_memory("Kapcsolat: hello@example.com")
    assert _valid_memory("A fő célpiac Németország")



def test_explicit_decision_and_lesson_commands_are_categorized():
    assert memory_command("Jegyezd meg a döntést: Németország legyen a második piac") == (
        "save:decision", "Németország legyen a második piac"
    )
    assert memory_command("Rögzítsd a tanulságot: a túl tág célzás gyenge eredményt adott") == (
        "save:lesson", "a túl tág célzás gyenge eredményt adott"
    )
    assert memory_command("Mentsd el a tapasztalatot: a rövidebb brief pontosabb") == (
        "save:outcome", "a rövidebb brief pontosabb"
    )


def test_forget_all_command():
    assert memory_command("Felejtsd el mindent") == ("forget", "")


class MemoryResult:
    def __init__(self, data):
        self.data = data


class MemoryQuery:
    def __init__(self, db):
        self.db = db
        self.filters = {}
        self.update_payload = None

    def select(self, _columns):
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, _limit):
        return self

    def update(self, payload):
        self.update_payload = payload
        return self

    def execute(self):
        if self.update_payload:
            changed = []
            for row in self.db.rows:
                if all(row.get(k) == v for k, v in self.filters.items()):
                    row.update(self.update_payload)
                    changed.append(row)
            return MemoryResult(changed)
        return MemoryResult([r.copy() for r in self.db.rows
                             if all(r.get(k) == v for k, v in self.filters.items())])


class MemoryDB:
    def __init__(self):
        self.rows = [
            {"id": "1", "category": "lesson", "content": "A gyártási szektorban a partneri ajánlás működött", "active": True, "created_at": "2026-01-02"},
            {"id": "2", "category": "decision", "content": "Németország legyen a második célpiac", "active": True, "created_at": "2026-01-01"},
        ]

    def table(self, _name):
        return MemoryQuery(self)


def test_forget_matches_complete_phrase_despite_hungarian_suffixes():
    from jarvis_memory import forget_memories
    db = MemoryDB()
    assert forget_memories(db, "gyártás partneri ajánlás") == 1
    assert db.rows[0]["active"] is False
    assert db.rows[1]["active"] is True


def test_forget_does_not_deactivate_on_only_partial_phrase():
    from jarvis_memory import forget_memories
    db = MemoryDB()
    assert forget_memories(db, "partneri ajánlás gyártás németország") == 0
    assert all(row["active"] for row in db.rows)



def test_memory_retrieval_prefers_relevant_category_without_dropping_matching_memories():
    from jarvis_memory import get_memories

    class CategoryDB:
        def table(self, _name):
            class CategoryQuery:
                def select(self, _columns): return self
                def eq(self, *_args): return self
                def order(self, *_args, **_kwargs): return self
                def limit(self, _limit): return self
                def execute(self):
                    return MemoryResult([
                        {"id": "1", "category": "business_preference", "content": "A gyártási piac fontos", "created_at": "2026-01-03"},
                        {"id": "2", "category": "outcome", "content": "A gyártási piacon a partneri módszer működött", "created_at": "2026-01-02"},
                        {"id": "3", "category": "lesson", "content": "A gyártási piacon a partneri módszer tanulsága", "created_at": "2026-01-01"},
                    ])
            return CategoryQuery()

    result = get_memories(CategoryDB(), "Mi működött a gyártási piacon?", limit=20)
    assert result[0]["category"] in {"outcome", "lesson"}
    assert {row["id"] for row in result} == {"1", "2", "3"}


def test_save_memory_writes_only_explicit_safe_business_memory():
    from jarvis_memory import save_memory

    class InsertQuery:
        def __init__(self, db):
            self.db = db
        def insert(self, payload):
            self.db.payload = payload
            return self
        def execute(self):
            return MemoryResult([self.db.payload])

    class DB:
        payload = None
        def table(self, _name):
            return InsertQuery(self)

    db = DB()
    assert save_memory(db, "A második célpiac Németország", category="decision") is True
    assert db.payload == {
        "category": "decision",
        "content": "A második célpiac Németország",
        "source": "explicit_user_instruction",
        "active": True,
    }


def test_save_memory_rejects_sensitive_or_oversized_content_before_database_access():
    from jarvis_memory import save_memory

    class ForbiddenDB:
        def table(self, _name):
            raise AssertionError("Rejected memory must not access the database")

    db = ForbiddenDB()
    assert save_memory(db, "secret token=abc123") is False
    assert save_memory(db, "x" * 701) is False


def test_save_memory_normalizes_unknown_category():
    from jarvis_memory import save_memory

    class DB:
        payload = None
        def table(self, _name):
            db = self
            class Query:
                def insert(self, payload):
                    db.payload = payload
                    return self
                def execute(self):
                    return MemoryResult([db.payload])
            return Query()

    db = DB()
    assert save_memory(db, "A célpiac Németország", category="unknown") is True
    assert db.payload["category"] == "business_preference"


def test_get_memories_clamps_limit_and_returns_recent_rows_for_empty_query():
    from jarvis_memory import get_memories

    class DB:
        def table(self, _name):
            class Query:
                requested_limit = None
                def select(self, _columns): return self
                def eq(self, *_args): return self
                def order(self, *_args, **_kwargs): return self
                def limit(self, value):
                    self.requested_limit = value
                    return self
                def execute(self):
                    self.db_limit = self.requested_limit
                    return MemoryResult([
                        {"id": str(i), "category": "lesson", "content": f"memory {i}"}
                        for i in range(30)
                    ])
            return Query()

    result = get_memories(DB(), "", limit=500)
    assert len(result) == 20


def test_forget_all_deactivates_only_active_memories():
    from jarvis_memory import forget_memories

    db = MemoryDB()
    db.rows.append({
        "id": "3", "category": "lesson", "content": "Old memory",
        "active": False, "created_at": "2025-01-01",
    })
    assert forget_memories(db, "") == 2
    assert all(row["active"] is False for row in db.rows)


def test_forget_without_meaningful_tokens_is_a_no_op():
    from jarvis_memory import forget_memories

    db = MemoryDB()
    assert forget_memories(db, "az és a") == 0
    assert all(row["active"] for row in db.rows)


def test_memory_command_handles_empty_and_unrecognized_requests():
    assert memory_command("Jegyezd meg") == ("none", "")
    assert memory_command("Felejtsd el") == ("forget", "")
    assert memory_command("Beszéljünk a piacról") == ("none", "")


def test_memory_write_paths_deny_missing_auth_session_when_enforced(monkeypatch):
    import pytest
    import jarvis_common
    from jarvis_memory import forget_memories, save_memory

    monkeypatch.setattr(jarvis_common, "env_bool", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        jarvis_common, "get_user_supabase",
        lambda *_args, **_kwargs: pytest.fail("Missing session must be denied before DB access"),
    )

    class ForbiddenDB:
        def table(self, _name):
            pytest.fail("No memory database access is allowed without Auth")

    db = ForbiddenDB()
    with pytest.raises(PermissionError, match="Auth-munkamenet"):
        save_memory(db, "A célpiac Németország")
    with pytest.raises(PermissionError, match="Auth-munkamenet"):
        forget_memories(db, "Németország")
