"""Second batch of final-path tests for shared configuration, consent and retry logic."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("", 512),
        ("röviden foglald össze", 384),
        ("részletesen elemezd", 3072),
        ("x" * 701 + " részletezd", 4096),
        ("a" * 901, 2048),
        ("a" * 400, 1536),
        ("a" * 121, 1024),
        ("a" * 50, 768),
        ("rövid", 512),
    ],
)
def test_response_token_estimator_covers_all_budgets(question, expected):
    from jarvis_common import estimate_response_tokens

    assert estimate_response_tokens(question) == expected


def test_shared_history_skips_empty_and_non_chat_messages_and_truncates():
    from jarvis_common import format_conversation_history

    result = format_conversation_history(
        [("system", "hidden"), ("user", "  "), ("assistant", "z" * 100)],
        max_chars=100,
        max_message_chars=30,
    )
    assert result.startswith("assistant: ")
    assert "üzenet rövidítve" in result


def test_get_secret_reports_unexpected_streamlit_secret_failure(monkeypatch):
    import jarvis_common

    reports = []
    monkeypatch.setenv("JARVIS_TEST_SECRET", "env-fallback")
    monkeypatch.setattr(
        jarvis_common, "report_error",
        lambda error, **kwargs: reports.append(kwargs),
    )

    class Secrets:
        def get(self, _name):
            raise RuntimeError("fake secrets backend")

    class FakeStreamlit:
        secrets = Secrets()

    monkeypatch.setitem(__import__("sys").modules, "streamlit", FakeStreamlit())
    assert jarvis_common.get_secret("JARVIS_TEST_SECRET") == "env-fallback"
    assert reports and reports[0]["operation"] == "read_streamlit_secret:JARVIS_TEST_SECRET"


def test_env_helpers_use_defaults_and_clamp_invalid_values(monkeypatch):
    import jarvis_common

    monkeypatch.setattr(jarvis_common, "get_secret", lambda _name: None)
    assert jarvis_common.env_bool("FLAG", True) is True
    assert jarvis_common.env_int("COUNT", 5, 1, 10) == 5
    monkeypatch.setattr(jarvis_common, "get_secret", lambda _name: "not-an-int")
    assert jarvis_common.env_int("COUNT", 5, 1, 10) == 5
    monkeypatch.setattr(jarvis_common, "get_secret", lambda _name: "99")
    assert jarvis_common.env_int("COUNT", 5, 1, 10) == 10


def test_generate_text_rethrows_non_transient_primary_error(monkeypatch):
    import jarvis_common

    class Models:
        def generate_content(self, **_kwargs):
            raise ValueError("invalid request")

    monkeypatch.setattr(jarvis_common, "get_model_name", lambda: "gemini-test")
    monkeypatch.setattr(jarvis_common, "env_int", lambda *_args, **_kwargs: 1)
    with pytest.raises(ValueError, match="invalid request"):
        jarvis_common.generate_text("prompt", SimpleNamespace(models=Models()))


def test_generate_text_empty_primary_response_fails_closed(monkeypatch):
    import jarvis_common

    class Models:
        def generate_content(self, **_kwargs):
            return SimpleNamespace(text="  ")

    monkeypatch.setattr(jarvis_common, "get_model_name", lambda: "gemini-test")
    monkeypatch.setattr(jarvis_common, "env_int", lambda *_args, **_kwargs: 1)
    with pytest.raises(RuntimeError, match="üres választ"):
        jarvis_common.generate_text("prompt", SimpleNamespace(models=Models()))


def test_audit_result_sanitizer_limits_depth_and_collection_size():
    import jarvis_common

    class DB:
        def __init__(self):
            self.row = None
        def table(self, _name):
            return self
        def insert(self, row):
            self.row = row
            return self
        def execute(self):
            return SimpleNamespace(data=[])

    db = DB()
    deep = {"level": {"level": {"level": {"level": {"level": {"level": "hidden"}}}}}}
    assert jarvis_common.audit_event(
        db, module="test", action="depth", status="success", result=deep
    )
    assert "[DEPTH_LIMIT]" in str(db.row["result"])


def test_follow_up_eligibility_rejects_malformed_timestamp_and_count():
    from follow_up import _eligible_for_follow_up

    now = datetime.now(timezone.utc)
    base = {
        "status": "sent",
        "consent_basis": "consent",
        "approved_to_contact": True,
        "consent_confirmed_at": now.isoformat(),
        "opted_out": False,
        "email": "person@example.test",
        "next_follow_up_at": "not-a-date",
        "follow_up_count": 0,
    }
    assert not _eligible_for_follow_up(base, now)
    malformed_count = dict(base, next_follow_up_at=now.isoformat(), follow_up_count="bad")
    assert not _eligible_for_follow_up(malformed_count, now)


def test_email_sender_due_follow_up_rejects_bad_timestamp_and_count():
    from email_sender import _due_follow_up

    now = datetime.now(timezone.utc)
    base = {
        "status": "sent",
        "opted_out": False,
        "next_follow_up_at": "not-a-date",
        "follow_up_count": 0,
    }
    assert not _due_follow_up(base, now)
    malformed_count = dict(base, next_follow_up_at=now.isoformat(), follow_up_count="bad")
    assert not _due_follow_up(malformed_count, now)


def test_email_sender_invalid_lead_is_rejected_before_database_or_smtp():
    from email_sender import _send_one

    class DB:
        def table(self, _name):
            raise AssertionError("invalid lead must not touch database")

    lead = {
        "id": "lead-1", "status": "new", "email": "bad-address",
        "consent_basis": "consent", "approved_to_contact": True,
        "opted_out": False,
        "consent_confirmed_at": datetime.now(timezone.utc).isoformat(),
    }
    assert not _send_one(DB(), lead, False, datetime.now(timezone.utc))


def test_global_research_url_rejects_credentials_and_local_hosts():
    from global_lead_research import _valid_http_url

    assert _valid_http_url("https://user:password@example.test") is None
    assert _valid_http_url("https://localhost/private") is None
    assert _valid_http_url("javascript:alert(1)") is None
    assert _valid_http_url("https://example.test/" + "x" * 2050) is None


def test_global_research_parser_rejects_invalid_json_and_non_list_companies():
    from global_lead_research import _parse_companies

    assert _parse_companies("not-json") == []
    assert _parse_companies('{"companies": "not-a-list"}') == []
    assert _parse_companies('{"companies": [{"company_name": "ok"}, null]}') == [
        {"company_name": "ok"}
    ]


def test_global_research_grounding_field_accepts_dict_and_object_shapes():
    from global_lead_research import _grounded_sources

    response = {
        "candidates": [{
            "grounding_metadata": {
                "grounding_chunks": [
                    {"web": {"uri": "https://one.example"}},
                    {"web": {"uri": "https://two.example"}},
                    {"web": {}},
                ]
            }
        }]
    }
    assert _grounded_sources(response) == [
        "https://one.example", "https://two.example"
    ]


def test_global_research_quality_handles_bad_score_and_missing_fit():
    from global_lead_research import _research_quality

    confidence, score, evidence = _research_quality({
        "fit_evidence": ["evidence"],
        "research_confidence": "unknown",
        "business_fit_score": "NaN",
        "potential_fit": "",
    })
    assert confidence == "low"
    assert score is None
    assert evidence == ["evidence"]
