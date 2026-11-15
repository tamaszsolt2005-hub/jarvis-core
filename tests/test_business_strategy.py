from business_strategy import build_market_intelligence


def _lead(company, country, industry, score, confidence="high"):
    return {
        "company_name": company,
        "research_intelligence": (
            f"Leadkutatás; célpiac: Hungary; tényleges ország: {country}; iparág: {industry}. "
            f"Cégprofil: Nyilvános céges profil. Lehetséges illeszkedés: automatizálási lehetőség. "
            f"AI üzleti illeszkedési becslés: {score}/100; bizonyosság: {confidence}; "
            "megfigyelhető üzleti igény: ismétlődő adminisztráció; "
            "alátámasztó jelek: nyilvános szolgáltatásleírás; javasolt kutatási lépés: további kutatás "
            "Forrás: https://example.com/about"
        ),
    }


def test_market_intelligence_aggregates_industries_and_countries():
    leads = [
        _lead("A", "Hungary", "Manufacturing", 80),
        _lead("B", "Hungary", "Manufacturing", 60, "medium"),
        _lead("C", "Germany", "Software", 90),
    ]

    result = build_market_intelligence(leads)

    assert result["research_record_count"] == 3
    assert result["overall_average_business_fit"] == 76.7
    assert result["industry_patterns"][0]["name"] == "Software"
    assert result["industry_patterns"][1]["name"] == "Manufacturing"
    manufacturing = result["industry_patterns"][1]
    assert manufacturing["sample_size"] == 2
    assert manufacturing["average_fit_score"] == 70
    assert manufacturing["high_confidence_count"] == 1
    assert result["best_observed_industries_with_multiple_examples"][0]["name"] == "Manufacturing"
    assert len(result["interpretation_limits"]) >= 4


def test_market_intelligence_ignores_manual_notes_and_unscored_research():
    leads = [
        {"company_name": "Manual", "notes": "Leadkutatás; tényleges ország: Hungary; iparág: Software."},
        {"company_name": "Unscored", "research_intelligence": "Leadkutatás; tényleges ország: Hungary; iparág: Software."},
        _lead("Valid", "Hungary", "Software", 75, "low"),
    ]

    result = build_market_intelligence(leads)

    assert result["research_record_count"] == 1
    assert result["industry_patterns"][0]["sample_size"] == 1
    assert result["best_observed_industries_with_multiple_examples"] == []


def test_market_intelligence_handles_no_history():
    result = build_market_intelligence([])

    assert result["research_record_count"] == 0
    assert result["industry_patterns"] == []
    assert "Még nincs elegendő" in result["message"]
