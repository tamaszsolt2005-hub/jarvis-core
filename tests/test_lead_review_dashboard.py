"""Focused tests for lead review display helpers and score fallback."""
from lead_review_dashboard import country_flag, extract_country


def test_extract_country_from_grounded_lead_note():
    lead = {"notes": "Leadkutatás; célpiac: Hungary; tényleges ország: Germany; iparág: SaaS"}
    assert extract_country(lead) == "Germany"
    assert country_flag(extract_country(lead)) == "🇩🇪"


def test_country_flag_is_safe_for_unknown_country():
    assert country_flag("Mars") == "🏳️"


def test_missing_country_is_explicitly_unknown():
    assert extract_country({"notes": "No country information"}) == "ismeretlen"

def test_existing_research_note_is_scored_without_research_intelligence_column():
    from intelligent_lead_scoring import score_researched_lead

    lead = {
        "notes": (
            "Leadkutatás; tényleges ország: Germany; "
            "AI üzleti illeszkedési becslés: 80/100; bizonyosság: high; "
            "alátámasztó jelek: ERP automation; CRM workflow; javasolt kutatási lépés: verify"
        )
    }
    assert score_researched_lead(lead)["priority_score"] is not None
