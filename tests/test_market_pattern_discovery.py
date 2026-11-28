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



def test_private_or_invalid_source_urls_are_not_discovery_evidence():
    private = _pain("pain-private", "company-2", "Manual invoice reconciliation requires several days")
    private["evidence"][0]["source_url"] = "http://127.0.0.1/private"
    valid = _pain("pain-public", "company-1", "Manual invoice reconciliation takes several days")

    assert build_cross_company_pattern_candidates([valid, private]) == []



def test_company_pain_persistence_is_snapshot_scoped_and_idempotent():
    from market_pattern_discovery import persist_company_pain_hypotheses

    db = _DB([])
    hypotheses = [{
        "statement": "Manual invoice reconciliation may create delays",
        "category": "finance",
        "confidence": 0.62,
        "evidence": [{
            "source_url": "https://company-1.example.com/report",
            "excerpt": "Invoices are reconciled manually over several days.",
            "evidence_type": "supporting",
        }],
    }]

    first = persist_company_pain_hypotheses(
        db, lead_id="company-1", snapshot_id="snapshot-1", hypotheses=hypotheses
    )
    second = persist_company_pain_hypotheses(
        db, lead_id="company-1", snapshot_id="snapshot-1", hypotheses=hypotheses
    )

    assert first == 1
    assert second == 0
    assert len(db.tables["business_pain_hypotheses"]) == 1
    assert db.tables["business_pain_hypotheses"][0]["snapshot_id"] == "snapshot-1"
    assert db.tables["business_pain_hypotheses"][0]["status"] == "hypothesis"



def test_rejected_market_pattern_is_not_reopened_by_later_discovery():
    from market_pattern_discovery import discover_market_patterns

    pains = [
        _pain("pain-1", "company-1", "Manual invoice reconciliation takes several days"),
        _pain("pain-2", "company-2", "Manual invoice reconciliation requires several days"),
    ]
    candidate = build_cross_company_pattern_candidates(pains)[0]
    db = _DB(pains)
    db.tables["market_problem_patterns"] = [{
        "id": "pattern-rejected",
        "fingerprint": candidate["fingerprint"],
        "status": "rejected",
    }]

    result = discover_market_patterns(db)

    assert result["patterns_created"] == 0
    assert result["saas_candidates_created"] == 0
    assert db.tables.get("saas_opportunities", []) == []

def test_discovery_recovers_from_concurrent_pattern_link_and_candidate_inserts():
    from market_pattern_discovery import discover_market_patterns

    class RaceQuery(_Query):
        def execute(self):
            from uuid import uuid4

            rows = self.db.tables.setdefault(self.table_name, [])
            if self.insert_rows is not None:
                for item in self.insert_rows:
                    if self.table_name == "market_problem_patterns" and any(
                        row.get("fingerprint") == item.get("fingerprint") for row in rows
                    ):
                        raise RuntimeError("unique pattern fingerprint conflict")
                    if self.table_name == "market_pattern_pains" and any(
                        row.get("market_pattern_id") == item.get("market_pattern_id")
                        and row.get("company_pain_id") == item.get("company_pain_id")
                        for row in rows
                    ):
                        raise RuntimeError("duplicate pattern pain link")
                    if self.table_name == "saas_opportunities" and any(
                        row.get("discovery_fingerprint") == item.get("discovery_fingerprint")
                        for row in rows
                    ):
                        raise RuntimeError("unique SaaS fingerprint conflict")
                return super().execute()

            if self.table_name == "market_problem_patterns" and "fingerprint" in self.filters:
                fingerprint = self.filters["fingerprint"]
                if fingerprint not in self.db.injected_patterns:
                    self.db.injected_patterns.add(fingerprint)
                    rows.append({
                        "id": "concurrent-pattern",
                        "fingerprint": fingerprint,
                        "status": "candidate",
                    })
                    return _Response([])  # Simulate a read that raced the concurrent commit.
            if self.table_name == "market_pattern_pains" and "market_pattern_id" in self.filters:
                pattern_id = self.filters["market_pattern_id"]
                if pattern_id not in self.db.injected_links:
                    self.db.injected_links.add(pattern_id)
                    first_pain = self.db.tables["business_pain_hypotheses"][0]
                    rows.append({
                        "market_pattern_id": pattern_id,
                        "company_pain_id": first_pain["id"],
                    })
                    return _Response([])
            if self.table_name == "saas_opportunities" and "discovery_fingerprint" in self.filters:
                fingerprint = self.filters["discovery_fingerprint"]
                if fingerprint not in self.db.injected_opportunities:
                    self.db.injected_opportunities.add(fingerprint)
                    rows.append({
                        "id": "concurrent-opportunity",
                        "discovery_fingerprint": fingerprint,
                    })
                    return _Response([])
            return super().execute()

    class RaceDB(_DB):
        def __init__(self, pains):
            super().__init__(pains)
            self.injected_patterns = set()
            self.injected_links = set()
            self.injected_opportunities = set()

        def table(self, name):
            return RaceQuery(self, name)

    db = RaceDB([
        _pain("pain-1", "company-1", "Manual invoice reconciliation takes several days"),
        _pain("pain-2", "company-2", "Manual invoice reconciliation requires several days"),
    ])

    result = discover_market_patterns(db)

    assert result["patterns_created"] == 0
    assert result["evidence_links_created"] == 1
    assert result["saas_candidates_created"] == 0
    assert len(db.tables["market_problem_patterns"]) == 1
    assert len(db.tables["market_pattern_pains"]) == 2
    assert len(db.tables["saas_opportunities"]) == 1
