from copy import deepcopy

from company_research_runtime import run_company_research_worker_once


class FakeRepository:
    def __init__(self):
        self.job = {
            "operation_id": "research:example:1",
            "lead_id": "00000000-0000-4000-8000-000000000001",
            "attempt_count": 1,
            "payload": {
                "company_name": "Example Ltd",
                "company_domain": "example.com",
            },
        }
        self.calls = []

    def claim(self, **kwargs):
        self.calls.append(("claim", kwargs))
        job, self.job = self.job, None
        return deepcopy(job)

    def heartbeat(self, **kwargs):
        self.calls.append(("heartbeat", kwargs))
        return {"operation_id": kwargs["operation_id"]}

    def complete(self, **kwargs):
        self.calls.append(("complete", kwargs))
        return {
            "operation_id": kwargs["operation_id"],
            "status": "succeeded",
            "result": kwargs["result"],
        }

    def fail(self, **kwargs):
        self.calls.append(("fail", kwargs))
        return {"status": "dead_letter"}


class FakeSnapshotQuery:
    def __init__(self, db, table_name):
        self.db = db
        self.table_name = table_name
        self.row = None
        self.filters = {}

    def select(self, _columns):
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def order(self, _column, desc=False):
        return self

    def limit(self, _value):
        return self

    def insert(self, row):
        self.row = row
        return self

    def execute(self):
        table_rows = self.db.rows if self.table_name == "company_research_snapshots" else []
        if self.row is not None:
            if any(existing["snapshot_id"] == self.row["snapshot_id"] for existing in table_rows):
                raise RuntimeError("duplicate snapshot id")
            table_rows.append(deepcopy(self.row))
            return type("Response", (), {"data": [deepcopy(self.row)]})()
        rows = [row for row in table_rows if all(row.get(key) == value for key, value in self.filters.items())]
        return type("Response", (), {"data": rows[:1]})()


class FakeSnapshotDB:
    def __init__(self):
        self.rows = []

    def table(self, name):
        return FakeSnapshotQuery(self, name)


class FakeProvider:
    def research_company(self, *, prompt, heartbeat):
        return {
            "research": {
                "company_facts": [{
                    "category": "business_model",
                    "fact": "B2B provider",
                    "source_url": "https://example.com/about",
                }],
                "decision_maker": {},
            },
            "grounded_sources": [{"source_url": "https://example.com/about", "title": "", "snippet": ""}],
            "research": {
                "company_facts": [{
                    "category": "business_model",
                    "fact": "B2B provider",
                    "source_url": "https://example.com/about",
                }],
                "decision_maker": {},
                "lead_fit_assessment": {
                    "assessment_version": "1.0",
                    "fit_score": 80,
                    "confidence": 0.7,
                    "rationale": "Grounded B2B company facts support a preliminary fit.",
                    "fit_signals": ["B2B provider"],
                    "risk_signals": [],
                    "recommended_next_step": "Confirm the current operational need.",
                    "evidence": [{
                        "source_url": "https://example.com/about",
                        "claim": "B2B provider",
                        "evidence_type": "fact",
                    }],
                },
            },
            "provider_usage": {"prompt_tokens": 10, "output_tokens": 5},
        }


def test_runtime_composes_worker_grounded_provider_and_actual_cost_settlement():
    repository = FakeRepository()
    snapshot_db = FakeSnapshotDB()
    result = run_company_research_worker_once(
        repository,
        provider=FakeProvider(),
        snapshot_db=snapshot_db,
        worker_id="worker-a",
        input_price_microusd_per_million_tokens=2_000_000,
        output_price_microusd_per_million_tokens=4_000_000,
    )
    complete = next(call[1] for call in repository.calls if call[0] == "complete")
    assert result["status"] == "succeeded"
    assert complete["actual_cost_microusd"] == 40
    assert complete["result"]["accepted_fact_count"] == 1
    assert complete["result"]["snapshot_persisted"] is True
    assert complete["result"]["snapshot_id"] == snapshot_db.rows[0]["snapshot_id"]
    assert snapshot_db.rows[0]["lead_id"] == "00000000-0000-4000-8000-000000000001"
    assert snapshot_db.rows[0]["dossier"]["facts"][0]["fact"] == "B2B provider"


def test_runtime_does_not_claim_when_provider_or_pricing_is_invalid():
    repository = FakeRepository()
    try:
        run_company_research_worker_once(
            repository,
            provider=FakeProvider(),
            snapshot_db=FakeSnapshotDB(),
            worker_id="worker-a",
            input_price_microusd_per_million_tokens=0,
            output_price_microusd_per_million_tokens=1,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("expected pricing validation error")
    assert repository.calls == []
