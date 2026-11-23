"""Isolated behavioral tests for dashboard helpers without importing/running Streamlit UI."""
import ast
import contextlib
import bs4
import socket
import sys
import types
from pathlib import Path
from typing import Any

import pytest
import requests
import pandas as pd
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "dashboard.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _load_helpers(monkeypatch, names):
    selected = [
        node for node in TREE.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in names
    ]
    assert {node.name for node in selected} == set(names)
    namespace = {"Any": Any, "BeautifulSoup": BeautifulSoup, "requests": requests, "pd": pd}
    module = ast.Module(body=selected, type_ignores=[])
    exec(compile(module, str(ROOT / "dashboard.py"), "exec"), namespace)
    return namespace


def test_format_conversation_history_filters_roles_and_keeps_recent_context(monkeypatch):
    fn = _load_helpers(monkeypatch, {"format_conversation_history"})["format_conversation_history"]
    result = fn([
        ("system", "ignore"),
        ("user", "régi kérdés"),
        ("assistant", "régi válasz"),
        ("user", "  új kérdés  "),
    ])
    assert result == "user: régi kérdés\nassistant: régi válasz\nuser: új kérdés"


def test_format_conversation_history_enforces_message_and_total_limits(monkeypatch):
    fn = _load_helpers(monkeypatch, {"format_conversation_history"})["format_conversation_history"]
    result = fn([("user", "x" * 100)], max_chars=40, max_message_chars=20)
    assert len(result) <= 40
    assert "rövidítve" in result
    assert fn([("user", "x")], max_chars=0) == ""


class _Query:
    def __init__(self, rows):
        self.rows = rows
        self.selected = None
        self.limit_value = None

    def select(self, columns):
        self.selected = columns
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def execute(self):
        return types.SimpleNamespace(data=self.rows)


def test_safe_rows_is_read_only_bounded_and_handles_empty_result(monkeypatch):
    fn = _load_helpers(monkeypatch, {"_safe_rows"})["_safe_rows"]
    query = _Query([{"id": "1"}])
    class DB:
        def table(self, name):
            assert name == "leads"
            return query
    assert fn(DB(), "leads", "id,email", 25) == [{"id": "1"}]
    assert query.selected == "id,email"
    assert query.limit_value == 25
    assert fn(type("DB", (), {"table": lambda self, _name: _Query(None)})(), "tasks", "id") == []


@pytest.mark.parametrize("url", [
    "", "file:///etc/passwd", "https://user:pass@example.com",
    "https://example.com:8443", "http://localhost", "https://a.localhost",
    "x" * 2049, "http://127.0.0.1", "http://[::1]",
])
def test_public_http_url_rejects_invalid_local_and_private_destinations(monkeypatch, url):
    fn = _load_helpers(monkeypatch, {"_public_http_url"})["_public_http_url"]
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_a, **_k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.8", 80))
    ])
    assert fn(url) is None


def test_public_http_url_accepts_public_dns_and_normalizes_bare_host(monkeypatch):
    fn = _load_helpers(monkeypatch, {"_public_http_url"})["_public_http_url"]
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_a, **_k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))
    ])
    assert fn("example.com") == "https://example.com"


def test_public_http_url_rejects_mixed_public_and_private_dns_answers(monkeypatch):
    fn = _load_helpers(monkeypatch, {"_public_http_url"})["_public_http_url"]
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_a, **_k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.2", 443)),
    ])
    assert fn("mixed.example") is None


class _Response:
    def __init__(self, status=200, headers=None, chunks=None):
        self.status_code = status
        self.headers = headers or {"Content-Type": "text/html; charset=utf-8"}
        self.chunks = chunks or [b"<html><title>Company</title><body>Services Contact About us</body></html>"]
        self.closed = False

    def iter_content(self, chunk_size):
        assert chunk_size == 16384
        yield from self.chunks

    def close(self):
        self.closed = True


def _website_namespace(monkeypatch, safe_url="https://example.com"):
    closed = []
    safe_http = types.ModuleType("safe_http")
    safe_http.safe_get = lambda *_a, **_k: None
    safe_http.close_response = lambda response: (response.close(), closed.append(response))
    monkeypatch.setitem(sys.modules, "safe_http", safe_http)
    namespace = _load_helpers(monkeypatch, {"_website_profile", "_public_http_url"})
    namespace["_public_http_url"] = lambda _url: safe_url
    reports = []
    namespace["report_error"] = lambda error, **kwargs: reports.append((error, kwargs))
    return namespace["_website_profile"], safe_http, closed, reports


def test_website_profile_scores_html_and_always_closes_response(monkeypatch):
    profile, safe_http, closed, _reports = _website_namespace(monkeypatch)
    response = _Response(chunks=[
        b"<html><head><title>Company</title><meta name='description' content='Solutions'></head>"
        b"<body>Services Contact About us References Request a quote " + (b"business " * 100) + b"</body></html>"
    ])
    safe_http.safe_get = lambda *_a, **_k: response
    result = profile("example.com")
    assert result["status"] == "sikeresen beolvasva"
    assert result["score"] > 50
    assert result["signals"]["kapcsolat"] is True
    assert response.closed and closed == [response]


def test_website_profile_rejects_unsafe_url_without_network(monkeypatch):
    profile, safe_http, _closed, _reports = _website_namespace(monkeypatch, safe_url=None)
    safe_http.safe_get = lambda *_a, **_k: pytest.fail("unsafe URL must not trigger HTTP")
    result = profile("http://127.0.0.1")
    assert result["score"] == 0
    assert "biztonságos" in result["status"]


def test_website_profile_closes_response_on_http_and_non_html_errors(monkeypatch):
    profile, safe_http, closed, _reports = _website_namespace(monkeypatch)
    response = _Response(status=503)
    safe_http.safe_get = lambda *_a, **_k: response
    assert profile("example.com")["status"] == "HTTP 503"
    assert response.closed
    response = _Response(headers={"Content-Type": "application/pdf"})
    safe_http.safe_get = lambda *_a, **_k: response
    assert profile("example.com")["status"] == "nem HTML weboldal"
    assert response.closed
    assert len(closed) == 2


def test_website_profile_blocks_unsafe_redirect_and_closes_redirect_response(monkeypatch):
    profile, safe_http, closed, _reports = _website_namespace(monkeypatch)
    original_validator = profile.__globals__["_public_http_url"]
    profile.__globals__["_public_http_url"] = lambda value: None if "127.0.0.1" in value else original_validator(value)
    response = _Response(status=302, headers={"Location": "http://127.0.0.1"})
    safe_http.safe_get = lambda *_a, **_k: response
    result = profile("example.com")
    assert result["status"] == "nem biztonságos átirányítási cél"
    assert response.closed and closed == [response]


def test_website_profile_reports_transport_and_parser_errors(monkeypatch):
    profile, safe_http, closed, reports = _website_namespace(monkeypatch)
    safe_http.safe_get = lambda *_a, **_k: (_ for _ in ()).throw(requests.Timeout("mock timeout"))
    result = profile("example.com")
    assert "Timeout" in result["status"]
    assert reports[-1][1]["severity"] == "warning"

    response = _Response()
    safe_http.safe_get = lambda *_a, **_k: response
    namespace = _load_helpers(monkeypatch, {"_website_profile", "_public_http_url"})
    namespace["_public_http_url"] = lambda _url: "https://example.com"
    namespace["report_error"] = lambda error, **kwargs: reports.append((error, kwargs))
    monkeypatch.setattr(bs4, "BeautifulSoup", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("mock parse")))
    result = namespace["_website_profile"]("example.com")
    assert "RuntimeError" in result["status"]
    assert reports[-1][1]["severity"] == "error"
    assert response.closed and response in closed



def test_proactive_signals_only_include_overdue_open_tasks_and_explicitly_approved_followups(monkeypatch):
    fn = _load_helpers(monkeypatch, {"_proactive_signals"})["_proactive_signals"]
    result = fn(
        leads=[
            {"id": "ok", "company_name": "Allowed", "next_follow_up_at": "2000-01-01T00:00:00Z",
             "approved_to_contact": True, "opted_out": False, "status": "sent"},
            {"id": "opted-out", "next_follow_up_at": "2000-01-01T00:00:00Z",
             "approved_to_contact": True, "opted_out": True},
            {"id": "not-approved", "next_follow_up_at": "2000-01-01T00:00:00Z",
             "approved_to_contact": False, "opted_out": False},
            {"id": "missing-approval", "next_follow_up_at": "2000-01-01T00:00:00Z",
             "opted_out": False},
            {"id": "invalid-date", "next_follow_up_at": "not-a-date",
             "approved_to_contact": True, "opted_out": False},
        ],
        tasks=[
            {"id": "late", "title": "Late", "due_at": "2000-01-01T00:00:00Z", "status": "open"},
            {"id": "done", "title": "Done", "due_at": "2000-01-01T00:00:00Z", "status": "done"},
            {"id": "invalid", "title": "Invalid", "due_at": "not-a-date", "status": "open"},
        ],
    )
    assert result["overdue_task_count"] == 1
    assert result["overdue_tasks"][0]["title"] == "Late"
    assert result["overdue_approved_followup_count"] == 1
    assert result["overdue_approved_followups"][0]["lead_id"] == "ok"
    assert "nem automatikus műveletek" in result["interpretation"]


def test_proactive_signals_caps_displayed_items_without_losing_total_counts(monkeypatch):
    fn = _load_helpers(monkeypatch, {"_proactive_signals"})["_proactive_signals"]
    tasks = [
        {"title": f"Late {i}", "due_at": "2000-01-01T00:00:00Z", "status": "open"}
        for i in range(35)
    ]
    result = fn([], tasks)
    assert result["overdue_task_count"] == 35
    assert len(result["overdue_tasks"]) == 30


@pytest.mark.parametrize("question,expected", [
    ("Keress új leadeket a magyar gyártóknál", True),
    ("Készíts leadkutatást", True),
    ("Ne keress új leadeket", False),
    ("Milyen feladatok vannak?", False),
    ("Azonosítsd a lehetséges beszállítókat", True),
])
def test_global_research_requires_explicit_prospecting_intent(monkeypatch, question, expected):
    fn = _load_helpers(monkeypatch, {"_wants_global_research"})["_wants_global_research"]
    assert fn(question) is expected



def test_safe_rows_isolates_database_read_failure_and_reports_warning(monkeypatch):
    fn_namespace = _load_helpers(monkeypatch, {"_safe_rows"})
    reports = []
    fn_namespace["report_error"] = lambda error, **kwargs: reports.append((error, kwargs))
    fn = fn_namespace["_safe_rows"]

    class BrokenQuery:
        def select(self, _columns):
            return self
        def limit(self, _limit):
            return self
        def execute(self):
            raise RuntimeError("mock database read failure")

    class BrokenDB:
        def table(self, _name):
            return BrokenQuery()

    assert fn(BrokenDB(), "logs", "module,level") == []
    assert len(reports) == 1
    assert isinstance(reports[0][0], RuntimeError)
    assert reports[0][1]["operation"] == "read_rows:logs"
    assert reports[0][1]["severity"] == "warning"


def test_safe_rows_rejects_unexpected_response_shape_without_crashing(monkeypatch):
    fn_namespace = _load_helpers(monkeypatch, {"_safe_rows"})
    reports = []
    fn_namespace["report_error"] = lambda error, **kwargs: reports.append((error, kwargs))

    class OddQuery(_Query):
        def execute(self):
            return types.SimpleNamespace(data={"not": "a row list"})

    class OddDB:
        def table(self, _name):
            return OddQuery([])

    assert fn_namespace["_safe_rows"](OddDB(), "tasks", "id") == []
    assert isinstance(reports[0][0], TypeError)



def test_safe_rows_status_distinguishes_empty_result_from_database_failure(monkeypatch):
    namespace = _load_helpers(monkeypatch, {"_safe_rows"})
    namespace["report_error"] = lambda *_args, **_kwargs: None
    fn = namespace["_safe_rows"]

    empty_status = {}
    empty_db = type("EmptyDB", (), {
        "table": lambda self, _name: _Query([])
    })()
    assert fn(empty_db, "leads", "*", status=empty_status) == []
    assert empty_status == {"ok": True, "error": False, "error_type": None}

    failed_status = {}
    class FailedQuery(_Query):
        def execute(self):
            raise OSError("mock offline database")
    failed_db = type("FailedDB", (), {
        "table": lambda self, _name: FailedQuery([])
    })()
    assert fn(failed_db, "leads", "*", status=failed_status) == []
    assert failed_status == {"ok": False, "error": True, "error_type": "OSError"}


def test_retrieve_context_does_not_present_database_failure_as_empty_lead_list(monkeypatch):
    namespace = _load_helpers(monkeypatch, {"retrieve_context", "_safe_rows"})
    namespace["report_error"] = lambda *_args, **_kwargs: None

    class FailedQuery(_Query):
        def execute(self):
            raise OSError("mock offline database")
    class FailedDB:
        def table(self, _name):
            return FailedQuery([])

    context, loaded = namespace["retrieve_context"](FailedDB(), "mutasd a leadeket")
    assert "ADATFORRÁS NEM ELÉRHETŐ" in context
    assert "nem tekinthető üres leadlistának" in context
    assert "Vizsgált leadek" not in context
    assert "leadek (adatforrás-hiba)" in loaded


def test_retrieve_context_keeps_a_real_empty_lead_list_distinct(monkeypatch):
    namespace = _load_helpers(monkeypatch, {"retrieve_context", "_safe_rows"})
    namespace["report_error"] = lambda *_args, **_kwargs: None

    class EmptyDB:
        def table(self, _name):
            return _Query([])

    context, loaded = namespace["retrieve_context"](EmptyDB(), "mutasd a leadeket")
    assert "Vizsgált leadek (legfeljebb 1500): 0" in context
    assert "ADATFORRÁS NEM ELÉRHETŐ" not in context
    assert "leadek" in loaded



def test_retrieve_context_suppresses_proactive_zero_counts_when_task_source_fails(monkeypatch):
    namespace = _load_helpers(monkeypatch, {"retrieve_context", "_safe_rows"})
    namespace["report_error"] = lambda *_args, **_kwargs: None

    class TaskFailureDB:
        def table(self, name):
            if name == "tasks":
                class FailedTaskQuery(_Query):
                    def execute(self):
                        raise OSError("mock task database outage")
                return FailedTaskQuery([])
            return _Query([])

    context, loaded = namespace["retrieve_context"](TaskFailureDB(), "mutasd a lejárt feladatokat")
    assert "ADATFORRÁS NEM ELÉRHETŐ" in context
    assert "PROAKTÍV JELZÉSEK NEM KÉSZÜLTEK" in context
    assert "overdue_task_count" not in context
    assert "feladatok (adatforrás-hiba)" in loaded



def test_retrieve_context_keeps_healthy_leads_when_task_source_fails(monkeypatch):
    namespace = _load_helpers(monkeypatch, {"retrieve_context", "_safe_rows"})
    namespace["report_error"] = lambda *_args, **_kwargs: None

    class PartiallyAvailableDB:
        def table(self, name):
            if name == "tasks":
                class FailedQuery(_Query):
                    def execute(self):
                        raise OSError("mock task store outage")
                return FailedQuery([])
            if name == "leads":
                return _Query([{"id": "lead-healthy", "company_name": "Healthy Ltd", "status": "new"}])
            return _Query([])

    context, loaded = namespace["retrieve_context"](
        PartiallyAvailableDB(), "mutasd a leadeket és a feladatokat"
    )
    assert "Healthy Ltd" in context
    assert "ADATFORRÁS NEM ELÉRHETŐ" in context
    assert "FELADATOK" not in context
    assert "leadek" in loaded
    assert "feladatok (adatforrás-hiba)" in loaded


def test_optional_draft_read_failure_does_not_hide_lead_context(monkeypatch):
    namespace = _load_helpers(monkeypatch, {"retrieve_context", "_safe_rows"})
    namespace["report_error"] = lambda *_args, **_kwargs: None

    class DraftFailureDB:
        def table(self, name):
            if name == "email_drafts":
                class FailedQuery(_Query):
                    def execute(self):
                        raise OSError("mock drafts store outage")
                return FailedQuery([])
            if name == "leads":
                return _Query([{"id": "lead-healthy", "company_name": "Healthy Ltd", "status": "new"}])
            return _Query([])

    context, loaded = namespace["retrieve_context"](
        DraftFailureDB(), "mutasd az e-mail piszkozatokat"
    )
    assert "Healthy Ltd" in context
    assert "e-mail-piszkozatok metaadatainak olvasása nem sikerült" in context
    assert "leadek" in loaded
    assert "e-mail-piszkozatok (adatforrás-hiba)" in loaded


def test_analytics_is_not_built_when_both_current_and_legacy_log_reads_fail(monkeypatch):
    namespace = _load_helpers(monkeypatch, {"retrieve_context", "_safe_rows"})
    reports = []
    namespace["report_error"] = lambda error, **kwargs: reports.append((error, kwargs))
    namespace["build_chat_analytics_context"] = lambda _rows: pytest.fail(
        "analytics must not be generated from a failed log read"
    )

    class LogsUnavailableDB:
        def table(self, name):
            if name == "logs":
                class FailedQuery(_Query):
                    def execute(self):
                        raise ConnectionError("mock logs outage")
                return FailedQuery([])
            return _Query([])

    context, loaded = namespace["retrieve_context"](LogsUnavailableDB(), "rendszer analitika")
    assert "ANALITIKA NEM KÉSZÜLT" in context
    assert "naplóalapú analitika (adatforrás-hiba)" in loaded
    assert len(reports) == 2
    assert all(item[1]["operation"] == "read_rows:logs" for item in reports)



def test_website_profile_follows_public_redirect_and_closes_each_response(monkeypatch):
    profile, safe_http, closed, _reports = _website_namespace(monkeypatch)
    profile.__globals__["_public_http_url"] = lambda value: value if "://" in value else "https://" + value
    redirect = _Response(status=302, headers={"Location": "/about"})
    final = _Response(chunks=[
        b"<html><title>About</title><body>" + b"Company services contact " * 20 + b"</body></html>"
    ])
    responses = iter([redirect, final])
    requested = []
    def fake_get(url, **_kwargs):
        requested.append(url)
        return next(responses)
    safe_http.safe_get = fake_get

    result = profile("example.com")

    assert requested == ["https://example.com", "https://example.com/about"]
    assert result["status"] == "sikeresen beolvasva"
    assert result["url"] == "https://example.com/about"
    assert redirect.closed and final.closed
    assert closed == [redirect, final]


def test_website_profile_handles_redirect_without_location_and_redirect_limit(monkeypatch):
    profile, safe_http, closed, _reports = _website_namespace(monkeypatch)
    missing = _Response(status=302, headers={})
    safe_http.safe_get = lambda *_args, **_kwargs: missing
    result = profile("example.com")
    assert "hiányzó átirányítási cím" in result["status"]
    assert missing.closed

    redirects = [_Response(status=302, headers={"Location": "/next"}) for _ in range(4)]
    iterator = iter(redirects)
    safe_http.safe_get = lambda *_args, **_kwargs: next(iterator)
    result = profile("example.com")
    assert "túl sok átirányítás" in result["status"]
    assert all(response.closed for response in redirects)
    assert len(closed) == 5


def test_public_http_url_fails_closed_on_dns_error_and_malformed_port(monkeypatch):
    fn = _load_helpers(monkeypatch, {"_public_http_url"})["_public_http_url"]
    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("mock DNS outage")),
    )
    assert fn("https://unresolvable.example") is None
    assert fn("https://example.com:99999") is None


def test_safe_rows_filters_non_dictionary_rows_without_losing_valid_rows(monkeypatch):
    namespace = _load_helpers(monkeypatch, {"_safe_rows"})
    namespace["report_error"] = lambda *_args, **_kwargs: None

    class MixedQuery(_Query):
        def execute(self):
            return types.SimpleNamespace(data=[{"id": "valid"}, None, "bad-row", {"id": "also-valid"}])

    class MixedDB:
        def table(self, _name):
            return MixedQuery([])

    assert namespace["_safe_rows"](MixedDB(), "leads", "*") == [
        {"id": "valid"}, {"id": "also-valid"}
    ]
