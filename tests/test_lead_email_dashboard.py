"""Tests for safe lead-linked email draft helpers; no delivery is invoked."""
from lead_email_dashboard import _email, _safe_public_source, _source_facts, _split_draft


def test_split_draft_extracts_subject_and_body():
    subject, body = _split_draft("Tárgy: Rövid egyeztetés\n\nTisztelt Partner!\nEgy kérdésem lenne.")
    assert subject == "Rövid egyeztetés"
    assert body.startswith("Tisztelt Partner!")


def test_split_draft_has_safe_fallback_subject():
    subject, body = _split_draft("Tisztelt Partner!\nSzeretnék egyeztetni.")
    assert subject
    assert "Tisztelt Partner" in body


def test_email_validator_rejects_multiple_or_malformed_recipients():
    assert _email("ceo@example.com")
    assert not _email("ceo@example.com,other@example.com")
    assert not _email("not-an-email")


def test_public_source_rejects_local_and_private_urls():
    assert _safe_public_source("https://example.com/leadership")
    assert _safe_public_source("http://127.0.0.1/admin") is None
    assert _safe_public_source("http://localhost/about") is None
    assert _safe_public_source("file:///etc/passwd") is None



def test_source_facts_only_returns_facts_with_safe_public_sources():
    snapshot = {
        "dossier": {
            "facts": [
                {"category": "Vezetőség", "fact": "Nyilvános ügyvezetői adat", "source_url": "https://example.com/team"},
                {"category": "Belső", "fact": "Nem biztonságos forrás", "source_url": "http://127.0.0.1/private"},
                {"category": "Hiányos", "fact": "Forrás nélküli állítás"},
            ]
        }
    }
    facts = _source_facts(snapshot)
    assert len(facts) == 1
    assert facts[0]["category"] == "Vezetőség"
    assert facts[0]["source_url"] == "https://example.com/team"
