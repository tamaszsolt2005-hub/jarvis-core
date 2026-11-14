"""Unit tests for JARVIS shared helpers; no live services or secrets required."""
from types import SimpleNamespace

import pytest

import jarvis_common


class FakeModels:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def generate_content(self, *, model, contents):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(text=outcome)


class FakeClient:
    def __init__(self, outcomes):
        self.models = FakeModels(outcomes)


def test_generate_text_returns_trimmed_response(monkeypatch):
    monkeypatch.setattr(jarvis_common, "get_model_name", lambda: "test-model")
    client = FakeClient(["  JARVIS válasz  "])
    assert jarvis_common.generate_text("hello", client) == "JARVIS válasz"
    assert client.models.calls == 1


def test_generate_text_retries_transient_503(monkeypatch):
    monkeypatch.setattr(jarvis_common, "get_model_name", lambda: "test-model")
    monkeypatch.setattr(jarvis_common, "env_int", lambda *args, **kwargs: 3)
    sleeps = []
    monkeypatch.setattr(jarvis_common.time, "sleep", sleeps.append)

    class ServiceUnavailable(Exception):
        code = 503
        status = "UNAVAILABLE"

    client = FakeClient([ServiceUnavailable("temporarily unavailable"), "recovered"])
    assert jarvis_common.generate_text("hello", client) == "recovered"
    assert client.models.calls == 2
    assert sleeps == [1]


def test_generate_text_stops_after_retry_limit(monkeypatch):
    monkeypatch.setattr(jarvis_common, "get_model_name", lambda: "test-model")
    monkeypatch.setattr(jarvis_common, "env_int", lambda *args, **kwargs: 3)
    sleeps = []
    monkeypatch.setattr(jarvis_common.time, "sleep", sleeps.append)

    class ServiceUnavailable(Exception):
        code = 503
        status = "UNAVAILABLE"

    client = FakeClient([ServiceUnavailable("503"), ServiceUnavailable("503"), ServiceUnavailable("503")])
    with pytest.raises(ServiceUnavailable):
        jarvis_common.generate_text("hello", client)
    assert client.models.calls == 3
    assert sleeps == [1, 2]


def test_generate_text_does_not_retry_auth_errors(monkeypatch):
    monkeypatch.setattr(jarvis_common, "get_model_name", lambda: "test-model")
    monkeypatch.setattr(jarvis_common, "env_int", lambda *args, **kwargs: 3)
    sleeps = []
    monkeypatch.setattr(jarvis_common.time, "sleep", sleeps.append)
    client = FakeClient([PermissionError("invalid credentials")])

    with pytest.raises(PermissionError):
        jarvis_common.generate_text("hello", client)
    assert client.models.calls == 1
    assert sleeps == []


def test_generate_text_rejects_empty_response(monkeypatch):
    monkeypatch.setattr(jarvis_common, "get_model_name", lambda: "test-model")
    client = FakeClient(["   "])
    with pytest.raises(RuntimeError, match="üres választ"):
        jarvis_common.generate_text("hello", client)


def test_env_int_uses_default_for_invalid_value(monkeypatch):
    monkeypatch.setattr(jarvis_common, "get_secret", lambda name: "not-a-number")
    assert jarvis_common.env_int("SOME_LIMIT", 3, minimum=1, maximum=5) == 3


def test_env_int_clamps_value(monkeypatch):
    monkeypatch.setattr(jarvis_common, "get_secret", lambda name: "99")
    assert jarvis_common.env_int("SOME_LIMIT", 3, minimum=1, maximum=5) == 5
