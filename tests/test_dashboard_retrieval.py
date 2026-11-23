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
_proactive_signals = _load_function("_proactive_signals")
_wants_global_research = _load_function("_wants_global_research")
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


def test_proactive_signals_require_open_tasks_and_explicit_non_opted_out_consent():
    from datetime import datetime, timedelta, timezone

    overdue = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    signals = _proactive_signals(
        [
            {"id": "approved", "company_name": "Engedélyezett Kft.", "approved_to_contact": True,
             "opted_out": False, "next_follow_up_at": overdue},
            {"id": "no-consent", "company_name": "Tiltott Kft.", "approved_to_contact": False,
             "opted_out": False, "next_follow_up_at": overdue},
            {"id": "opted-out", "company_name": "Leiratkozott Kft.", "approved_to_contact": True,
             "opted_out": True, "next_follow_up_at": overdue},
        ],
        [
            {"id": "open", "title": "Lejárt feladat", "status": "open", "due_at": overdue},
            {"id": "done", "title": "Kész feladat", "status": "completed", "due_at": overdue},
            {"id": "invalid", "title": "Dátum nélküli", "status": "open", "due_at": "invalid"},
        ],
    )

    assert signals["overdue_task_count"] == 1
    assert signals["overdue_tasks"][0]["title"] == "Lejárt feladat"
    assert signals["overdue_approved_followup_count"] == 1
    assert signals["overdue_approved_followups"][0]["company_name"] == "Engedélyezett Kft."
    assert "nem automatikus műveletek" in signals["interpretation"]


def test_proactive_signals_bound_large_result_sets():
    from datetime import datetime, timedelta, timezone

    overdue = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    tasks = [
        {"title": f"Task {i}", "status": "open", "due_at": overdue}
        for i in range(40)
    ]
    leads = [
        {"id": str(i), "company_name": f"Lead {i}", "approved_to_contact": True,
         "opted_out": False, "next_follow_up_at": overdue}
        for i in range(40)
    ]
    signals = _proactive_signals(leads, tasks)
    assert signals["overdue_task_count"] == 40
    assert len(signals["overdue_tasks"]) == 30
    assert signals["overdue_approved_followup_count"] == 40
    assert len(signals["overdue_approved_followups"]) == 30


def test_global_research_trigger_requires_explicit_intent_and_honors_negation():
    assert _wants_global_research("Kérlek, végezz leadkutatást Németországban")
    assert _wants_global_research("Keress gyártókat Lengyelországban")
    assert _wants_global_research("Azonosíts potenciális ügyfeleket")
    assert not _wants_global_research("Ne keress új leadeket")
    assert not _wants_global_research("Ne kutass most")
    assert not _wants_global_research("Milyen lehetőségek vannak a piacon?")


def test_retrieve_context_loads_strategy_learning_analytics_and_proactive_signals(monkeypatch):
    monkeypatch.setitem(
        _NAMESPACE, "rank_researched_leads",
        lambda _rows, limit=20: [{
            "company_name": "Minta Kft.", "priority_score": 80,
            "business_fit_score": 75, "research_confidence": "high", "evidence_count": 2,
        }],
    )
    monkeypatch.setitem(_NAMESPACE, "build_market_intelligence", lambda _rows: {"pattern": "manufacturing"})
    monkeypatch.setitem(_NAMESPACE, "get_memories", lambda *_args, **_kwargs: [])
    monkeypatch.setitem(_NAMESPACE, "build_business_learning", lambda *_args: {"lesson": "review sources"})
    monkeypatch.setitem(_NAMESPACE, "build_chat_analytics_context", lambda _rows: "ANALYTICS_CONTEXT")
    monkeypatch.setitem(
        _NAMESPACE, "_website_profile",
        lambda url: {"status": "sikeresen beolvasva", "score": 88, "url": url},
    )
    db = FakeDB({
        "leads": [{
            "id": "lead-1", "company_name": "Minta Kft.", "website": "https://example.com",
            "status": "research", "approved_to_contact": False, "opted_out": False,
            "source": "gemini_google_search_grounding:example.com",
            "notes": "Leadkutatás; nyilvános vállalati adat",
        }],
        "tasks": [{
            "id": "task-1", "title": "Ajánlat ellenőrzése", "status": "open",
            "priority": "high", "due_at": "2020-01-01T00:00:00Z",
        }],
        "logs": [{
            "module": "chat", "level": "info", "message": "request",
            "created_at": "2026-11-22T10:00:00Z",
        }],
    })

    context, sources = retrieve_context(db, "Átfogó stratégiai analitika lead és feladat áttekintés")

    assert "KORÁBBI LEADKUTATÁS ALAPJÁN KÉSZÜLT PIACI INTELLIGENCIA" in context
    assert "ÜZLETI TANULÓMEMÓRIA" in context
    assert "WEBOLDAL-ALAPÚ LEADPONTOZÁS" in context
    assert "ANALYTICS_CONTEXT" in context
    assert "határidő- és utánkövetési jelzések" in sources
    assert "naplóalapú analitika" in sources
    assert "bizonyíték-alapú leadprioritás" in sources


def test_retrieve_context_draft_and_legacy_log_fallback_exclude_email_body():
    class LegacyLogsQuery(FakeQuery):
        def execute(self):
            if "operation_id" in self.columns:
                return FakeResponse([])
            return FakeResponse([{
                "module": "mailer", "level": "warning",
                "message": "legacy log row", "created_at": "2026-11-22T10:00:00Z",
            }])

    class LegacyLogsDB(FakeDB):
        def table(self, name):
            if name == "logs":
                self.calls.append(("table", name))
                return LegacyLogsQuery([], self.calls)
            return super().table(name)

    db = LegacyLogsDB({
        "leads": [{"id": "lead-1", "company_name": "Minta Kft.", "status": "new"}],
        "email_drafts": [{
            "id": "draft-1", "subject": "Biztonságos tárgy",
            "status": "draft", "body": "Személyes levéltörzs",
        }],
    })

    context, sources = retrieve_context(db, "Mutasd az e-mail piszkozatokat és naplókat")

    assert "Biztonságos tárgy" in context
    assert "Személyes levéltörzs" not in context
    assert "legacy log row" in context
    assert "e-mail-piszkozatok" in sources
    assert "naplók" in sources


def test_retrieve_context_generic_business_question_loads_bounded_leads_and_tasks():
    db = FakeDB({
        "leads": [{"id": "lead-1", "company_name": "Minta Kft.", "status": "new"}],
        "tasks": [{"id": "task-1", "title": "Első feladat", "status": "open"}],
    })

    context, sources = retrieve_context(db, "Szia JARVIS")

    assert "Minta Kft." in context
    assert "Első feladat" in context
    assert sources == ["leadek", "feladatok"]


def test_dashboard_website_profile_rejects_private_redirect_target(monkeypatch):
    import socket
    import safe_http

    _load_function("_public_http_url")
    website_profile = _load_function("_website_profile")
    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ],
    )

    class Redirect:
        status_code = 302
        headers = {"Location": "http://127.0.0.1/admin"}
        closed = False

        def close(self):
            self.closed = True

    response = Redirect()
    monkeypatch.setattr(safe_http, "safe_get", lambda *_args, **_kwargs: response)

    result = website_profile("https://example.com")

    assert result["status"] == "nem biztonságos átirányítási cél"
    assert response.closed


def test_dashboard_public_url_rejects_dns_resolving_to_private_address(monkeypatch):
    import socket

    public_http_url = _load_function("_public_http_url")
    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.10", 443))
        ],
    )
    assert public_http_url("https://internal.example") is None
    assert public_http_url("https://example.com:8443") is None
    assert public_http_url("https://user:password@example.com") is None
