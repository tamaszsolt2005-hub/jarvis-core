from market_pattern_discovery import build_cross_company_pattern_candidates


def _pain(pain_id, company_id, statement, category="operational_process", confidence=0.6):
    return {
        "id": pain_id,
        "lead_id": company_id,
        "statement": statement,
        "category": category,
        "confidence": confidence,
        "status": "hypothesis",
        "evidence": [{
            "source_url": f"https://{company_id}.example.com/report",
            "excerpt": statement,
            "evidence_type": "supporting",
        }],
    }


def test_repeated_source_backed_problem_creates_candidate_not_validated_pattern():
    candidates = build_cross_company_pattern_candidates([
        _pain("pain-1", "company-1", "Manual invoice reconciliation takes several days"),
        _pain("pain-2", "company-2", "Manual invoice reconciliation requires several days"),
    ])

    assert len(candidates) == 1
    assert candidates[0]["status"] == "candidate"
    assert len(candidates[0]["company_ids"]) == 2
    assert set(candidates[0]["company_pain_ids"]) == {"pain-1", "pain-2"}
    assert candidates[0]["fingerprint"]


def test_single_company_or_missing_source_does_not_create_market_pattern():
    one_company = [
        _pain("pain-1", "company-1", "Manual invoice reconciliation takes several days"),
        _pain("pain-2", "company-1", "Manual invoice reconciliation requires several days"),
    ]
    missing_source = _pain("pain-3", "company-2", "Manual invoice reconciliation requires several days")
    missing_source["evidence"] = []

    assert build_cross_company_pattern_candidates(one_company) == []
    assert build_cross_company_pattern_candidates([one_company[0], missing_source]) == []


def test_rejected_pain_and_different_categories_do_not_cluster():
    rejected = _pain("pain-1", "company-1", "Manual invoice reconciliation takes several days")
    rejected["status"] = "rejected"
    different_category = _pain(
        "pain-2", "company-2",
        "Manual invoice reconciliation requires several days",
        category="technology",
    )

    assert build_cross_company_pattern_candidates([rejected, different_category]) == []


def test_pattern_discovery_is_deterministic_for_input_order():
    pains = [
        _pain("pain-1", "company-1", "Manual invoice reconciliation takes several days"),
        _pain("pain-2", "company-2", "Manual invoice reconciliation requires several days"),
    ]

    assert build_cross_company_pattern_candidates(pains) == build_cross_company_pattern_candidates(list(reversed(pains)))
