def test_stats_module_imports_without_connecting(monkeypatch, capsys):
    import stats

    monkeypatch.setattr(
        stats, "get_service_supabase",
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

    monkeypatch.setattr(jarvis_status, "get_service_supabase", lambda: DB())
    jarvis_status.run()
    output = capsys.readouterr().out
    assert "new: 2" in output
    assert "research: 1" in output


def test_stats_prints_lead_counts_and_sanitized_recent_logs(monkeypatch, capsys):
    import stats

    class Result:
        def __init__(self, data):
            self.data = data

    class Query:
        def __init__(self, table):
            self.table_name = table

        def select(self, _columns):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def limit(self, _limit):
            return self

        def execute(self):
            if self.table_name == "leads":
                return Result([{"status": "new"}, {"status": None}, {"status": "new"}])
            return Result([{
                "created_at": "2026-11-22T10:00:00Z",
                "module": "mailer",
                "level": "error",
                "message": "password=hidden-value",
            }])

    class DB:
        def table(self, name):
            return Query(name)

    monkeypatch.setattr(stats, "get_service_supabase", lambda: DB())
    monkeypatch.setattr(stats, "sanitize_log_text", lambda value: value.replace("hidden-value", "[REDACTED]"))

    stats.print_jarvis_status()

    output = capsys.readouterr().out
    assert "Összes lead: 3" in output
    assert "new: 2" in output
    assert "unknown: 1" in output
    assert "[REDACTED]" in output
    assert "hidden-value" not in output


def test_stats_reports_database_query_failure_without_leaking_exception(monkeypatch, capsys):
    import stats

    db = object()
    reports = []

    class Query:
        def select(self, _columns):
            return self

        def limit(self, _limit):
            return self

        def execute(self):
            raise RuntimeError("database failure")

    class DB:
        def table(self, _name):
            return Query()

    monkeypatch.setattr(stats, "get_service_supabase", lambda: DB())
    monkeypatch.setattr(
        stats, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )

    stats.print_jarvis_status()

    output = capsys.readouterr().out
    assert "Statisztikai lekérdezési hiba: RuntimeError" in output
    assert "database failure" not in output
    assert len(reports) == 1
    assert reports[0][1]["module"] == "stats"
    assert reports[0][1]["severity"] == "error"
    assert reports[0][1]["db"] is not None
