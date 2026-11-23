"""Final defensive branch checks for diagnostics, memory, scoring and task parsing."""
from __future__ import annotations

import sys
from datetime import datetime, timezone

import pytest


def test_business_learning_decision_match_rejects_empty_and_unrelated_text():
    from business_learning import _decision_matches

    assert not _decision_matches("", "Német piac")
    assert not _decision_matches("Német piac tesztelése", "")
    assert not _decision_matches("Teljesen külön kampány", "Másik, eltérő döntés")
    assert _decision_matches("Német piac tesztelése", "Német piac tesztelése")


def test_health_check_reports_email_safety_lock_import_failure(monkeypatch):
    import health_check

    monkeypatch.setattr(health_check, "get_secret", lambda _name: None)
    monkeypatch.setattr(
        health_check, "get_supabase",
        lambda: (_ for _ in ()).throw(RuntimeError("no configured DB")),
    )
    reports = []
    monkeypatch.setattr(
        health_check, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )
    monkeypatch.setitem(sys.modules, "email_utils", None)

    report = health_check.run_self_diagnostics()

    assert "E-mail-küldési biztonsági zár | FIGYELMET IGÉNYEL" in report
    assert any(item[1]["operation"] == "check_email_safety_lock" for item in reports)


def test_memory_matcher_rejects_empty_query_or_content_tokens():
    from jarvis_memory import _matches_query

    assert not _matches_query("", {"gyártási"})
    assert not _matches_query("és az", {"gyártási"})
    assert not _matches_query("gyártási partneri", set())


def test_lead_scoring_handles_malformed_url_and_minimum_score():
    from lead_scoring import score_lead

    assert score_lead({"website": "http://[invalid", "company_name": "", "notes": ""}) == 35
    assert score_lead({}) == 35


def test_stats_empty_logs_print_truthful_empty_state(monkeypatch, capsys):
    import stats

    class Result:
        def __init__(self, data):
            self.data = data

    class Query:
        def __init__(self, table):
            self.table = table
        def select(self, *_args):
            return self
        def order(self, *_args, **_kwargs):
            return self
        def limit(self, *_args):
            return self
        def execute(self):
            return Result([{"status": "new"}] if self.table == "leads" else [])

    class DB:
        def table(self, name):
            return Query(name)

    monkeypatch.setattr(stats, "get_supabase", lambda: DB())
    stats.print_jarvis_status()
    assert "Nincsenek még logbejegyzések." in capsys.readouterr().out


def test_task_update_rejects_calendar_invalid_date():
    from task_actions import parse_task_command

    task_id = "123e4567-e89b-12d3-a456-426614174000"
    result = parse_task_command(
        f"Módosítsd a feladatot: {task_id}; határidő=2026-02-30"
    )
    assert result == {"error": "A megadott határidő nem érvényes dátum."}


def test_task_action_rejects_unknown_action_without_db_access():
    from task_actions import execute_task_action

    class DB:
        def table(self, _name):
            raise AssertionError("unknown action must not access DB")

    assert execute_task_action(DB(), {"type": "unknown"}, approved=True) == (
        "Ismeretlen feladatművelet; nem történt módosítás."
    )


def test_safe_http_closes_session_even_if_response_close_raises():
    from safe_http import close_response

    events = []

    class Session:
        def close(self):
            events.append("session")

    class Response:
        _jarvis_session = Session()
        def close(self):
            events.append("response")
            raise RuntimeError("close failure")

    with pytest.raises(RuntimeError, match="close failure"):
        close_response(Response())
    assert events == ["response", "session"]


def test_jarvis_status_empty_result_has_no_fabricated_counts(monkeypatch, capsys):
    import jarvis_status

    class Result:
        data = []

    class Query:
        def select(self, *_args):
            return self
        def limit(self, *_args):
            return self
        def execute(self):
            return Result()

    class DB:
        def table(self, _name):
            return Query()

    monkeypatch.setattr(jarvis_status, "get_supabase", lambda: DB())
    jarvis_status.run()
    assert capsys.readouterr().out == "JARVIS STATUS\n"
