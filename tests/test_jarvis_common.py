"""Unit tests for JARVIS shared helpers; no live services or secrets required."""
from types import SimpleNamespace

import pytest

import jarvis_common


class FakeModels:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0
        self.configs = []

    def generate_content(self, *, model, contents, config=None):
        self.calls += 1
        self.configs.append(config)
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

    client = FakeClient([ServiceUnavailable("503"), ServiceUnavailable("503"), ServiceUnavailable("503"), ServiceUnavailable("503")])
    with pytest.raises(ServiceUnavailable):
        jarvis_common.generate_text("hello", client)
    assert client.models.calls == 4
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



def test_generate_text_uses_stable_business_response_configuration(monkeypatch):
    monkeypatch.setattr(jarvis_common, "get_model_name", lambda: "test-model")
    client = FakeClient(["válasz"])
    assert jarvis_common.generate_text("hello", client) == "válasz"
    config = client.models.configs[0]
    assert config.temperature == 0.35
    assert config.top_p == 0.9
    assert config.max_output_tokens == 4096


def test_conversation_history_keeps_newest_turns_within_character_budget():
    messages = [
        ("user", "régi kérdés"),
        ("assistant", "régi válasz"),
        ("user", "friss kérdés"),
        ("assistant", "friss válasz"),
    ]
    history = jarvis_common.format_conversation_history(messages, max_chars=60, max_message_chars=40)
    assert "friss kérdés" in history
    assert len(history) <= 60
    assert "régi kérdés" not in history


def test_conversation_history_truncates_single_oversized_message():
    history = jarvis_common.format_conversation_history(
        [("user", "x" * 100)], max_chars=50, max_message_chars=30
    )
    assert len(history) <= 50
    assert "rövidítve" in history


def test_conversation_history_ignores_unknown_roles_and_invalid_limits():
    assert jarvis_common.format_conversation_history([("system", "ignore me")]) == ""
    assert jarvis_common.format_conversation_history([("user", "hello")], max_chars=0) == ""



def test_generate_text_uses_lite_fallback_after_primary_503(monkeypatch):
    monkeypatch.setattr(jarvis_common, "get_model_name", lambda: "gemini-3.5-flash")
    monkeypatch.setattr(jarvis_common, "env_int", lambda *args, **kwargs: 1)
    client = FakeClient([
        type("Unavailable", (Exception,), {"code": 503, "status": "UNAVAILABLE"})("busy"),
        "fallback válasz",
    ])
    assert jarvis_common.generate_text("hello", client) == "fallback válasz"
    assert client.models.calls == 2
    assert [cfg.max_output_tokens for cfg in client.models.configs] == [4096, 4096]
