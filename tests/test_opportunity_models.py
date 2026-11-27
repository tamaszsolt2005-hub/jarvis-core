import pytest

from opportunity_models import CompanyPain, Evidence, MarketPattern, SaaSOpportunity


def test_company_pain_keeps_hypothesis_separate_from_evidence():
    item = CompanyPain.from_dict({
        "id": "pain-1", "company_id": "company-1",
        "statement": "Manual invoice reconciliation may be costly",
        "confidence": 0.62, "status": "hypothesis",
        "evidence": [{
            "source_url": "https://example.com/careers",
            "excerpt": "Hiring an accounts payable specialist",
            "observed_at": "2026-11-27T00:00:00Z",
            "evidence_type": "context",
        }],
    })
    assert item.status == "hypothesis"
    assert item.confidence == 0.62
    assert item.evidence[0].evidence_type == "context"


def test_rejects_untraceable_or_invalid_evidence():
    with pytest.raises(ValueError):
        Evidence.from_dict({"source_url": "javascript:alert(1)", "excerpt": "x", "observed_at": "today"})


def test_market_pattern_requires_company_problem_links():
    with pytest.raises(ValueError):
        MarketPattern.from_dict({"id": "pattern-1", "title": "Repeated workflow", "company_pain_ids": [], "confidence": 0.5})


def test_market_pattern_deduplicates_linked_company_pains():
    item = MarketPattern.from_dict({
        "id": "pattern-1", "title": "Repeated workflow",
        "company_pain_ids": ["pain-a", "pain-a", "pain-b"], "confidence": 0.7,
    })
    assert item.company_pain_ids == ("pain-a", "pain-b")


def test_saas_opportunity_requires_a_market_pattern():
    with pytest.raises(ValueError):
        SaaSOpportunity.from_dict({"id": "idea-1", "name": "Workflow SaaS", "summary": "A tool"})


from opportunity_models import calculate_opportunity_score


def test_opportunity_score_uses_documented_weights_and_penalizes_risk():
    score = calculate_opportunity_score({
        "problem_evidence": 80, "business_value": 70,
        "willingness_to_pay": 60, "feasibility": 90,
        "reusability": 80, "risk": 20,
    })
    assert score == 76.5


def test_opportunity_score_is_not_calculated_when_evidence_is_incomplete():
    assert calculate_opportunity_score({
        "problem_evidence": 100, "business_value": 100,
        "willingness_to_pay": None, "feasibility": 100,
        "reusability": 100, "risk": 0,
    }) is None


@pytest.mark.parametrize("value", [-0.1, 100.1, True, "90"])
def test_opportunity_score_rejects_invalid_dimensions(value):
    with pytest.raises(ValueError):
        calculate_opportunity_score({
            "problem_evidence": value, "business_value": 70,
            "willingness_to_pay": 60, "feasibility": 90,
            "reusability": 80, "risk": 20,
        })
