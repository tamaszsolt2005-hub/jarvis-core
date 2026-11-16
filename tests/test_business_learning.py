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


def test_learning_tracks_explicit_negative_and_unclassified_outcomes():
    result = build_business_learning([
        {"category": "outcome", "content": "iparág=Gyártás; módszer=Hideg hívás; eredmény=nem volt sikeres, 0 érdeklődő"},
        {"category": "outcome", "content": "iparág=IT; módszer=Partneri ajánlás; eredmény=sikeres, 4 minősített érdeklődő"},
        {"category": "outcome", "content": "iparág=Építőipar; módszer=Konferencia; eredmény=2 találkozó"},
    ], [])
    assert result["outcome_polarity_counts"] == {"positive": 1, "negative": 1, "unclassified": 1}
    assert result["explicitly_unsuccessful_methods"][0]["name"] == "Hideg hívás"
    assert result["explicitly_successful_methods"][0]["name"] == "Partneri ajánlás"


def test_learning_links_only_explicitly_tagged_outcomes_to_decisions():
    result = build_business_learning([
        {"category": "decision", "content": "Német piac tesztelése"},
        {"category": "outcome", "content": "döntés=Német piac tesztelése; iparág=Gyártás; módszer=Partneri ajánlás; eredmény=sikeres, 3 érdeklődő"},
        {"category": "outcome", "content": "döntés=Másik kampány; iparág=Gyártás; módszer=Partneri ajánlás; eredmény=nem volt sikeres"},
        {"category": "outcome", "content": "iparág=Gyártás; módszer=Partneri ajánlás; eredmény=sikeres, 2 érdeklődő"},
    ], [])
    link = result["decision_outcome_links"][0]
    assert link["decision"] == "Német piac tesztelése"
    assert link["linked_outcome_count"] == 1
    assert link["positive"] == 1
    assert link["negative"] == 0


def test_repeated_outcome_patterns_require_multiple_explicit_records():
    result = build_business_learning([
        {"category": "outcome", "content": "iparág=Gyártás; módszer=Partneri ajánlás; eredmény=sikeres"},
        {"category": "outcome", "content": "iparág=Gyártás; módszer=Partneri ajánlás; eredmény=nem volt sikeres"},
        {"category": "outcome", "content": "iparág=IT; módszer=Hideg hívás; eredmény=3 találkozó"},
    ], [])
    pattern = result["repeated_outcome_patterns"][0]
    assert pattern["industry"] == "Gyártás"
    assert pattern["record_count"] == 2
    assert pattern["positive"] == 1
    assert pattern["negative"] == 1
