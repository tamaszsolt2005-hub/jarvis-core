import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from company_research_store import get_company_research_history, save_company_research_snapshot


def make_dossier():
    content = {"facts": [{"category": "business_model", "fact": "B2B"}], "decision_maker": {}}
    canonical = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        **content,
        "schema_version": 1,
        "snapshot_id": str(uuid4()),
        "researched_at": datetime(2026, 11, 26, tzinfo=timezone.utc).isoformat(),
        "content_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }


class Response:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, db):
        self.db = db
        self.row = None
        self.filters = {}
        self.limit_value = None

    def insert(self, row):
        self.row = row
        return self

    def select(self, _columns):
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def order(self, _column, desc=False):
        self.desc = desc
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def execute(self):
        if self.row is not None:
            if any(row.get("snapshot_id") == self.row.get("snapshot_id") for row in self.db.rows):
                raise RuntimeError("duplicate snapshot id")
            self.db.rows.append(self.row)
            return Response([self.row])
        rows = [row for row in self.db.rows if all(row.get(k) == v for k, v in self.filters.items())]
        return Response(rows[: self.limit_value])


class FakeDB:
    def __init__(self):
        self.rows = []

    def table(self, _name):
        return FakeQuery(self)


def test_save_company_research_snapshot_persists_full_immutable_document():
    db = FakeDB()
    dossier = make_dossier()
    result = save_company_research_snapshot(
        db, lead_id=str(uuid4()), company_domain="www.example.com", dossier=dossier
    )
    assert result["snapshot_id"] == dossier["snapshot_id"]
    assert db.rows[0]["company_domain"] == "www.example.com"
    assert db.rows[0]["dossier"]["facts"] == dossier["facts"]
    assert db.rows[0]["content_sha256"] == dossier["content_sha256"]


def test_snapshot_rejects_modified_content_fingerprint():
    db = FakeDB()
    dossier = make_dossier()
    dossier["facts"][0]["fact"] = "tampered"
    with pytest.raises(ValueError, match="fingerprint"):
        save_company_research_snapshot(db, lead_id=str(uuid4()), company_domain="example.com", dossier=dossier)
    assert db.rows == []


@pytest.mark.parametrize("domain", ["", "https://example.com", "example.com/path", "example.com;drop"])
def test_snapshot_rejects_invalid_company_domain(domain):
    with pytest.raises(ValueError, match="domain"):
        save_company_research_snapshot(FakeDB(), lead_id=str(uuid4()), company_domain=domain, dossier=make_dossier())


def test_history_reads_only_requested_lead_and_caps_limit():
    db = FakeDB()
    lead_id = str(uuid4())
    other_id = str(uuid4())
    for owner in (lead_id, other_id):
        save_company_research_snapshot(db, lead_id=owner, company_domain="example.com", dossier=make_dossier())
    history = get_company_research_history(db, lead_id=lead_id, limit=500)
    assert len(history) == 1
    assert history[0]["lead_id"] == lead_id


@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_history_rejects_invalid_limit(limit):
    with pytest.raises(ValueError, match="limit"):
        get_company_research_history(FakeDB(), lead_id=str(uuid4()), limit=limit)



def test_snapshot_save_is_idempotent_for_the_same_worker_operation():
    db = FakeDB()
    lead_id = str(uuid4())
    first = save_company_research_snapshot(db, lead_id=lead_id, company_domain="example.com",
        dossier=make_dossier(), idempotency_key="research:lead:123456")
    second = save_company_research_snapshot(db, lead_id=lead_id, company_domain="example.com",
        dossier=make_dossier(), idempotency_key="research:lead:123456")
    assert first["snapshot_id"] == second["snapshot_id"]
    assert len(db.rows) == 1
    assert second["researched_at"] == first["researched_at"]


def test_snapshot_idempotency_rejects_changed_content_for_same_operation():
    db = FakeDB()
    lead_id = str(uuid4())
    dossier = make_dossier()
    save_company_research_snapshot(db, lead_id=lead_id, company_domain="example.com",
        dossier=dossier, idempotency_key="research:lead:123456")
    changed = make_dossier()
    changed["facts"][0]["fact"] = "different content"
    canonical = json.dumps({"facts": changed["facts"], "decision_maker": changed["decision_maker"]},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    changed["content_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    with pytest.raises(ValueError, match="idempotency conflict"):
        save_company_research_snapshot(db, lead_id=lead_id, company_domain="example.com",
            dossier=changed, idempotency_key="research:lead:123456")
    assert len(db.rows) == 1



def test_snapshot_fingerprint_includes_grounded_pain_hypotheses():
    db = FakeDB()
    dossier = make_dossier()
    dossier["pain_hypotheses"] = [{
        "statement": "Manual invoice reconciliation may create delays.",
        "category": "finance",
        "confidence": 0.6,
        "evidence": [{
            "source_url": "https://example.com/report",
            "excerpt": "Invoices are reconciled manually over several days.",
            "evidence_type": "supporting",
        }],
    }]
    canonical = json.dumps({
        "facts": dossier["facts"],
        "decision_maker": dossier["decision_maker"],
        "pain_hypotheses": dossier["pain_hypotheses"],
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    dossier["content_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    saved = save_company_research_snapshot(
        db, lead_id=str(uuid4()), company_domain="example.com",
        dossier=dossier, idempotency_key="research:pain:123456",
    )

    assert db.rows[0]["dossier"]["pain_hypotheses"] == dossier["pain_hypotheses"]
    assert db.rows[0]["content_sha256"] == dossier["content_sha256"]
    assert saved["snapshot_id"] == db.rows[0]["snapshot_id"]


def test_snapshot_persister_connects_grounded_pains_to_pattern_and_saas_candidate_idempotently():
    from company_research_store import make_company_research_snapshot_persister

    class PipelineQuery:
        def __init__(self, db, table):
            self.db = db
            self.table_name = table
            self.filters = {}
            self.insert_rows = None
            self.limit_value = None

        def select(self, *_args, **_kwargs):
            return self

        def eq(self, key, value):
            self.filters[key] = value
            return self

        def order(self, *_args, **_kwargs):
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
                        row.setdefault("id", str(uuid4()))
                    if self.table_name == "market_pattern_pains" and any(
                        existing.get("market_pattern_id") == row.get("market_pattern_id")
                        and existing.get("company_pain_id") == row.get("company_pain_id")
                        for existing in rows
                    ):
                        continue
                    rows.append(row)
                    inserted.append(row)
                return Response(inserted)
            selected = [
                row for row in rows
                if all(row.get(key) == value for key, value in self.filters.items())
            ]
            if self.limit_value is not None:
                selected = selected[:self.limit_value]
            return Response(selected)

    class PipelineDB:
        def __init__(self):
            self.tables = {"company_research_snapshots": []}

        def table(self, name):
            return PipelineQuery(self, name)

    lead_id = str(uuid4())
    dossier = make_dossier()
    dossier["pain_hypotheses"] = [
        {
            "statement": "Manual invoice reconciliation takes several days",
            "category": "finance",
            "confidence": 0.62,
            "evidence": [{
                "source_url": "https://example.com/finance-process",
                "excerpt": "Invoices are reconciled manually over several days.",
                "evidence_type": "supporting",
            }],
        }
    ]
    content = {
        "facts": dossier["facts"],
        "decision_maker": dossier["decision_maker"],
        "pain_hypotheses": dossier["pain_hypotheses"],
    }
    canonical = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    dossier["content_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    # A second company supplies the independent evidence required for a pattern.
    db = PipelineDB()
    db.tables["business_pain_hypotheses"] = [{
        "id": "pain-existing",
        "lead_id": str(uuid4()),
        "statement": "Manual invoice reconciliation requires several days",
        "category": "finance",
        "confidence": 0.58,
        "status": "hypothesis",
        "evidence": [{
            "source_url": "https://other.example.com/finance-process",
            "excerpt": "Invoices are reconciled manually and take several days.",
            "evidence_type": "supporting",
        }],
    }]
    persist = make_company_research_snapshot_persister(db)
    job = {
        "operation_id": "research:pipeline:123456",
        "lead_id": lead_id,
        "payload": {"company_domain": "example.com"},
    }
    result = {"company_domain": "example.com", "company_dossier": dossier}

    first = persist(job, result)
    second = persist(job, result)

    assert first["snapshot_persisted"] is True
    assert first["pain_hypotheses_created"] == 1
    assert first["market_pattern_discovery"]["patterns_created"] == 1
    assert first["market_pattern_discovery"]["saas_candidates_created"] == 1
    assert second["pain_hypotheses_created"] == 0
    assert second["market_pattern_discovery"]["patterns_created"] == 0
    assert second["market_pattern_discovery"]["saas_candidates_created"] == 0
    assert len(db.tables["company_research_snapshots"]) == 1
    assert len(db.tables["business_pain_hypotheses"]) == 2
    assert len(db.tables["market_problem_patterns"]) == 1
    assert db.tables["market_problem_patterns"][0]["status"] == "candidate"
    assert len(db.tables["market_pattern_pains"]) == 2
    assert len(db.tables["saas_opportunities"]) == 1
    assert db.tables["saas_opportunities"][0]["status"] == "draft"
