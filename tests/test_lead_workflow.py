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


def test_recommended_task_command_requires_a_valid_lead_uuid():
    from lead_workflow import parse_recommended_task_command

    lead_id = "123e4567-e89b-42d3-a456-426614174000"
    assert parse_recommended_task_command(
        f"Hozz létre javasolt feladat: {lead_id}"
    ) == {"lead_id": lead_id}
    assert parse_recommended_task_command(
        f"hozz letre javasolt feladat: {lead_id.upper()}"
    ) == {"lead_id": lead_id}
    assert "error" in parse_recommended_task_command(
        "Hozz létre javasolt feladat: nem-uuid"
    )
    assert parse_recommended_task_command("Szia JARVIS") is None


def test_recommended_task_action_is_grounded_linked_and_not_outreach():
    from lead_workflow import build_recommended_task_action

    lead_id = "123e4567-e89b-42d3-a456-426614174000"
    action = build_recommended_task_action(
        {
            "id": lead_id,
            "company_name": "Minta Kft.",
            "source": "gemini_google_search_grounding:example.test",
            "notes": (
                "Leadkutatás; tényleges ország: Hungary; iparág: Manufacturing. "
                "AI üzleti illeszkedési becslés: 88/100; bizonyosság: high; "
                "megfigyelhető üzleti igény: manuális adminisztráció csökkentése; "
                "alátámasztó jelek: termékoldal; esettanulmány; "
                "javasolt kutatási lépés: folyamatellenőrzés"
            ),
        },
        [],
    )

    assert action is not None
    assert action["type"] == "create"
    assert action["lead_id"] == lead_id
    assert action["priority"] == "high"
    assert "Minta Kft." in action["title"]
    assert "nem kapcsolatfelvételi engedély" in action["notes"]


def test_recommended_task_action_rejects_unverified_and_already_linked_leads():
    from lead_workflow import build_recommended_task_action

    lead_id = "123e4567-e89b-42d3-a456-426614174000"
    lead = {
        "id": lead_id,
        "company_name": "Minta Kft.",
        "source": "gemini_google_search_grounding:example.test",
        "notes": (
            "Leadkutatás; tényleges ország: Hungary; iparág: Manufacturing. "
            "AI üzleti illeszkedési becslés: 88/100; bizonyosság: high; "
            "megfigyelhető üzleti igény: adminisztráció; "
            "alátámasztó jelek: termékoldal; esettanulmány"
        ),
    }
    assert build_recommended_task_action(
        {**lead, "source": "manual"}, []
    ) is None
    assert build_recommended_task_action(
        lead, [{"lead_id": lead_id, "status": "open"}]
    ) is None


def test_completed_or_cancelled_linked_task_does_not_block_next_recommendation():
    lead = _lead("lead-1", "Minta Kft.")
    plans = build_lead_workflow_recommendations(
        [lead],
        [
            {"lead_id": "lead-1", "status": "done", "title": "Korábbi ellenőrzés"},
            {"lead_id": "lead-1", "status": "cancelled", "title": "Visszavont feladat"},
        ],
    )
    assert len(plans) == 1
    assert plans[0]["lead_id"] == "lead-1"


def test_recommended_task_action_allows_next_step_after_completed_task():
    from lead_workflow import build_recommended_task_action

    lead_id = "123e4567-e89b-42d3-a456-426614174000"
    lead = {
        "id": lead_id,
        "company_name": "Minta Kft.",
        "source": "gemini_google_search_grounding:example.test",
        "notes": (
            "Leadkutatás; tényleges ország: Hungary; iparág: Manufacturing. "
            "AI üzleti illeszkedési becslés: 88/100; bizonyosság: high; "
            "megfigyelhető üzleti igény: adminisztráció; "
            "alátámasztó jelek: termékoldal; esettanulmány"
        ),
    }
    action = build_recommended_task_action(
        lead, [{"lead_id": lead_id, "status": "done", "title": "Elvégzett ellenőrzés"}]
    )
    assert action is not None
    assert action["lead_id"] == lead_id


def test_workflow_advances_after_each_completed_stage_and_stops_at_outcome():
    lead = _lead("lead-1", "Minta Kft.")
    first = build_lead_workflow_recommendations([lead], [])[0]
    assert first["workflow_stage"] == "business_need_validation"
    assert "[JARVIS_STAGE:business_need_validation]" in first["notes"]

    second = build_lead_workflow_recommendations(
        [lead],
        [{
            "lead_id": "lead-1", "status": "done",
            "notes": "[JARVIS_STAGE:business_need_validation]",
            "created_at": "2026-11-25T10:00:00Z",
            "completed_at": "2026-11-25T11:00:00Z",
        }],
    )[0]
    assert second["workflow_stage"] == "offer_preparation"

    final = build_lead_workflow_recommendations(
        [lead],
        [{
            "lead_id": "lead-1", "status": "done",
            "notes": "[JARVIS_STAGE:outcome_measurement]",
            "created_at": "2026-11-25T10:00:00Z",
            "completed_at": "2026-11-25T11:00:00Z",
        }],
    )
    assert final == []


def test_cancelled_workflow_stage_is_recommended_again():
    lead = _lead("lead-1", "Minta Kft.")
    plans = build_lead_workflow_recommendations(
        [lead],
        [{
            "lead_id": "lead-1", "status": "cancelled",
            "notes": "[JARVIS_STAGE:offer_review]",
            "created_at": "2026-11-25T10:00:00Z",
        }],
    )
    assert plans[0]["workflow_stage"] == "offer_review"


def test_open_workflow_task_blocks_stage_progression():
    lead = _lead("lead-1", "Minta Kft.")
    plans = build_lead_workflow_recommendations(
        [lead],
        [{
            "lead_id": "lead-1", "status": "open",
            "notes": "[JARVIS_STAGE:business_need_validation]",
        }],
    )
    assert plans == []


def test_followup_stage_is_review_only_and_outcome_stage_requests_measurement():
    lead = _lead("lead-1", "Minta Kft.")
    followup = build_lead_workflow_recommendations(
        [lead],
        [{
            "lead_id": "lead-1", "status": "done",
            "notes": "[JARVIS_STAGE:offer_review]",
            "completed_at": "2026-11-25T11:00:00Z",
        }],
    )[0]
    assert followup["workflow_stage"] == "follow_up_review"
    assert "Ne küldj üzenetet" in followup["notes"]
    outcome = build_lead_workflow_recommendations(
        [lead],
        [{
            "lead_id": "lead-1", "status": "done",
            "notes": "[JARVIS_STAGE:follow_up_review]",
            "completed_at": "2026-11-25T11:00:00Z",
        }],
    )[0]
    assert outcome["workflow_stage"] == "outcome_measurement"
    assert "mérhető üzleti eredményt" in outcome["notes"]
