"""Behavioral tests for schema-tolerant, read-only Supabase retrieval."""
import ast
from pathlib import Path
from typing import Any

import pandas as pd
from safe_http import safe_get, close_response


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "dashboard.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
_NAMESPACE = {"Any": Any, "pd": pd, "safe_get": safe_get, "close_response": close_response}


def _load_function(name):
    node = next(
        item for item in TREE.body
        if isinstance(item, ast.FunctionDef) and item.name == name
    )
    module = ast.Module(body=[node], type_ignores=[])
    exec(compile(module, str(ROOT / "dashboard.py"), "exec"), _NAMESPACE)
    return _NAMESPACE[name]


_safe_rows = _load_function("_safe_rows")
retrieve_context = _load_function("retrieve_context")


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, rows, calls):
        self.rows = rows
        self.calls = calls
        self.columns = "*"

    def select(self, columns):
        self.columns = columns
        self.calls.append(("select", columns))
        return self

    def limit(self, count):
        self.calls.append(("limit", count))
        return self

    def execute(self):
        self.calls.append(("execute",))
        if self.columns == "*":
            data = self.rows
        else:
            selected = self.columns.split(",")
            data = [{key: row[key] for key in selected if key in row} for row in self.rows]
        return FakeResponse(data)


class FakeDB:
    def __init__(self, tables):
        self.tables = tables
        self.calls = []

    def table(self, name):
        self.calls.append(("table", name))
        return FakeQuery(self.tables.get(name, []), self.calls)


def test_lead_retrieval_handles_legacy_schema_and_filters_personal_fields():
    db = FakeDB({
        "leads": [{
            "id": "lead-1",
            "company_name": "Minta Kft.",
            "status": "new",
            "email": "private@example.com",
            "notes": "Személyes megjegyzés",
        }]
    })

    context, sources = retrieve_context(db, "Mutasd a leadeket")

    assert "Minta Kft." in context
    assert "private@example.com" not in context
    assert "Személyes megjegyzés" not in context
    assert "leadek" in sources
    assert ("select", "*") in db.calls



def test_email_draft_retrieval_excludes_recipient_addresses():
    db = FakeDB({
        "email_drafts": [{
            "id": "draft-1",
            "recipient": "private@example.com",
            "subject": "Szakmai bemutatkozás",
            "status": "draft",
        }]
    })

    context, sources = retrieve_context(db, "Mutasd az e-mail piszkozatokat")

    assert "Szakmai bemutatkozás" in context
    assert "private@example.com" not in context
    assert ("select", "id,subject,status,created_at,lead_id") in db.calls
    assert "e-mail-piszkozatok" in sources


def test_read_query_is_bounded_and_does_not_call_mutation_methods():
    db = FakeDB({"leads": [{"id": "1", "company_name": "Minta", "status": "new"}]})

    _safe_rows(db, "leads", "*", 37)

    assert ("limit", 37) in db.calls
    assert not any(
        entry[0] in {"insert", "update", "upsert", "delete"}
        for entry in db.calls
    )


def test_empty_lead_table_returns_valid_context():
    db = FakeDB({"leads": []})

    context, sources = retrieve_context(db, "Lead áttekintés")

    assert "Vizsgált leadek (legfeljebb 1500): 0" in context
    assert sources == ["leadek", "feladatok", "e-mail-piszkozatok", "naplók"]



def test_website_url_filter_rejects_non_http_and_local_targets():
    public_http_url = _load_function("_public_http_url")
    assert public_http_url("file:///etc/passwd") is None
    assert public_http_url("http://127.0.0.1") is None
    assert public_http_url("http://localhost") is None


def test_ranking_request_fetches_only_bounded_website_set():
    assert "wants_ranking" in SOURCE
    assert '"website"' in SOURCE
    assert "_website_profile(website)" in SOURCE
    assert "if len(ranked) >= 30" in SOURCE
    assert "allow_redirects=False" in (ROOT / "safe_http.py").read_text(encoding="utf-8")
    assert ".is_global" in SOURCE


def test_website_profile_safely_follows_public_redirect(monkeypatch):
    import socket
    import requests

    _load_function("_public_http_url")
    website_profile = _load_function("_website_profile")
    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
    )

    class Response:
        def __init__(self, status, headers=None, body=b""):
            self.status_code = status
            self.headers = headers or {}
            self.body = body
            self.closed = False

        def iter_content(self, chunk_size):
            yield self.body

        def close(self):
            self.closed = True

    responses = [
        Response(301, {"Location": "https://www.example.com/company"}),
        Response(200, {"Content-Type": "text/html; charset=utf-8"}, b"<html><title>Example</title><body>Company services contact</body></html>"),
    ]
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return responses.pop(0)

    import safe_http
    monkeypatch.setattr(safe_http, "safe_get", fake_get)
    result = website_profile("https://example.com")

    assert result["status"] == "sikeresen beolvasva"
    assert result["url"] == "https://www.example.com/company"
    assert len(calls) == 2
    assert all("allow_redirects" not in call[1] for call in calls)


def test_website_error_question_loads_leads_and_website_profiles(monkeypatch):
    monkeypatch.setitem(
        _NAMESPACE,
        "_website_profile",
        lambda url: {"status": "HTTP 403", "score": 0, "url": url},
    )
    db = FakeDB({
        "leads": [{
            "id": "lead-web-1",
            "company_name": "Minta Kft.",
            "website": "https://example.com",
            "status": "new",
        }]
    })

    context, sources = retrieve_context(db, "Mutasd a hibás weboldalakat")

    assert "Minta Kft." in context
    assert "HTTP 403" in context
    assert "lead-weboldalak és rangsorolás" in sources



def test_dashboard_website_fetch_uses_dns_pinned_transport():
    assert "from safe_http import safe_get, close_response" in SOURCE
    assert "response = safe_get(" in SOURCE


def test_website_score_uses_a_true_100_point_maximum(monkeypatch):
    import socket
    import safe_http

    _load_function("_public_http_url")
    website_profile = _load_function("_website_profile")
    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
    )

    class Response:
        status_code = 200
        headers = {"Content-Type": "text/html; charset=utf-8"}
        def iter_content(self, chunk_size):
            yield (
                "<html><head><title>Company</title>"
                '<meta name="description" content="Business services"></head>'
                "<body>services solutions products contact about us testimonials case study "
                "request a quote " + ("business information " * 120) + "</body></html>"
            ).encode()
        def close(self):
            pass

    monkeypatch.setattr(safe_http, "safe_get", lambda *args, **kwargs: Response())
    result = website_profile("https://example.com")
    assert result["score"] == 100


def test_ranking_scans_entire_bounded_lead_sample_until_30_sites(monkeypatch):
    monkeypatch.setitem(
        _NAMESPACE,
        "_website_profile",
        lambda url: {"status": "sikeresen beolvasva", "score": 88, "url": url},
    )
    rows = [{"id": str(i), "company_name": f"Cég {i}", "status": "research"} for i in range(520)]
    rows[-1]["website"] = "https://last.example"
    db = FakeDB({"leads": rows})

    context, _ = retrieve_context(db, "Rangsorold a weboldalakat")
    assert "Cég 519" in context
