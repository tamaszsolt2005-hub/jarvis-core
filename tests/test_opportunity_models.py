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



def _score_evidence_fixture():
    source = {
        "source_url": "https://example.com/process",
        "excerpt": "The company is hiring an operations coordinator to reconcile orders.",
        "observed_at": "2026-11-27T00:00:00Z",
        "evidence_type": "supporting",
    }
    pain = {
        "id": "pain-1", "company_id": "company-1",
        "statement": "Order reconciliation may be manual",
        "confidence": 0.7, "status": "hypothesis",
        "evidence": [source],
    }
    references = {
        dimension: [{**source, "pain_hypothesis_id": "pain-1"}]
        for dimension in (
            "problem_evidence", "business_value", "willingness_to_pay",
            "feasibility", "reusability", "risk",
        )
    }
    return pain, references


def test_score_evidence_must_match_existing_company_pain_sources():
    from opportunity_models import validate_opportunity_score_evidence

    pain, references = _score_evidence_fixture()
    validated = validate_opportunity_score_evidence(references, [pain])
    assert len(validated) == 6
    assert validated["problem_evidence"][0]["pain_hypothesis_id"] == "pain-1"


def test_score_evidence_rejects_missing_dimension_or_unlinked_source():
    from opportunity_models import validate_opportunity_score_evidence

    pain, references = _score_evidence_fixture()
    incomplete = dict(references)
    incomplete["risk"] = []
    with pytest.raises(ValueError):
        validate_opportunity_score_evidence(incomplete, [pain])

    unlinked = dict(references)
    unlinked["business_value"] = [{
        **references["business_value"][0],
        "excerpt": "This excerpt is not present in the stored company dossier.",
    }]
    with pytest.raises(ValueError):
        validate_opportunity_score_evidence(unlinked, [pain])


def test_company_pain_accepts_database_lead_id_and_optional_evidence_timestamp():
    item = CompanyPain.from_dict({
        "id": "pain-db", "lead_id": "lead-db",
        "statement": "A source-backed operational pain",
        "confidence": 0.6, "status": "hypothesis",
        "created_at": "2026-11-27T10:00:00Z",
        "evidence": [{
            "source_url": "https://example.com/report",
            "excerpt": "A documented operational fact",
        }],
    })
    assert item.company_id == "lead-db"
    assert item.evidence[0].observed_at == "2026-11-27T10:00:00Z"


def _evaluator_fixture():
    pains = []
    for index in (1, 2):
        pains.append({
            "id": f"pain-{index}", "lead_id": f"lead-{index}",
            "statement": f"Repeated workflow issue at company {index}",
            "confidence": 0.75, "status": "supported",
            "created_at": "2026-11-27T10:00:00Z",
            "evidence": [{
                "source_url": f"https://company{index}.example/process",
                "excerpt": f"Company {index} documents manual reconciliation work.",
            }],
        })
    pattern = {
        "id": "pattern-validated", "title": "Manual reconciliation",
        "company_pain_ids": ["pain-1", "pain-2"],
        "confidence": 0.85, "status": "validated",
    }
    candidate = {
        "id": "candidate-1", "market_pattern_id": "pattern-validated",
        "name": "Reconciliation SaaS", "summary": "Automates repeatable reconciliation.",
        "status": "shortlisted",
    }
    evidence = {}
    for dimension in (
        "problem_evidence", "business_value", "willingness_to_pay",
        "feasibility", "reusability", "risk",
    ):
        evidence[dimension] = [{
            "pain_hypothesis_id": pain["id"],
            "source_url": pain["evidence"][0]["source_url"],
            "excerpt": pain["evidence"][0]["excerpt"],
            "observed_at": pain["created_at"],
            "evidence_type": "supporting",
        } for pain in pains]
    response = {
        "status": "scored",
        "scores": {
            "problem_evidence": 80, "business_value": 70,
            "willingness_to_pay": 60, "feasibility": 90,
            "reusability": 80, "risk": 20,
        },
        "assessment_confidence": 0.82,
        "score_rationale": {
            key: f"Source-grounded rationale for {key}"
            for key in (
                "problem_evidence", "business_value", "willingness_to_pay",
                "feasibility", "reusability", "risk",
            )
        },
        "score_evidence": evidence,
    }
    return pattern, candidate, pains, response


def test_evaluator_returns_non_persisted_preview_from_two_companies():
    from opportunity_evaluator import evaluate_opportunity_candidate

    pattern, candidate, pains, response = _evaluator_fixture()
    seen = []
    result = evaluate_opportunity_candidate(
        market_pattern=pattern, candidate=candidate, company_pains=pains,
        provider=lambda prompt: (seen.append(prompt) or response),
    )
    assert result["status"] == "scored"
    assert result["weighted_score"] == 76.5
    assert result["requires_human_approval"] is True
    assert result["persisted"] is False
    assert "untrusted data" in seen[0]


def test_evaluator_fails_closed_when_provider_cannot_score_all_dimensions():
    from opportunity_evaluator import evaluate_opportunity_candidate

    pattern, candidate, pains, _ = _evaluator_fixture()
    result = evaluate_opportunity_candidate(
        market_pattern=pattern, candidate=candidate, company_pains=pains,
        provider=lambda _prompt: {
            "status": "insufficient_evidence",
            "reason": "No reliable willingness-to-pay signal.",
            "missing_dimensions": ["willingness_to_pay"],
        },
    )
    assert result["weighted_score"] is None
    assert "scores" not in result


def test_evaluator_rejects_a_pattern_without_two_distinct_companies():
    from opportunity_evaluator import evaluate_opportunity_candidate

    pattern, candidate, pains, response = _evaluator_fixture()
    pains[1] = {**pains[1], "lead_id": pains[0]["lead_id"]}
    with pytest.raises(ValueError):
        evaluate_opportunity_candidate(
            market_pattern=pattern, candidate=candidate, company_pains=pains,
            provider=lambda _prompt: response,
        )


def test_evaluator_rejects_provider_evidence_not_matching_a_stored_source():
    from copy import deepcopy
    from opportunity_evaluator import evaluate_opportunity_candidate

    pattern, candidate, pains, response = _evaluator_fixture()
    forged = deepcopy(response)
    forged["score_evidence"]["business_value"][0]["excerpt"] = "Invented evidence"
    with pytest.raises(ValueError):
        evaluate_opportunity_candidate(
            market_pattern=pattern, candidate=candidate, company_pains=pains,
            provider=lambda _prompt: forged,
        )

@pytest.mark.parametrize("status", ["draft", "under_review"])
def test_evaluator_requires_shortlisted_candidate_before_calling_provider(status):
    from opportunity_evaluator import OpportunityEvaluationError, evaluate_opportunity_candidate

    pattern, candidate, pains, _response = _evaluator_fixture()
    candidate["status"] = status
    called = []
    with pytest.raises(OpportunityEvaluationError, match="must_be_shortlisted"):
        evaluate_opportunity_candidate(
            market_pattern=pattern, candidate=candidate, company_pains=pains,
            provider=lambda _prompt: called.append(True) or {},
        )
    assert called == []


def test_evaluator_refuses_rejected_candidate_before_calling_provider():
    from opportunity_evaluator import OpportunityEvaluationError, evaluate_opportunity_candidate

    pattern, candidate, pains, _response = _evaluator_fixture()
    candidate["status"] = "rejected"
    called = []
    with pytest.raises(OpportunityEvaluationError, match="rejected_opportunity"):
        evaluate_opportunity_candidate(
            market_pattern=pattern, candidate=candidate, company_pains=pains,
            provider=lambda _prompt: called.append(True) or {},
        )
    assert called == []
