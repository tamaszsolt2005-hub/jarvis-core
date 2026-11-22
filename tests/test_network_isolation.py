"""Sanity checks for the autouse outbound-network guard."""
import socket

import pytest


def test_unit_test_network_guard_blocks_dns_and_tcp(monkeypatch):
    def deny(*_args, **_kwargs):
        raise AssertionError("network blocked")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)

    with pytest.raises(AssertionError, match="network blocked"):
        socket.getaddrinfo("example.com", 443)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        with pytest.raises(AssertionError, match="network blocked"):
            client.connect(("93.184.216.34", 443))


@pytest.mark.live_integration
def test_live_marker_outside_allowlisted_file_does_not_disable_network_guard():
    with pytest.raises(AssertionError, match="unmocked network access"):
        socket.getaddrinfo("example.com", 443)
