def test_stats_module_imports_without_connecting(monkeypatch, capsys):
    import stats

    monkeypatch.setattr(
        stats, "get_supabase",
        lambda: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    stats.print_jarvis_status()
    assert "Statisztikai lekérdezési hiba" in capsys.readouterr().out


def test_jarvis_status_run_reports_lead_status_counts(monkeypatch, capsys):
    import jarvis_status

    class Result:
        data = [{"status": "new"}, {"status": "research"}, {"status": "new"}]

    class Query:
        def select(self, _columns):
            return self

        def limit(self, _limit):
            return self

        def execute(self):
            return Result()

    class DB:
        def table(self, _name):
            return Query()

    monkeypatch.setattr(jarvis_status, "get_supabase", lambda: DB())
    jarvis_status.run()
    output = capsys.readouterr().out
    assert "new: 2" in output
    assert "research: 1" in output
