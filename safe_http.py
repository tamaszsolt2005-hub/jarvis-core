"""SSRF-resistant HTTP fetches with DNS resolution pinned to a validated public IP."""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter


class _PinnedIPAdapter(HTTPAdapter):
    """Connect to a previously validated IP while preserving HTTP Host and TLS SNI."""

    def __init__(self, hostname: str, address: str, **kwargs):
        self.hostname = hostname
        self.address = address
        super().__init__(**kwargs)

    def get_connection(self, url, proxies=None):
        if proxies:
            raise requests.exceptions.InvalidProxyURL("Proxy használata biztonsági okból tiltott.")
        parsed = urlsplit(url)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        pool_kwargs = {}
        if parsed.scheme == "https":
            pool_kwargs.update(server_hostname=self.hostname, assert_hostname=self.hostname)
        return self.poolmanager.connection_from_host(
            self.address, port=port, scheme=parsed.scheme, pool_kwargs=pool_kwargs
        )


def _validated_public_address(hostname: str, port: int) -> str:
    try:
        literal = ipaddress.ip_address(hostname)
        if not literal.is_global:
            raise ValueError("Nem nyilvános IP-cím.")
        return str(literal)
    except ValueError as exc:
        # A ValueError for a non-IP hostname is expected; a parsed private IP is not.
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            pass
        else:
            raise ValueError("Nem nyilvános IP-cím.") from exc

    try:
        answers = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError("A webcím DNS-feloldása sikertelen.") from exc
    addresses = list(dict.fromkeys(answer[4][0] for answer in answers))
    if not addresses:
        raise ValueError("A webcímhez nem található IP-cím.")
    parsed_addresses = [ipaddress.ip_address(address) for address in addresses]
    if any(not address.is_global for address in parsed_addresses):
        raise ValueError("A webcím nem nyilvános hálózatra mutat.")
    return str(parsed_addresses[0])


def safe_get(url: str, *, timeout=(4, 8), headers=None, stream=True):
    """GET a public HTTP(S) URL without a second, unpinned DNS lookup."""
    parsed = urlsplit(str(url or ""))
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or len(str(url)) > 2048
    ):
        raise ValueError("Érvénytelen vagy nem biztonságos HTTP(S) cím.")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    expected_port = 443 if parsed.scheme == "https" else 80
    if port != expected_port:
        raise ValueError("Csak a szabványos HTTP/HTTPS port engedélyezett.")
    address = _validated_public_address(parsed.hostname, port)

    session = requests.Session()
    session.trust_env = False
    adapter = _PinnedIPAdapter(parsed.hostname, address)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    try:
        response = session.get(
            url, timeout=timeout, allow_redirects=False,
            headers=headers or {}, stream=stream,
        )
        response._jarvis_session = session
        return response
    except Exception:
        session.close()
        raise


def close_response(response) -> None:
    if response is None:
        return
    session = getattr(response, "_jarvis_session", None)
    try:
        response.close()
    finally:
        if session is not None:
            session.close()
