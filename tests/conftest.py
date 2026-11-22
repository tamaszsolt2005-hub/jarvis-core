"""Repository-wide guard against accidental network access in unit tests."""
import socket

import pytest


@pytest.fixture(autouse=True)
def block_unmocked_network(monkeypatch, request):
    """Fail closed on DNS and outbound sockets; opt-in live tests are explicitly marked."""
    if request.node.get_closest_marker("live_integration"):
        return

    def deny(*_args, **_kwargs):
        raise AssertionError(
            "A unit test attempted unmocked network access. Mock the external client "
            "or mark an explicitly approved live integration test."
        )

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(socket.socket, "sendto", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)
    monkeypatch.setattr(socket, "gethostbyname", deny)
    monkeypatch.setattr(socket, "gethostbyname_ex", deny)
    monkeypatch.setattr(socket, "gethostbyaddr", deny)
