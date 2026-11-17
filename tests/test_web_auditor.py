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
        self.raw = Raw(body)
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
