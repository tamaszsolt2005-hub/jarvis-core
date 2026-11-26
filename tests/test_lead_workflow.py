from lead_workflow import build_lead_workflow_recommendations


def _lead(lead_id, company, fit=88, confidence="high", evidence="termékoldal; esettanulmány"):
    return {
        "id": lead_id,
        "company_name": company,
        "research_intelligence": (
            "Leadkutatás; tényleges ország: Hungary; iparág: Manufacturing. "
            f"AI üzleti illeszkedési becslés: {fit}/100; bizonyosság: {confidence}; "
            f"megfigyelhető üzleti igény: manuális adminisztráció csökkentése; "
            f"alátámasztó jelek: {evidence}; javasolt kutatási lépés: folyamatellenőrzés"
        ),
    }


def test_recommendation_connects_research_score_strategy_and_next_internal_task():
    plans = build_lead_workflow_recommendations(
        [_lead("lead-1", "Minta Kft.")],
        [],
    )

    assert len(plans) == 1
    plan = plans[0]
    assert plan["lead_id"] == "lead-1"
    assert plan["company_name"] == "Minta Kft."
    assert plan["task_title"].endswith("Minta Kft.")
    assert plan["task_priority"] == "high"
    assert plan["business_fit_score"] == 88
    assert plan["research_confidence"] == "high"
    assert plan["industry"] == "Manufacturing"
    assert plan["business_need"] == "manuális adminisztráció csökkentése"
    assert plan["evidence_count"] == 2
    assert plan["outreach_allowed"] is False
    assert "nem kapcsolatfelvételi engedély" in plan["notes"]


def test_low_confidence_or_thin_evidence_only_proposes_research_validation():
    plans = build_lead_workflow_recommendations(
        [
            _lead("lead-low", "Gyenge Kft.", fit=91, confidence="low", evidence=""),
            _lead("lead-thin", "Hiányos Kft.", fit=74, confidence="high", evidence="egy forrás"),
        ],
        [],
    )

    by_id = {item["lead_id"]: item for item in plans}
    assert by_id["lead-low"]["task_priority"] == "normal"
    assert "Kutatási bizonyítékok kiegészítése" in by_id["lead-low"]["task_title"]
    assert "Kutatási bizonyítékok kiegészítése" in by_id["lead-thin"]["task_title"]


def test_existing_linked_task_suppresses_duplicate_recommendation():
    plans = build_lead_workflow_recommendations(
        [_lead("lead-1", "Minta Kft.")],
        [{"lead_id": "lead-1", "status": "open", "title": "Már van teendő"}],
    )
    assert plans == []


def test_unstructured_or_unidentified_leads_are_not_actioned():
    plans = build_lead_workflow_recommendations(
        [
            {"id": "lead-1", "company_name": "Kézi rekord", "research_intelligence": ""},
            _lead("", "Azonosító nélküli Kft."),
        ],
        [],
    )
    assert plans == []


def test_recommendations_are_ranked_and_bounded():
    plans = build_lead_workflow_recommendations(
        [
            _lead("low", "Alacsony Kft.", fit=50, confidence="medium"),
            _lead("high", "Magas Kft.", fit=95, confidence="high"),
        ],
        [],
        limit=1,
    )
    assert [item["lead_id"] for item in plans] == ["high"]
