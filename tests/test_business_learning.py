from business_learning import build_business_learning


def test_learning_distinguishes_research_patterns_from_explicit_success():
    memories = [
        {"category": "decision", "content": "Új célpiac tesztelése"},
        {"category": "outcome", "content": "iparág=Manufacturing; módszer=Partneri ajánlás; döntés=Új célpiac tesztelése; eredmény=sikeres, 3 minősített érdeklődő"},
        {"category": "lesson", "content": "Ne bővítsünk piacot két bizonyíték alapján."},
    ]
    leads = [{
        "company_name": "Példa Kft.",
        "research_intelligence": (
            "Leadkutatás; tényleges ország: Hungary; iparág: Manufacturing; "
            "kutatási módszer: Google Search grounding; "
            "AI üzleti illeszkedési becslés: 82/100; bizonyosság: high"
        ),
    }]
    result = build_business_learning(memories, leads)
    assert result["observed_industries"][0]["name"] == "Manufacturing"
    assert result["explicitly_successful_methods"][0]["name"] == "Partneri ajánlás"
    assert result["explicitly_successful_decisions"][0]["name"] == "Új célpiac tesztelése"
    assert result["recorded_lessons"] == ["Ne bővítsünk piacot két bizonyíték alapján."]


def test_learning_does_not_treat_negative_outcome_as_success():
    result = build_business_learning([
        {"category": "outcome", "content": "módszer=Hideg megkeresés; eredmény=nem működött"},
    ], [])
    assert result["explicitly_successful_methods"] == []
