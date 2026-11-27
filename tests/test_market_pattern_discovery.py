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



class _Response:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, db, table):
        self.db = db
        self.table_name = table
        self.filters = {}
        self.insert_rows = None
        self.limit_value = None

    def select(self, _columns):
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def order(self, _column, desc=False):
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def insert(self, rows):
        self.insert_rows = rows if isinstance(rows, list) else [rows]
        return self

    def execute(self):
        from uuid import uuid4

        rows = self.db.tables.setdefault(self.table_name, [])
        if self.insert_rows is not None:
            inserted = []
            for item in self.insert_rows:
                row = dict(item)
                if self.table_name in {"market_problem_patterns", "saas_opportunities"}:
                    row["id"] = str(uuid4())
                if self.table_name == "market_pattern_pains" and any(
                    existing.get("market_pattern_id") == row.get("market_pattern_id")
                    and existing.get("company_pain_id") == row.get("company_pain_id")
                    for existing in rows
                ):
                    continue
                rows.append(row)
                inserted.append(row)
            return _Response(inserted)
        selected = [row for row in rows if all(row.get(key) == value for key, value in self.filters.items())]
        return _Response(selected[:self.limit_value] if self.limit_value is not None else selected)


class _DB:
    def __init__(self, pains):
        self.tables = {"business_pain_hypotheses": list(pains)}

    def table(self, name):
        return _Query(self, name)


def test_discovery_persists_candidate_pattern_links_and_draft_saas_once():
    from market_pattern_discovery import discover_market_patterns

    db = _DB([
        _pain("pain-1", "company-1", "Manual invoice reconciliation takes several days"),
        _pain("pain-2", "company-2", "Manual invoice reconciliation requires several days"),
    ])

    first = discover_market_patterns(db)
    second = discover_market_patterns(db)

    assert first["patterns_created"] == 1
    assert first["evidence_links_created"] == 2
    assert first["saas_candidates_created"] == 1
    assert second["patterns_created"] == 0
    assert second["evidence_links_created"] == 0
    assert second["saas_candidates_created"] == 0
    assert db.tables["market_problem_patterns"][0]["status"] == "candidate"
    assert db.tables["saas_opportunities"][0]["status"] == "draft"
    assert len(db.tables["market_pattern_pains"]) == 2
