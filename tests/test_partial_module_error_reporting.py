"""Regression tests for centralized reporting in previously partial modules."""
import pytest


def test_stats_reports_failure_without_printing_exception_secret(monkeypatch, capsys):
    import stats
    reports = []
    monkeypatch.setattr(stats, "get_supabase", lambda: (_ for _ in ()).throw(RuntimeError("password=hidden-stats-secret")))
    monkeypatch.setattr(stats, "report_error", lambda error, **kwargs: reports.append((error, kwargs)))
    stats.print_jarvis_status()
    assert len(reports) == 1
    assert reports[0][1]["module"] == "stats"
    assert reports[0][1]["operation"] == "load_system_statistics"
    assert "hidden-stats-secret" not in capsys.readouterr().out


def test_inbox_analyzer_reports_error_and_keeps_later_fallback(monkeypatch):
    import inbox_analyzer
    reports = []
    monkeypatch.setattr(inbox_analyzer.genai, "Client", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("model unavailable")))
    monkeypatch.setattr(inbox_analyzer, "report_error", lambda error, **kwargs: reports.append((error, kwargs)))
    assert inbox_analyzer.analyze_incoming_reply("Kérek ajánlatot", "dummy-key") == "later"
    assert reports[0][1]["module"] == "inbox_analyzer"
    assert reports[0][1]["severity"] == "warning"


def test_reply_analyzer_reports_error_and_keeps_unknown_fallback(monkeypatch):
    import reply_analyzer
    reports = []
    monkeypatch.setattr(reply_analyzer, "generate_text", lambda _prompt: (_ for _ in ()).throw(RuntimeError("model unavailable")))
    monkeypatch.setattr(reply_analyzer, "report_error", lambda error, **kwargs: reports.append((error, kwargs)))
    assert reply_analyzer.classify_reply("Köszönöm az üzenetet.") == "unknown"
    assert reports[0][1]["module"] == "reply_analyzer"
    assert reports[0][1]["severity"] == "warning"


def test_analytics_reports_database_failure_and_keeps_ui_fallback(monkeypatch):
    import jarvis_analytics
    reports = []
    class BrokenQuery:
        def select(self, *_args, **_kwargs): return self
        def gte(self, *_args, **_kwargs): return self
        def lte(self, *_args, **_kwargs): return self
        def order(self, *_args, **_kwargs): return self
        def limit(self, *_args, **_kwargs): return self
        def execute(self): raise RuntimeError("password=analytics-secret")
    class DB:
        def table(self, _name): return BrokenQuery()
    monkeypatch.setattr(jarvis_analytics.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(jarvis_analytics.st, "error", lambda *args, **kwargs: None)
    monkeypatch.setattr(jarvis_analytics.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(jarvis_analytics.st, "session_state", {})
    monkeypatch.setattr(jarvis_analytics, "report_error", lambda error, **kwargs: reports.append((error, kwargs)))
    jarvis_analytics.render_analytics(DB())
    assert len(reports) == 1
    assert reports[0][1]["module"] == "jarvis_analytics"
    assert reports[0][1]["operation"] == "load_analytics_logs"
    assert reports[0][1]["db"] is not None


def test_follow_up_reports_batch_failure_and_reraises_original(monkeypatch):
    import follow_up
    original = RuntimeError("database unavailable")
    reports = []
    monkeypatch.setattr(follow_up, "_run", lambda: (_ for _ in ()).throw(original))
    monkeypatch.setattr(follow_up, "report_error", lambda error, **kwargs: reports.append((error, kwargs)))
    with pytest.raises(RuntimeError) as caught:
        follow_up.run()
    assert caught.value is original
    assert reports[0][0] is original
    assert reports[0][1]["module"] == "follow_up"
    assert reports[0][1]["severity"] == "critical"


def test_inbox_monitor_reports_failure_and_reraises_original(monkeypatch):
    import inbox_monitor
    original = RuntimeError("IMAP unavailable")
    reports = []
    monkeypatch.setattr(inbox_monitor, "_run", lambda: (_ for _ in ()).throw(original))
    monkeypatch.setattr(inbox_monitor, "report_error", lambda error, **kwargs: reports.append((error, kwargs)))
    with pytest.raises(RuntimeError) as caught:
        inbox_monitor.run()
    assert caught.value is original
    assert reports[0][0] is original
    assert reports[0][1]["module"] == "inbox_monitor"
    assert reports[0][1]["severity"] == "error"
