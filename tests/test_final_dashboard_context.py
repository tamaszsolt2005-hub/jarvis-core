"""Final Dashboard context and website audit branches, with all transport mocked."""
from __future__ import annotations

from types import SimpleNamespace

import requests


def test_dashboard_website_profile_scores_bounded_html_and_closes_response(monkeypatch):
    import dashboard
    import safe_http

    html = (
        "<html><head><title>Example Company</title>"
        '<meta name="description" content="Services and solutions for companies"></head>'
        "<body><p>About us, our company provides services, products and solutions. "
        "Contact phone, references, testimonials, request a quote, partners and customers. "
        + ("Business information. " * 60)
        + "</p><script>ignore this content</script></body></html>"
    ).encode()
    response = SimpleNamespace(
        status_code=200,
        headers={"Content-Type": "text/html; charset=utf-8"},
        iter_content=lambda chunk_size: [html[:100], html[100:]],
    )
    closed = []
    monkeypatch.setattr(dashboard, "_public_http_url", lambda _value: "https://public.example")
    monkeypatch.setattr(safe_http, "safe_get", lambda *_args, **_kwargs: response)
    monkeypatch.setattr(safe_http, "close_response", lambda value: closed.append(value))

    result = dashboard._website_profile("public.example")

    assert result["status"] == "sikeresen beolvasva"
    assert result["title"] == "Example Company"
    assert result["score"] > 50
    assert result["signals"]["kapcsolat"] is True
    assert result["signals"]["referenciak"] is True
    assert "ignore this content" not in result["content_excerpt"]
    assert closed == [response]


def test_dashboard_website_profile_reports_non_success_http_status(monkeypatch):
    import dashboard
    import safe_http

    response = SimpleNamespace(status_code=503, headers={})
    closed = []
    monkeypatch.setattr(dashboard, "_public_http_url", lambda _value: "https://public.example")
    monkeypatch.setattr(safe_http, "safe_get", lambda *_args, **_kwargs: response)
    monkeypatch.setattr(safe_http, "close_response", lambda value: closed.append(value))

    result = dashboard._website_profile("public.example")

    assert result["status"] == "HTTP 503"
    assert result["score"] == 0
    assert closed == [response]


def test_dashboard_website_profile_reports_transport_and_parser_failures(monkeypatch):
    import bs4
    import dashboard
    import safe_http

    monkeypatch.setattr(dashboard, "_public_http_url", lambda _value: "https://public.example")
    reports = []
    monkeypatch.setattr(
        dashboard, "report_error",
        lambda error, **kwargs: reports.append(kwargs),
    )
    monkeypatch.setattr(
        safe_http, "safe_get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(requests.Timeout("mock timeout")),
    )
    transport = dashboard._website_profile("public.example")
    assert "Timeout" in transport["status"]
    assert reports[-1]["operation"] == "audit_lead_website_http"

    response = SimpleNamespace(
        status_code=200,
        headers={"Content-Type": "text/html"},
        iter_content=lambda *_args: [b"<html></html>"],
    )
    monkeypatch.setattr(safe_http, "safe_get", lambda *_args, **_kwargs: response)
    monkeypatch.setattr(safe_http, "close_response", lambda _response: None)
    monkeypatch.setattr(
        bs4, "BeautifulSoup",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad html")),
    )
    parsed = dashboard._website_profile("public.example")
    assert "feldolgozási hiba" in parsed["status"]
    assert reports[-1]["operation"] == "audit_lead_website_parse"


def test_dashboard_retrieve_context_ranks_only_company_fields(monkeypatch):
    import dashboard

    rows = [{
        "id": str(index),
        "company_name": f"Company {index}",
        "website": f"https://company{index}.example",
        "status": "new",
        "email": "private@example.test",
        "notes": "human private note",
    } for index in range(35)]
    monkeypatch.setattr(
        dashboard, "_safe_rows",
        lambda _db, table, _columns, _limit, status=None: (
            status.update(ok=True, error=False) or (rows if table == "leads" else [])
        ),
    )
    inspected = []
    monkeypatch.setattr(
        dashboard, "_website_profile",
        lambda url: (inspected.append(url) or {
            "score": 50, "status": "sikeresen beolvasva", "url": url
        }),
    )

    context, loaded = dashboard.retrieve_context(object(), "Rangsorold a legjobb leadeket")

    assert len(inspected) == 30
    assert "lead-weboldalak és rangsorolás" in loaded
    assert "private@example.test" not in context
    assert "human private note" not in context


def test_dashboard_retrieve_context_does_not_invent_signals_when_sources_fail(monkeypatch):
    import dashboard

    def failed_read(_db, table, _columns, _limit, status=None):
        if status is not None:
            status.update(ok=False, error=True, error_type="OSError")
        return []

    monkeypatch.setattr(dashboard, "_safe_rows", failed_read)
    context, loaded = dashboard.retrieve_context(object(), "Milyen üzleti lehetőségek és sürgős feladatok vannak?")

    assert "lead-adatbázis lekérdezése nem sikerült" in context
    assert "feladat-adatbázis lekérdezése nem sikerült" in context
    assert "PROAKTÍV JELZÉSEK NEM KÉSZÜLTEK" in context
    assert "proaktív jelzések (adatforrás-hiba)" in loaded
