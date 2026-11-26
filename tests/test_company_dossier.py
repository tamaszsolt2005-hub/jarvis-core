from company_dossier import build_company_dossier, render_company_dossier


def test_company_dossier_keeps_only_grounded_public_business_facts():
    grounded = {"example.com", "industry.test"}
    item = {
        "company_facts": [
            {
                "category": "products_services",
                "fact": "The company manufactures industrial sensors.",
                "source_url": "https://www.example.com/products",
            },
            {
                "category": "growth_signal",
                "fact": "Opened a new regional facility.",
                "source_url": "https://industry.test/news",
            },
            {
                "category": "public_news",
                "fact": "Unsupported claim must be dropped.",
                "source_url": "https://unverified.test/article",
            },
            {
                "category": "private_personal_data",
                "fact": "Not an allowed business fact.",
                "source_url": "https://example.com/about",
            },
        ],
        "decision_maker": {
            "name": "Alex Example",
            "role": "Chief Operating Officer",
            "professional_background": "Leads operations and manufacturing strategy.",
            "source_url": "https://example.com/leadership",
            "email": "private@example.com",
            "phone": "+1-555-0100",
        },
    }

    dossier = build_company_dossier(item, grounded)

    assert len(dossier["facts"]) == 2
    assert dossier["facts"][0]["category"] == "products_services"
    assert dossier["facts"][1]["category"] == "growth_signal"
    assert dossier["decision_maker"] == {
        "name": "Alex Example",
        "role": "Chief Operating Officer",
        "professional_background": "Leads operations and manufacturing strategy.",
        "source_url": "https://example.com/leadership",
    }
    rendered = render_company_dossier(dossier)
    assert "Alex Example" in rendered
    assert "manufactures industrial sensors" in rendered
    assert "unverified.test" not in rendered
    assert "private@example.com" not in rendered
    assert "+1-555-0100" not in rendered


def test_company_dossier_rejects_untrusted_urls_and_unknown_categories():
    dossier = build_company_dossier(
        {
            "company_facts": [
                {"category": "business_model", "fact": "Fact", "source_url": "file:///etc/passwd"},
                {"category": "unknown", "fact": "Fact", "source_url": "https://example.com"},
                {"category": "markets", "fact": "Fact", "source_url": "https://localhost/private"},
            ],
            "decision_maker": {
                "name": "Unverified Person",
                "role": "CEO",
                "professional_background": "Unknown",
                "source_url": "https://not-grounded.test/profile",
            },
        },
        {"example.com"},
    )
    assert dossier == {"facts": [], "decision_maker": {}}
    assert render_company_dossier(dossier) == ""


def test_company_dossier_rendering_is_bounded():
    dossier = {
        "facts": [{
            "category": "operational_process",
            "fact": "A" * 260,
            "source_url": "https://example.com/" + "x" * 100,
        }],
        "decision_maker": {
            "name": "A" * 100,
            "role": "B" * 100,
            "professional_background": "C" * 260,
            "source_url": "https://example.com/leadership",
        },
    }
    assert len(render_company_dossier(dossier, max_chars=180)) <= 180
