"""Negative and positive tests for DNS-pinned public HTTP transport; no live network."""
import socket

import pytest
import requests

import safe_http


@pytest.mark.parametrize("host", ["127.0.0.1", "10.0.0.1", "::1", "169.254.169.254"])
def test_public_address_rejects_private_literal_ips(host):
    with pytest.raises(ValueError, match="Nem nyilvános"):
        safe_http._validated_public_address(host, 443)


def test_public_address_accepts_global_literal_without_dns(monkeypatch):
    monkeypatch.setattr(
        safe_http.socket, "getaddrinfo",
        lambda *_args, **_kwargs: pytest.fail("literal IP must not trigger DNS"),
    )
    assert safe_http._validated_public_address("8.8.8.8", 443) == "8.8.8.8"


def test_public_address_rejects_dns_failure_empty_and_mixed_answers(monkeypatch):
    monkeypatch.setattr(
        safe_http.socket, "getaddrinfo",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(socket.gaierror("mock DNS failure")),
    )
    with pytest.raises(ValueError, match="DNS-feloldása"):
        safe_http._validated_public_address("missing.example", 443)

    monkeypatch.setattr(safe_http.socket, "getaddrinfo", lambda *_args, **_kwargs: [])
    with pytest.raises(ValueError, match="nem található IP-cím"):
        safe_http._validated_public_address("empty.example", 443)

    monkeypatch.setattr(
        safe_http.socket, "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.8", 443)),
        ],
    )
    with pytest.raises(ValueError, match="nem nyilvános hálózatra"):
        safe_http._validated_public_address("mixed.example", 443)


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "ftp://example.com", "https://user:pass@example.com",
    "https://example.com:8443", "https://example.com:99999", "https://" + "x" * 2050,
])
def test_safe_get_rejects_invalid_urls_before_session_creation(monkeypatch, url):
    monkeypatch.setattr(
        safe_http.requests, "Session",
        lambda: pytest.fail("invalid URL must fail before creating a session"),
    )
    with pytest.raises(ValueError):
        safe_http.safe_get(url)


def test_safe_get_pins_validated_address_and_closes_owned_session(monkeypatch):
    calls = {}

    class Response:
        _jarvis_session = None
        def close(self):
            calls["response_closed"] = True

    response = Response()

    class Session:
        def __init__(self):
            self.trust_env = True
            self.mounted = {}
        def mount(self, prefix, adapter):
            self.mounted[prefix] = adapter
        def get(self, url, **kwargs):
            calls["request"] = (url, kwargs)
            return response
        def close(self):
            calls["session_closed"] = True

    session = Session()
    monkeypatch.setattr(safe_http, "_validated_public_address", lambda host, port: "8.8.8.8")
    monkeypatch.setattr(safe_http.requests, "Session", lambda: session)

    result = safe_http.safe_get("https://example.com/path", headers={"X-Test": "yes"})

    assert result is response
    assert session.trust_env is False
    assert set(session.mounted) == {"http://", "https://"}
    assert all(isinstance(adapter, safe_http._PinnedIPAdapter) for adapter in session.mounted.values())
    assert calls["request"][1]["allow_redirects"] is False
    assert calls["request"][1]["headers"] == {"X-Test": "yes"}
    safe_http.close_response(result)
    assert calls["response_closed"] is True
    assert calls["session_closed"] is True


def test_safe_get_closes_session_when_transport_raises(monkeypatch):
    closed = []
    class Session:
        trust_env = True
        def mount(self, *_args):
            pass
        def get(self, *_args, **_kwargs):
            raise requests.Timeout("mock timeout")
        def close(self):
            closed.append(True)
    monkeypatch.setattr(safe_http, "_validated_public_address", lambda *_args: "8.8.8.8")
    monkeypatch.setattr(safe_http.requests, "Session", Session)

    with pytest.raises(requests.Timeout):
        safe_http.safe_get("https://example.com")
    assert closed == [True]


def test_pinned_adapter_rejects_proxy_and_preserves_https_hostname():
    adapter = safe_http._PinnedIPAdapter("example.com", "8.8.8.8")
    with pytest.raises(requests.exceptions.InvalidProxyURL):
        adapter.get_connection("https://example.com", proxies={"https": "http://proxy.invalid"})

    calls = {}
    class PoolManager:
        def connection_from_host(self, host, **kwargs):
            calls["host"] = host
            calls["kwargs"] = kwargs
            return "pinned-connection"
    adapter.poolmanager = PoolManager()

    assert adapter.get_connection("https://example.com/path") == "pinned-connection"
    assert calls["host"] == "8.8.8.8"
    assert calls["kwargs"]["pool_kwargs"] == {
        "server_hostname": "example.com", "assert_hostname": "example.com"
    }
