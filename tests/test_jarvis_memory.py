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
