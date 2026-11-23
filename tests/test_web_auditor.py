from web_auditor import audit_company_website, MAX_BYTES


class Raw:
    def __init__(self, body=b"<html><title>Example</title><p>Business information</p></html>"):
        self.body = body
        self.requested = None

    def read(self, amount, decode_content=True):
        self.requested = amount
        return self.body[:amount]


class Response:
    def __init__(self, status=200, headers=None, body=None):
        self.status_code = status
        self.headers = headers or {"Content-Type": "text/html; charset=utf-8"}
        self.raw = Raw(body if body is not None else b"<html><title>Example</title><p>Business information</p></html>")
        self.closed = False

    def close(self):
        self.closed = True


def test_auditor_returns_title_and_sample_and_closes_response(monkeypatch):
    import web_auditor
    response = Response()
    monkeypatch.setattr(web_auditor, "_validated_url", lambda value: value)
    monkeypatch.setattr(web_auditor, "safe_get", lambda *args, **kwargs: response)

    result = audit_company_website("https://example.com")
    assert "Example" in result
    assert "Business information" in result
    assert response.raw.requested == MAX_BYTES
    assert response.closed


def test_auditor_validates_redirect_target_and_closes_redirect_response(monkeypatch):
    import web_auditor
    redirect = Response(302, {"Location": "http://127.0.0.1/admin"})
    monkeypatch.setattr(web_auditor, "_validated_url", lambda value: None if "127.0.0.1" in value else value)
    monkeypatch.setattr(web_auditor, "safe_get", lambda *args, **kwargs: redirect)

    result = audit_company_website("https://example.com")
    assert "nem biztonságos címre" in result
    assert redirect.closed


def test_auditor_reports_http_error_and_non_html(monkeypatch):
    import web_auditor
    monkeypatch.setattr(web_auditor, "_validated_url", lambda value: value)
    error = Response(503)
    monkeypatch.setattr(web_auditor, "safe_get", lambda *args, **kwargs: error)
    assert "503" in audit_company_website("https://example.com")
    assert error.closed

    binary = Response(200, {"Content-Type": "application/pdf"})
    monkeypatch.setattr(web_auditor, "safe_get", lambda *args, **kwargs: binary)
    assert "nem HTML" in audit_company_website("https://example.com")
    assert binary.closed


def test_auditor_rejects_missing_or_invalid_url_without_network(monkeypatch):
    import web_auditor
    monkeypatch.setattr(web_auditor, "safe_get", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network called")))
    assert "Nem adott meg" in audit_company_website(None)
    monkeypatch.setattr(web_auditor, "_validated_url", lambda _value: None)
    assert "Érvénytelen" in audit_company_website("file:///etc/passwd")


def test_public_host_rejects_localhost_and_any_private_dns_answer(monkeypatch):
    import socket
    import web_auditor

    assert web_auditor._is_public_host("localhost") is False

    def mixed_answers(*_args, **_kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.8", 0)),
        ]

    monkeypatch.setattr(web_auditor.socket, "getaddrinfo", mixed_answers)
    assert web_auditor._is_public_host("mixed.example") is False


def test_public_host_accepts_only_all_global_addresses(monkeypatch):
    import socket
    import web_auditor

    monkeypatch.setattr(
        web_auditor.socket, "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", 0)),
        ],
    )
    assert web_auditor._is_public_host("public.example") is True


def test_validated_url_rejects_credentials_ports_schemes_and_oversized_values(monkeypatch):
    import web_auditor

    monkeypatch.setattr(web_auditor, "_is_public_host", lambda _host: True)
    assert web_auditor._validated_url("https://user:pass@example.com") is None
    assert web_auditor._validated_url("https://example.com:8443") is None
    assert web_auditor._validated_url("file:///etc/passwd") is None
    assert web_auditor._validated_url("x" * 2049) is None
    assert web_auditor._validated_url("example.com") == "https://example.com"


def test_redirect_without_location_is_reported_and_response_is_closed(monkeypatch):
    import web_auditor

    response = Response(302, {"Content-Type": "text/html"})
    monkeypatch.setattr(web_auditor, "_validated_url", lambda value: value)
    monkeypatch.setattr(web_auditor, "safe_get", lambda *_args, **_kwargs: response)

    result = web_auditor.audit_company_website("https://example.com")

    assert "nem adott célcímet" in result
    assert response.closed


def test_redirect_limit_is_enforced_and_each_response_is_closed(monkeypatch):
    import web_auditor

    responses = []

    def redirect(*_args, **_kwargs):
        response = Response(302, {"Location": "/next"})
        responses.append(response)
        return response

    monkeypatch.setattr(web_auditor, "_validated_url", lambda value: value)
    monkeypatch.setattr(web_auditor, "safe_get", redirect)

    result = web_auditor.audit_company_website("https://example.com")

    assert "túl sok átirányítást" in result
    assert len(responses) == 4
    assert all(response.closed for response in responses)


def test_http_transport_error_is_reported_and_returned(monkeypatch):
    import requests
    import web_auditor

    reports = []
    monkeypatch.setattr(web_auditor, "_validated_url", lambda value: value)
    monkeypatch.setattr(
        web_auditor, "safe_get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(requests.Timeout("mock timeout")),
    )
    monkeypatch.setattr(
        web_auditor, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )

    result = web_auditor.audit_company_website("https://example.com")

    assert "Timeout" in result
    assert reports[0][1]["module"] == "web_auditor"
    assert reports[0][1]["severity"] == "warning"


def test_unexpected_parser_error_is_reported_and_response_is_closed(monkeypatch):
    import web_auditor

    response = Response()
    reports = []
    monkeypatch.setattr(web_auditor, "_validated_url", lambda value: value)
    monkeypatch.setattr(web_auditor, "safe_get", lambda *_args, **_kwargs: response)
    monkeypatch.setattr(
        web_auditor, "BeautifulSoup",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("mock parser failure")),
    )
    monkeypatch.setattr(
        web_auditor, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )

    result = web_auditor.audit_company_website("https://example.com")

    assert "RuntimeError" in result
    assert response.closed
    assert reports[0][1]["operation"] == "audit_company_website_parse"
