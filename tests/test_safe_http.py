import socket

import pytest

import safe_http


def test_safe_transport_pins_dns_resolution_to_public_ip(monkeypatch):
    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ],
    )

    adapter = safe_http._PinnedIPAdapter("example.com", "93.184.216.34")
    pool = adapter.get_connection("https://example.com/path")
    assert pool.host == "93.184.216.34"
    assert pool.assert_hostname == "example.com"
    adapter.close()


def test_safe_transport_rejects_private_and_mixed_dns_answers(monkeypatch):
    with pytest.raises(ValueError, match="nyilvános"):
        safe_http._validated_public_address("127.0.0.1", 80)

    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.4", 443)),
        ],
    )
    with pytest.raises(ValueError, match="nyilvános"):
        safe_http._validated_public_address("rebind.example", 443)


def test_safe_transport_disables_environment_proxies_and_pins_session(monkeypatch):
    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ],
    )
    captured = {}

    class FakeResponse:
        def close(self):
            captured["response_closed"] = True

    class FakeSession:
        def __init__(self):
            self.trust_env = True
            self.adapters = {}
        def mount(self, prefix, adapter):
            self.adapters[prefix] = adapter
        def get(self, url, **kwargs):
            captured["url"] = url
            captured["kwargs"] = kwargs
            captured["trust_env"] = self.trust_env
            captured["adapter"] = self.adapters["https://"]
            return FakeResponse()
        def close(self):
            captured["session_closed"] = True

    monkeypatch.setattr(safe_http.requests, "Session", FakeSession)
    response = safe_http.safe_get("https://example.com/test")
    assert captured["trust_env"] is False
    assert captured["url"] == "https://example.com/test"
    assert captured["adapter"].address == "93.184.216.34"
    safe_http.close_response(response)
    assert captured["response_closed"] is True
    assert captured["session_closed"] is True


def test_safe_transport_rejects_credentials_and_non_http_schemes():
    with pytest.raises(ValueError):
        safe_http.safe_get("file:///etc/passwd")
    with pytest.raises(ValueError):
        safe_http.safe_get("https://user:password@example.com")
