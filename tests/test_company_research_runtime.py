from copy import deepcopy

from company_research_runtime import run_company_research_worker_once


class FakeRepository:
    def __init__(self):
        self.job = {
            "operation_id": "research:example:1",
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
            "grounded_sources": ["https://example.com/about"],
            "provider_usage": {"prompt_tokens": 10, "output_tokens": 5},
        }


def test_runtime_composes_worker_grounded_provider_and_actual_cost_settlement():
    repository = FakeRepository()
    result = run_company_research_worker_once(
        repository,
        provider=FakeProvider(),
        worker_id="worker-a",
        input_price_microusd_per_million_tokens=2_000_000,
        output_price_microusd_per_million_tokens=4_000_000,
    )
    complete = next(call[1] for call in repository.calls if call[0] == "complete")
    assert result["status"] == "succeeded"
    assert complete["actual_cost_microusd"] == 40
    assert complete["result"]["accepted_fact_count"] == 1


def test_runtime_does_not_claim_when_provider_or_pricing_is_invalid():
    repository = FakeRepository()
    try:
        run_company_research_worker_once(
            repository,
            provider=FakeProvider(),
            worker_id="worker-a",
            input_price_microusd_per_million_tokens=0,
            output_price_microusd_per_million_tokens=1,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("expected pricing validation error")
    assert repository.calls == []
