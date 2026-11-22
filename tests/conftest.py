"""Repository-wide guard against accidental network access in unit tests."""
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

    def deny(*_args, **_kwargs):
        raise AssertionError(
            "A unit test attempted unmocked network access. Mock the external client "
            "or use the dedicated opt-in live integration test file."
        )

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(socket.socket, "sendto", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)
    monkeypatch.setattr(socket, "gethostbyname", deny)
    monkeypatch.setattr(socket, "gethostbyname_ex", deny)
    monkeypatch.setattr(socket, "gethostbyaddr", deny)
