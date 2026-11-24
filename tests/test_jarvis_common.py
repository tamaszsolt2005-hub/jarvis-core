"""Unit tests for JARVIS shared helpers; no live services or secrets required."""
from types import SimpleNamespace

import pytest

import jarvis_common


class FakeModels:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0
        self.configs = []
        self.model_calls = []

    def generate_content(self, *, model, contents, config=None):
        self.calls += 1
        self.configs.append(config)
        self.model_calls.append(model)
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

    client = FakeClient([
        ServiceUnavailable("503"), ServiceUnavailable("503"), ServiceUnavailable("503"),
        ServiceUnavailable("503"), ServiceUnavailable("503"),
    ])
    with pytest.raises(ServiceUnavailable):
        jarvis_common.generate_text("hello", client)
    # Three primary attempts, then one attempt for each fallback model.
    assert client.models.calls == 5
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
    assert config.max_output_tokens == 8192


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



def test_generate_text_uses_current_flash_fallback_after_primary_503(monkeypatch):
    monkeypatch.setattr(jarvis_common, "get_model_name", lambda: "gemini-3.5-flash")
    monkeypatch.setattr(jarvis_common, "env_int", lambda *args, **kwargs: 1)
    client = FakeClient([
        type("Unavailable", (Exception,), {"code": 503, "status": "UNAVAILABLE"})("busy"),
        "fallback válasz",
    ])
    assert jarvis_common.generate_text("hello", client) == "fallback válasz"
    assert client.models.calls == 2
    assert client.models.model_calls == ["gemini-3.5-flash", "gemini-3.8-flash"]
    assert [cfg.max_output_tokens for cfg in client.models.configs] == [8192, 8192]


def test_generate_text_uses_fallback_after_primary_429(monkeypatch):
    monkeypatch.setattr(jarvis_common, "get_model_name", lambda: "gemini-3.5-flash")
    monkeypatch.setattr(jarvis_common, "env_int", lambda *args, **kwargs: 1)
    quota_error = type("QuotaExceeded", (Exception,), {"code": 429, "status": "RESOURCE_EXHAUSTED"})(
        "429 RESOURCE_EXHAUSTED"
    )
    client = FakeClient([quota_error, "fallback válasz"])

    assert jarvis_common.generate_text("hello", client) == "fallback válasz"
    assert client.models.model_calls == ["gemini-3.5-flash", "gemini-3.8-flash"]


def test_generate_text_uses_gemini_38_supported_generation_config(monkeypatch):
    monkeypatch.setattr(jarvis_common, "get_model_name", lambda: "gemini-3.8-flash")
    client = FakeClient(["válasz"])

    assert jarvis_common.generate_text("hello", client) == "válasz"
    config = client.models.configs[0]
    assert config.max_output_tokens == 8192
    assert config.temperature is None
    assert config.top_p is None



def test_required_secret_points_to_runtime_secret_locations(monkeypatch):
    monkeypatch.setattr(jarvis_common, "get_secret", lambda _name: None)
    with pytest.raises(RuntimeError) as error:
        jarvis_common.required_secret("GEMINI_API_KEY")
    assert "Codespaces secretként" in str(error.value)
    assert ".streamlit/secrets.toml" in str(error.value)
    assert "GitHub Actions Secretként" not in str(error.value)



@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Szia!", 512),
        ("Mi az a CRM?", 512),
        ("Hogyan működik a CRM rendszer egy kisebb vállalkozás napi folyamataiban?", 768),
        ("Mutasd be a CRM előnyeit és hátrányait több szempontból, térj ki a bevezetésre, költségekre, kockázatokra és a mérhető üzleti eredményekre is.", 2048),
        ("Elemezd részletesen a CRM bevezetésének kockázatait.", 3072),
        ("Röviden elemezd a CRM-et.", 384),
    ],
)
def test_estimate_response_tokens_adapts_to_question_complexity(question, expected):
    assert jarvis_common.estimate_response_tokens(question) == expected


def test_generate_text_uses_requested_output_token_budget(monkeypatch):
    monkeypatch.setattr(jarvis_common, "get_model_name", lambda: "gemini-3.8-flash")
    client = FakeClient(["rövid válasz"])
    assert jarvis_common.generate_text("hello", client, max_output_tokens=512) == "rövid válasz"
    assert client.models.configs[0].max_output_tokens == 512


def test_generate_text_clamps_output_token_budget(monkeypatch):
    monkeypatch.setattr(jarvis_common, "get_model_name", lambda: "gemini-3.8-flash")
    client = FakeClient(["válasz"])
    jarvis_common.generate_text("hello", client, max_output_tokens=50000)
    assert client.models.configs[0].max_output_tokens == 8192


def test_legacy_dashboard_factory_delegates_only_to_service_factory(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(jarvis_common, "get_service_supabase", lambda: sentinel)
    assert jarvis_common.get_legacy_dashboard_supabase() is sentinel
    assert jarvis_common.get_supabase() is sentinel


def test_user_factory_delegates_to_verified_jwt_client(monkeypatch):
    import jarvis_auth

    sentinel_client = object()
    refreshed = {"access_token": "new", "refresh_token": "new-refresh"}
    monkeypatch.setattr(
        jarvis_auth,
        "verified_user_client",
        lambda session, allowed_roles=None: (sentinel_client, refreshed),
    )
    client, current_session = jarvis_common.get_user_supabase(
        {"access_token": "old", "refresh_token": "old-refresh", "user_id": "u1"},
        allowed_roles={"operator"},
    )
    assert client is sentinel_client
    assert current_session is refreshed



def test_enforced_user_client_is_disabled_by_default(monkeypatch):
    monkeypatch.setattr(jarvis_common, "env_bool", lambda *_args, **_kwargs: False)
    assert jarvis_common.get_enforced_user_supabase(
        None, "leads.write", allowed_roles={"admin", "operator"}
    ) is None


def test_enforced_user_client_denies_missing_session_before_client_creation(monkeypatch):
    monkeypatch.setattr(jarvis_common, "env_bool", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        jarvis_common, "get_user_supabase",
        lambda *_args, **_kwargs: pytest.fail("Missing session must be rejected before client creation"),
    )
    with pytest.raises(PermissionError, match="Auth-munkamenet"):
        jarvis_common.get_enforced_user_supabase(
            None, "leads.write", allowed_roles={"admin", "operator"}
        )


def test_enforced_user_client_checks_permission_and_refreshes_session(monkeypatch):
    monkeypatch.setattr(jarvis_common, "env_bool", lambda *_args, **_kwargs: True)
    client = object()
    session = {"access_token": "old", "refresh_token": "old-refresh", "user_id": "u1"}
    refreshed = {
        "access_token": "new", "refresh_token": "new-refresh",
        "user_id": "u1", "role": "operator",
    }
    monkeypatch.setattr(
        jarvis_common, "get_user_supabase",
        lambda supplied, *, allowed_roles: (client, refreshed),
    )
    result = jarvis_common.get_enforced_user_supabase(
        session, "leads.write", allowed_roles={"admin", "operator"}
    )
    assert result == (client, refreshed)
    assert session == refreshed


def test_enforced_user_client_denies_role_without_permission(monkeypatch):
    monkeypatch.setattr(jarvis_common, "env_bool", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        jarvis_common, "get_user_supabase",
        lambda *_args, **_kwargs: (object(), {"role": "reader"}),
    )
    with pytest.raises(PermissionError, match="leads.write"):
        jarvis_common.get_enforced_user_supabase(
            {"access_token": "a", "refresh_token": "r", "user_id": "u1"},
            "leads.write", allowed_roles={"admin", "operator", "reader"},
        )
