from datetime import datetime, timedelta, timezone

from chat_email import (
    build_chat_email_draft,
    extract_explicit_recipient,
    is_chat_email_request,
)
from email_inbox import _is_optout
from email_sender import _due_follow_up, _valid_consent


def test_chat_email_request_handles_hungarian_inflections():
    assert is_chat_email_request("Küldj neki egy emailt a szolgáltatásról")
    assert is_chat_email_request("Írj egy e-mailt erről")
    assert not is_chat_email_request("Készíts egy üzleti elemzést")


def test_chat_email_requires_explicit_address():
    assert extract_explicit_recipient("Küldj emailt a teszt@example.com címre") == "teszt@example.com"
    assert extract_explicit_recipient("Küldj emailt Péternek") is None


def test_chat_email_draft_parses_subject_and_body():
    def fake_generate(prompt, max_output_tokens):
        assert "Ne küldd el" in prompt
        assert max_output_tokens == 1200
        return "Tárgy: Rövid bemutatkozás\n\nKedves Partner!\nSzeretnék egyeztetni."

    subject, body = build_chat_email_draft(
        "Küldj emailt a teszt@example.com címre a szolgáltatásunkról", fake_generate
    )
    assert subject == "Rövid bemutatkozás"
    assert "Kedves Partner" in body


def test_background_requires_timestamped_explicit_consent():
    valid = {
        "consent_basis": "consent",
        "approved_to_contact": True,
        "opted_out": False,
        "consent_confirmed_at": "2026-11-20T10:00:00+00:00",
    }
    assert _valid_consent(valid)
    assert not _valid_consent({**valid, "consent_confirmed_at": None})
    assert not _valid_consent({**valid, "approved_to_contact": False})
    assert not _valid_consent({**valid, "opted_out": True})
    assert not _valid_consent({**valid, "consent_basis": "legitimate_interest"})


def test_follow_up_is_only_due_for_eligible_unreplied_lead(monkeypatch):
    monkeypatch.setenv("MAX_FOLLOW_UPS", "2")
    now = datetime.now(timezone.utc)
    base = {
        "status": "sent",
        "opted_out": False,
        "next_follow_up_at": (now - timedelta(minutes=1)).isoformat(),
        "follow_up_count": 0,
        "last_inbound_message_id": None,
    }
    assert _due_follow_up(base, now)
    assert not _due_follow_up({**base, "last_inbound_message_id": "<reply@example.com>"}, now)
    assert not _due_follow_up({**base, "follow_up_count": 2}, now)
    assert not _due_follow_up({**base, "status": "replied"}, now)
    assert not _due_follow_up({**base, "next_follow_up_at": (now + timedelta(days=1)).isoformat()}, now)


def test_inbound_opt_out_and_reply_classification():
    assert _is_optout("Re: bemutatkozás", "Kérem, leiratkozom.")
    assert _is_optout("Unsubscribe", "Please remove me")
    assert not _is_optout("Re: bemutatkozás", "Köszönöm, érdekel a téma.")
