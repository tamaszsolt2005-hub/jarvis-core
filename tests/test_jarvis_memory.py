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
