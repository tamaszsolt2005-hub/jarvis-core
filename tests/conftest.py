"""Repository-wide guard against accidental network access in unit tests."""
import ipaddress
import os
import socket
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def block_unmocked_network(monkeypatch, request):
    """Fail closed; only the dedicated, explicitly enabled smoke-test file is exempt."""
    is_approved_live_test = (
        request.node.get_closest_marker("live_integration") is not None
        and Path(str(request.fspath)).name == "test_live_integrations.py"
        and os.getenv("JARVIS_LIVE_INTEGRATION_TESTS") == "1"
    )
    if is_approved_live_test:
        return

    is_browser_test = request.node.get_closest_marker("browser_e2e") is not None

    def deny(*_args, **_kwargs):
        raise AssertionError(
            "A unit test attempted unmocked network access. Mock the external client "
            "or use the dedicated opt-in live integration test file."
        )

    def loopback_only(address):
        host = address[0] if isinstance(address, tuple) and address else ""
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    if is_browser_test:
        original_connect = socket.socket.connect
        original_connect_ex = socket.socket.connect_ex
        original_create_connection = socket.create_connection
        original_getaddrinfo = socket.getaddrinfo

        def getaddrinfo_local(host, port, *args, **kwargs):
            try:
                allowed = ipaddress.ip_address(host).is_loopback
            except ValueError:
                allowed = False
            if not allowed:
                return deny(host)
            return original_getaddrinfo(host, port, *args, **kwargs)

        def connect_local(sock, address):
            if not loopback_only(address):
                return deny(address)
            return original_connect(sock, address)

        def connect_ex_local(sock, address):
            if not loopback_only(address):
                return deny(address)
            return original_connect_ex(sock, address)

        def create_connection_local(address, *args, **kwargs):
            if not loopback_only(address):
                return deny(address)
            return original_create_connection(address, *args, **kwargs)

        monkeypatch.setattr(socket.socket, "connect", connect_local)
        monkeypatch.setattr(socket.socket, "connect_ex", connect_ex_local)
        monkeypatch.setattr(socket, "create_connection", create_connection_local)
        monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo_local)
    else:
        monkeypatch.setattr(socket.socket, "connect", deny)
        monkeypatch.setattr(socket.socket, "connect_ex", deny)
        monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket.socket, "sendto", deny)
    if not is_browser_test:
        monkeypatch.setattr(socket, "getaddrinfo", deny)
    monkeypatch.setattr(socket, "gethostbyname", deny)
    monkeypatch.setattr(socket, "gethostbyname_ex", deny)
    monkeypatch.setattr(socket, "gethostbyaddr", deny)
