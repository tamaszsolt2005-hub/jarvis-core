"""Isolated behavioral tests for dashboard helpers without importing/running Streamlit UI."""
import ast
import contextlib
import socket
import sys
import types
from pathlib import Path
from typing import Any

import pytest
import requests
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
    namespace = {"Any": Any, "BeautifulSoup": BeautifulSoup, "requests": requests}
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
    namespace["BeautifulSoup"] = lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("mock parse"))
    result = namespace["_website_profile"]("example.com")
    assert "RuntimeError" in result["status"]
    assert reports[-1][1]["severity"] == "error"
    assert response.closed and response in closed
