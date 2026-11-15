from intelligent_lead_scoring import score_researched_lead, rank_researched_leads


def _lead(name, score, confidence, evidence="nyilvános termékoldal; esettanulmány"):
    return {
        "company_name": name,
        "research_intelligence": (
            "Leadkutatás; tényleges ország: Hungary; iparág: Manufacturing. "
            f"AI üzleti illeszkedési becslés: {score}/100; bizonyosság: {confidence}; "
            f"alátámasztó jelek: {evidence}; javasolt kutatási lépés: további ellenőrzés"
        ),
    }


def test_high_confidence_evidence_scores_above_weak_research():
    strong = score_researched_lead(_lead("A", 85, "high"))
    weak = score_researched_lead(_lead("B", 85, "low", ""))
    assert strong["priority_score"] > weak["priority_score"]
    assert strong["priority_score"] <= 100
    assert "nem vásárlási szándék" in strong["interpretation"]


def test_manual_notes_are_not_scored():
    result = score_researched_lead({"notes": "Leadkutatás; AI üzleti illeszkedési becslés: 99/100"})
    assert result["scored"] is False


def test_ranking_is_descending():
    ranked = rank_researched_leads([_lead("Low", 40, "medium"), _lead("High", 90, "high")])
    assert [x["company_name"] for x in ranked] == ["High", "Low"]
