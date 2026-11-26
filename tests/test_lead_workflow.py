import pytest

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
            "notes": "[JARVIS_STAGE:outcome_measurement] Eredmény: pozitív: igazolt üzleti igény",
            "created_at": "2026-11-25T10:00:00Z",
            "completed_at": "2026-11-25T11:00:00Z",
        }],
    )
    assert final[0]["workflow_stage"] == "outcome_positive_review"

    unclassified = build_lead_workflow_recommendations(
        [lead],
        [{
            "lead_id": "lead-1", "status": "done",
            "notes": "[JARVIS_STAGE:outcome_measurement] Eredmény: további vizsgálat szükséges",
            "created_at": "2026-11-25T10:00:00Z",
            "completed_at": "2026-11-25T11:00:00Z",
        }],
    )
    assert unclassified[0]["workflow_stage"] == "outcome_classification_review"


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


def test_low_confidence_research_validation_does_not_unlock_commercial_stages():
    weak_lead = _lead(
        "lead-weak", "Bizonytalan Kft.", fit=91, confidence="low", evidence=""
    )
    plans = build_lead_workflow_recommendations(
        [weak_lead],
        [{
            "lead_id": "lead-weak", "status": "done",
            "notes": "[JARVIS_STAGE:research_validation]",
            "completed_at": "2026-11-25T11:00:00Z",
        }],
    )
    assert plans == []


def test_completed_research_validation_unlocks_business_stage_after_evidence_improves():
    lead = _lead(
        "lead-improved", "Pontos Kft.", fit=88, confidence="high",
        evidence="termékoldal; esettanulmány",
    )
    plans = build_lead_workflow_recommendations(
        [lead],
        [{
            "lead_id": "lead-improved", "status": "done",
            "notes": "[JARVIS_STAGE:research_validation]",
            "completed_at": "2026-11-25T11:00:00Z",
        }],
    )
    assert len(plans) == 1
    assert plans[0]["workflow_stage"] == "business_need_validation"


def test_recorded_positive_outcome_recommends_internal_opportunity_review():
    lead = _lead("lead-outcome", "Pozitív Kft.")
    tasks = [{
        "lead_id": "lead-outcome", "status": "done",
        "notes": "[JARVIS_STAGE:outcome_measurement] Eredmény: pozitív: 3 pilot érdeklődő, 1 validált igény",
        "completed_at": "2026-11-26T10:00:00Z",
    }]
    plan = build_lead_workflow_recommendations([lead], tasks)[0]
    assert plan["workflow_stage"] == "outcome_positive_review"
    assert "Pozitív üzleti eredmény" in plan["task_title"]
    assert "ne tekintsd automatikus megrendelésnek" in plan["rationale"]
    assert plan["outreach_allowed"] is False


def test_recorded_negative_outcome_recommends_internal_closeout_review():
    lead = _lead("lead-negative", "Negatív Kft.")
    tasks = [{
        "lead_id": "lead-negative", "status": "done",
        "notes": "[JARVIS_STAGE:outcome_measurement] Eredmény: negatív: nincs illeszkedés",
        "completed_at": "2026-11-26T10:00:00Z",
    }]
    plan = build_lead_workflow_recommendations([lead], tasks)[0]
    assert plan["workflow_stage"] == "outcome_negative_review"
    assert "lezárási javaslat" in plan["rationale"]


def test_no_response_outcome_recommends_requalification_without_outreach():
    lead = _lead("lead-silent", "Válasz nélkül Kft.")
    tasks = [{
        "lead_id": "lead-silent", "status": "done",
        "notes": "[JARVIS_STAGE:outcome_measurement] Eredmény: nincs válasz: nem érkezett reakció",
        "completed_at": "2026-11-26T10:00:00Z",
    }]
    plan = build_lead_workflow_recommendations([lead], tasks)[0]
    assert plan["workflow_stage"] == "outcome_no_response_review"
    assert "új kapcsolatfelvételt ne kezdeményezz" in plan["rationale"]


def test_unclassified_or_free_text_outcome_requires_manual_classification():
    lead = _lead("lead-unknown", "Bizonytalan Kft.")
    tasks = [{
        "lead_id": "lead-unknown", "status": "done",
        "notes": "[JARVIS_STAGE:outcome_measurement] Eredmény: talán jó lehetőség",
        "completed_at": "2026-11-26T10:00:00Z",
    }]
    plan = build_lead_workflow_recommendations([lead], tasks)[0]
    assert plan["workflow_stage"] == "outcome_classification_review"
    assert "emberi eredménybesorolást" in plan["rationale"]


def test_cancelled_outcome_recommendation_repeats_but_completed_one_stops():
    lead = _lead("lead-review", "Felülvizsgálat Kft.")
    measurement = {
        "lead_id": "lead-review", "status": "done",
        "notes": "[JARVIS_STAGE:outcome_measurement] Eredmény: pozitív: validált igény",
        "completed_at": "2026-11-25T10:00:00Z",
    }
    cancelled = {
        "lead_id": "lead-review", "status": "cancelled",
        "notes": "[JARVIS_STAGE:outcome_positive_review]",
        "completed_at": "2026-11-26T10:00:00Z",
    }
    assert build_lead_workflow_recommendations([lead], [measurement, cancelled])[0]["workflow_stage"] == "outcome_positive_review"
    completed = {**cancelled, "status": "done"}
    assert build_lead_workflow_recommendations([lead], [measurement, completed]) == []



def test_end_to_end_researched_lead_to_approved_atomic_task_and_audit_rpc(monkeypatch):
    """Connect grounded scoring and task planning to the one-use approval RPC contract."""
    import hashlib
    from types import SimpleNamespace
    import task_actions
    from lead_workflow import build_recommended_task_action

    lead_id = "123e4567-e89b-42d3-a456-426614174000"
    operation_id = "223e4567-e89b-42d3-a456-426614174001"
    approval_token = "one-use-approval-token-for-e2e-contract-test"
    principal = "legacy:323e4567-e89b-42d3-a456-426614174002"
    lead = {
        "id": lead_id,
        "company_name": "Minta Kft.",
        "source": "gemini_google_search_grounding:example.test",
        "notes": (
            "Leadkutatás; tényleges ország: Hungary; iparág: Manufacturing. "
            "AI üzleti illeszkedési becslés: 92/100; bizonyosság: high; "
            "megfigyelhető üzleti igény: manuális adminisztráció csökkentése; "
            "alátámasztó jelek: termékoldal; esettanulmány; "
            "javasolt kutatási lépés: folyamatellenőrzés"
        ),
    }
    linked_tasks = []
    action = build_recommended_task_action(lead, linked_tasks)
    assert action is not None
    assert action["lead_id"] == lead_id
    assert action["priority"] == "high"
    action["operation_id"] = operation_id

    # No database call is possible before explicit user confirmation and a
    # separately issued, principal-bound, one-use approval token.
    class AtomicTaskDatabase:
        def __init__(self):
            self.calls = []

        def rpc(self, name, params):
            self.calls.append((name, params))
            return SimpleNamespace(execute=lambda: SimpleNamespace(data={
                "ok": True,
                "status": "success",
                "message": "Feladat létrehozva és auditálva.",
                "lead_id": lead_id,
                "task_id": "423e4567-e89b-42d3-a456-426614174003",
            }))

    db = AtomicTaskDatabase()
    monkeypatch.setattr(
        task_actions, "get_enforced_user_supabase",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(PermissionError):
        task_actions.execute_task_action(
            db, action, approved=False,
            approval={"token": approval_token, "principal": principal},
        )
    assert db.calls == []

    result = task_actions.execute_task_action(
        db,
        action,
        approved=True,
        approval={"token": approval_token, "principal": principal},
    )

    assert result == "Feladat létrehozva és auditálva."
    assert len(db.calls) == 1
    rpc_name, rpc_params = db.calls[0]
    assert rpc_name == "execute_approved_task_action"
    assert rpc_params["p_token_hash"] == hashlib.sha256(
        approval_token.encode("utf-8")
    ).hexdigest()
    assert rpc_params["p_principal"] == principal
    assert rpc_params["p_operation_id"] == operation_id
    assert rpc_params["p_action"] == action
    assert rpc_params["p_action"]["lead_id"] == lead_id
    assert rpc_params["p_action"]["notes"].startswith("[JARVIS_STAGE:business_need_validation]")
    assert "nem kapcsolatfelvételi engedély" in rpc_params["p_action"]["notes"]
