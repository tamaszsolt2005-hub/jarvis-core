from company_dossier import build_company_dossier, render_company_dossier, stamp_company_dossier


def test_company_dossier_keeps_only_grounded_public_business_facts():
    grounded = {
        "https://www.example.com/products",
        "https://industry.test/news",
        "https://example.com/leadership",
    }
    item = {
        "company_facts": [
            {
                "category": "products_services",
                "fact": "The company manufactures industrial sensors.",
                "source_url": "https://www.example.com/products",
            },
            {
                "category": "growth_signal",
                "fact": "Opened a new regional facility.",
                "source_url": "https://industry.test/news",
            },
            {
                "category": "public_news",
                "fact": "Unsupported claim must be dropped.",
                "source_url": "https://unverified.test/article",
            },
            {
                "category": "private_personal_data",
                "fact": "Not an allowed business fact.",
                "source_url": "https://example.com/about",
            },
            {
                "category": "public_news",
                "fact": "Same-domain but not grounded at this exact URL.",
                "source_url": "https://www.example.com/unverified-page",
            },
        ],
        "decision_maker": {
            "name": "Alex Example",
            "role": "Chief Operating Officer",
            "professional_background": "Leads operations and manufacturing strategy.",
            "source_url": "https://example.com/leadership",
            "email": "private@example.com",
            "phone": "+1-555-0100",
        },
    }

    dossier = build_company_dossier(item, grounded)

    assert len(dossier["facts"]) == 2
    assert dossier["facts"][0]["category"] == "products_services"
    assert dossier["facts"][1]["category"] == "growth_signal"
    assert dossier["decision_maker"] == {
        "name": "Alex Example",
        "role": "Chief Operating Officer",
        "professional_background": "Leads operations and manufacturing strategy.",
        "source_url": "https://example.com/leadership",
    }
    rendered = render_company_dossier(dossier)
    assert "Alex Example" in rendered
    assert "manufactures industrial sensors" in rendered
    assert "unverified.test" not in rendered
    assert "private@example.com" not in rendered
    assert "+1-555-0100" not in rendered


def test_company_dossier_rejects_untrusted_urls_and_unknown_categories():
    dossier = build_company_dossier(
        {
            "company_facts": [
                {"category": "business_model", "fact": "Fact", "source_url": "file:///etc/passwd"},
                {"category": "unknown", "fact": "Fact", "source_url": "https://example.com"},
                {"category": "markets", "fact": "Fact", "source_url": "https://localhost/private"},
                {"category": "markets", "fact": "Fact", "source_url": "http://127.0.0.1/private"},
            ],
            "decision_maker": {
                "name": "Unverified Person",
                "role": "CEO",
                "professional_background": "Unknown",
                "source_url": "https://not-grounded.test/profile",
            },
        },
        {"https://example.com/about"},
    )
    assert dossier == {"facts": [], "decision_maker": {}}
    assert render_company_dossier(dossier) == ""


def test_company_dossier_rendering_is_bounded():
    dossier = {
        "facts": [{
            "category": "operational_process",
            "fact": "A" * 260,
            "source_url": "https://example.com/" + "x" * 100,
        }],
        "decision_maker": {
            "name": "A" * 100,
            "role": "B" * 100,
            "professional_background": "C" * 260,
            "source_url": "https://example.com/leadership",
        },
    }
    assert len(render_company_dossier(dossier, max_chars=180)) <= 180



def test_company_dossier_snapshot_metadata_is_versioned_and_content_addressed():
    dossier = build_company_dossier(
        {"company_facts": [{
            "category": "business_model",
            "fact": "Builds industrial software.",
            "source_url": "https://example.com/about",
        }]},
        {"https://example.com/about"},
    )
    first = stamp_company_dossier(dossier)
    second = stamp_company_dossier(dossier)

    assert first["schema_version"] == 1
    assert first["snapshot_id"] != second["snapshot_id"]
    assert first["researched_at"]
    assert len(first["content_sha256"]) == 64
    assert first["content_sha256"] == second["content_sha256"]
    assert first["facts"] == dossier["facts"]

from datetime import datetime, timedelta, timezone
import pytest
from company_dossier import is_company_dossier_stale


def test_company_dossier_freshness_policy_uses_configurable_age():
    now = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)
    fresh = {"researched_at": (now - timedelta(days=29)).isoformat()}
    expired = {"researched_at": (now - timedelta(days=30)).isoformat()}
    assert is_company_dossier_stale(fresh, now=now) is False
    assert is_company_dossier_stale(expired, now=now) is True
    assert is_company_dossier_stale(fresh, max_age_days=7, now=now) is True


@pytest.mark.parametrize("dossier", [
    {},
    {"researched_at": ""},
    {"researched_at": "not-a-date"},
    {"researched_at": "2026-11-25T12:00:00"},
])
def test_company_dossier_freshness_fails_closed_for_invalid_timestamps(dossier):
    now = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)
    assert is_company_dossier_stale(dossier, now=now) is True


def test_company_dossier_future_timestamp_is_stale():
    now = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)
    future = {"researched_at": (now + timedelta(minutes=1)).isoformat()}
    assert is_company_dossier_stale(future, now=now) is True


@pytest.mark.parametrize("age", [-1, True, 1.5, "30"])
def test_company_dossier_freshness_rejects_invalid_age_configuration(age):
    with pytest.raises(ValueError):
        is_company_dossier_stale({"researched_at": "2026-11-01T00:00:00+00:00"}, max_age_days=age)
