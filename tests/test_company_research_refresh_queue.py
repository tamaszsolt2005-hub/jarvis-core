import pytest
from datetime import datetime, timezone
from uuid import uuid4

from company_research_job_repository import CompanyResearchAdmissionRejected, CompanyResearchBudgetExceeded
from company_research_refresh_queue import (
    enqueue_company_research_refreshes,
    enqueue_company_research_refreshes_with_admission,
)


class FakeRepository:
    def __init__(self):
        self.by_operation_id = {}
        self.create_kwargs = []

    def create(self, *, operation_id, lead_id, payload, estimated_cost_microusd=0, daily_budget_microusd=None, max_jobs_per_hour=None, max_jobs_per_domain_per_day=None):
        self.create_kwargs.append({
            "estimated_cost_microusd": estimated_cost_microusd,
            "daily_budget_microusd": daily_budget_microusd,
            "max_jobs_per_hour": max_jobs_per_hour,
            "max_jobs_per_domain_per_day": max_jobs_per_domain_per_day,
        })
        if operation_id not in self.by_operation_id:
            self.by_operation_id[operation_id] = {
                "operation_id": operation_id, "lead_id": lead_id,
                "payload": payload, "status": "queued",
            }
        return self.by_operation_id[operation_id]


def test_queue_bridge_enqueues_only_planner_candidates_and_is_idempotent():
    eligible_id = str(uuid4())
    rejected_id = str(uuid4())
    leads = [
        {"id": eligible_id, "company_name": "Eligible Ltd", "website": "https://eligible.example"},
        {"id": rejected_id, "company_name": "No Contact Ltd", "website": "https://blocked.example",
         "status": "opted_out"},
    ]
    repository = FakeRepository()
    now = datetime(2026, 11, 26, tzinfo=timezone.utc)

    enqueue_limits = {
        "max_jobs_per_hour": 10,
        "max_jobs_per_domain_per_day": 10,
        "max_concurrent_jobs": 2,
        "max_daily_cost_microusd": 1_000_000,
    }
    first = enqueue_company_research_refreshes(
        repository, leads, {}, limits=enqueue_limits,
        input_price_microusd_per_million_tokens=1_000_000,
        output_price_microusd_per_million_tokens=1_000_000, now=now,
    )
    second = enqueue_company_research_refreshes(
        repository, leads, {}, limits=enqueue_limits,
        input_price_microusd_per_million_tokens=1_000_000,
        output_price_microusd_per_million_tokens=1_000_000, now=now,
    )

    assert len(first) == 1
    assert len(second) == 1
    assert first[0]["operation_id"] == second[0]["operation_id"]
    assert first[0]["payload"]["reason"] == "missing_dossier"
    assert first[0]["payload"]["company_domain"] == "eligible.example"
    assert len(repository.by_operation_id) == 1
    assert repository.create_kwargs[0] == {
        "estimated_cost_microusd": 14_048,
        "daily_budget_microusd": 1_000_000,
        "max_jobs_per_hour": 10,
        "max_jobs_per_domain_per_day": 10,
    }


def test_new_snapshot_version_produces_a_new_refresh_operation_id():
    lead_id = str(uuid4())
    leads = [{"id": lead_id, "company_name": "Example", "website": "https://example.com"}]
    repository = FakeRepository()
    now = datetime(2026, 11, 26, tzinfo=timezone.utc)
    old_dossier = {"researched_at": "2026-01-01T00:00:00+00:00"}
    new_dossier = {"researched_at": "2026-02-01T00:00:00+00:00"}

    enqueue_limits = {
        "max_jobs_per_hour": 10,
        "max_jobs_per_domain_per_day": 10,
        "max_concurrent_jobs": 2,
        "max_daily_cost_microusd": 1_000_000,
    }
    old_job = enqueue_company_research_refreshes(
        repository, leads, {lead_id: old_dossier}, limits=enqueue_limits,
        input_price_microusd_per_million_tokens=1_000_000,
        output_price_microusd_per_million_tokens=1_000_000, now=now,
    )[0]
    new_job = enqueue_company_research_refreshes(
        repository, leads, {lead_id: new_dossier}, limits=enqueue_limits,
        input_price_microusd_per_million_tokens=1_000_000,
        output_price_microusd_per_million_tokens=1_000_000, now=now,
    )[0]

    assert old_job["operation_id"] != new_job["operation_id"]
    assert len(repository.by_operation_id) == 2


def test_queue_bridge_does_not_enqueue_fresh_or_invalid_domain_leads():
    repository = FakeRepository()
    leads = [
        {"id": str(uuid4()), "company_name": "Fresh", "website": "https://fresh.example"},
        {"id": str(uuid4()), "company_name": "Invalid", "website": "javascript:alert(1)"},
    ]
    fresh_id = leads[0]["id"]
    result = enqueue_company_research_refreshes(
        repository, leads,
        {fresh_id: {"researched_at": "2026-11-25T00:00:00+00:00"}},
        limits={
            "max_jobs_per_hour": 10,
            "max_jobs_per_domain_per_day": 10,
            "max_concurrent_jobs": 2,
            "max_daily_cost_microusd": 1_000_000,
        },
        input_price_microusd_per_million_tokens=1_000_000,
        output_price_microusd_per_million_tokens=1_000_000,
        now=datetime(2026, 11, 26, tzinfo=timezone.utc),
    )
    assert result == []
    assert repository.by_operation_id == {}



def test_admission_aware_queue_limits_batch_and_tracks_cost_estimates():
    leads = [
        {"id": str(uuid4()), "company_name": "Alpha", "website": "https://alpha.example"},
        {"id": str(uuid4()), "company_name": "Beta", "website": "https://beta.example"},
    ]
    repository = FakeRepository()
    result = enqueue_company_research_refreshes_with_admission(
        repository, leads, {},
        limits={
            "max_jobs_per_hour": 1,
            "max_jobs_per_domain_per_day": 2,
            "max_concurrent_jobs": 2,
            "max_daily_cost_microusd": 1_000_000,
        },
        usage_snapshot={
            "jobs_last_hour": 0, "jobs_by_domain_today": {},
            "running_jobs": 0, "spent_today_microusd": 0,
        },
        input_price_microusd_per_million_tokens=1_000_000,
        output_price_microusd_per_million_tokens=1_000_000,
        now=datetime(2026, 11, 26, tzinfo=timezone.utc),
    )
    assert len(result["jobs"]) == 1
    assert len(result["rejected"]) == 1
    assert result["rejected"][0]["reason"] == "global_hourly_limit"
    assert result["jobs"][0]["payload"]["estimated_cost_microusd"] == 14_048
    assert repository.create_kwargs[0] == {
        "estimated_cost_microusd": 14_048,
        "daily_budget_microusd": 1_000_000,
        "max_jobs_per_hour": 1,
        "max_jobs_per_domain_per_day": 2,
    }


def test_admission_aware_queue_rejects_job_over_remaining_daily_budget():
    lead_id = str(uuid4())
    repository = FakeRepository()
    result = enqueue_company_research_refreshes_with_admission(
        repository,
        [{"id": lead_id, "company_name": "Costly", "website": "https://costly.example"}],
        {},
        limits={
            "max_jobs_per_hour": 10,
            "max_jobs_per_domain_per_day": 2,
            "max_concurrent_jobs": 2,
            "max_daily_cost_microusd": 1_000_000,
        },
        usage_snapshot={
            "jobs_last_hour": 0, "jobs_by_domain_today": {},
            "running_jobs": 0, "spent_today_microusd": 990_000,
        },
        input_price_microusd_per_million_tokens=1_000_000,
        output_price_microusd_per_million_tokens=1_000_000,
        now=datetime(2026, 11, 26, tzinfo=timezone.utc),
    )
    assert result["jobs"] == []
    assert result["rejected"] == [{"lead_id": lead_id, "reason": "daily_cost_limit"}]
    assert repository.by_operation_id == {}


def test_admission_aware_queue_rejects_malformed_usage_snapshot():
    repository = FakeRepository()
    with pytest.raises(ValueError, match="usage_snapshot"):
        enqueue_company_research_refreshes_with_admission(
            repository, [], {}, limits={}, usage_snapshot=None,
            input_price_microusd_per_million_tokens=1_000_000,
        output_price_microusd_per_million_tokens=1_000_000,
        )



def test_admission_queue_matches_domain_usage_case_insensitively():
    lead_id = str(uuid4())
    repository = FakeRepository()
    result = enqueue_company_research_refreshes_with_admission(
        repository,
        [{"id": lead_id, "company_name": "Alpha", "website": "https://alpha.example"}],
        {},
        limits={
            "max_jobs_per_hour": 10,
            "max_jobs_per_domain_per_day": 1,
            "max_concurrent_jobs": 2,
            "max_daily_cost_microusd": 1_000_000,
        },
        usage_snapshot={
            "jobs_last_hour": 0,
            "jobs_by_domain_today": {"ALPHA.EXAMPLE": 1},
            "running_jobs": 0,
            "spent_today_microusd": 0,
        },
        input_price_microusd_per_million_tokens=1_000_000,
        output_price_microusd_per_million_tokens=1_000_000,
        now=datetime(2026, 11, 26, tzinfo=timezone.utc),
    )
    assert result["jobs"] == []
    assert result["rejected"] == [{"lead_id": lead_id, "reason": "domain_daily_limit"}]



def test_admission_queue_reports_atomic_database_budget_rejection():
    class BudgetLimitedRepository(FakeRepository):
        def create(self, **kwargs):
            raise CompanyResearchBudgetExceeded("Daily research budget exceeded.")

    lead_id = str(uuid4())
    result = enqueue_company_research_refreshes_with_admission(
        BudgetLimitedRepository(),
        [{"id": lead_id, "company_name": "Alpha", "website": "https://alpha.example"}],
        {},
        limits={
            "max_jobs_per_hour": 10,
            "max_jobs_per_domain_per_day": 10,
            "max_concurrent_jobs": 2,
            "max_daily_cost_microusd": 500,
        },
        usage_snapshot={
            "jobs_last_hour": 0, "jobs_by_domain_today": {},
            "running_jobs": 0, "spent_today_microusd": 0,
        },
        input_price_microusd_per_million_tokens=1_000_000,
        output_price_microusd_per_million_tokens=1_000_000,
        now=datetime(2026, 11, 26, tzinfo=timezone.utc),
    )
    assert result == {
        "jobs": [],
        "rejected": [{"lead_id": lead_id, "reason": "daily_cost_limit"}],
    }



@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("global_hourly_limit", "global_hourly_limit"),
        ("domain_daily_limit", "domain_daily_limit"),
    ],
)
def test_admission_queue_reports_database_rate_limit_rejection(reason, expected):
    class RateLimitedRepository(FakeRepository):
        def create(self, **kwargs):
            raise CompanyResearchAdmissionRejected(reason)

    lead_id = str(uuid4())
    result = enqueue_company_research_refreshes_with_admission(
        RateLimitedRepository(),
        [{"id": lead_id, "company_name": "Alpha", "website": "https://alpha.example"}],
        {},
        limits={
            "max_jobs_per_hour": 10,
            "max_jobs_per_domain_per_day": 10,
            "max_concurrent_jobs": 2,
            "max_daily_cost_microusd": 500,
        },
        usage_snapshot={
            "jobs_last_hour": 0, "jobs_by_domain_today": {},
            "running_jobs": 0, "spent_today_microusd": 0,
        },
        input_price_microusd_per_million_tokens=1_000_000,
        output_price_microusd_per_million_tokens=1_000_000,
        now=datetime(2026, 11, 26, tzinfo=timezone.utc),
    )
    assert result == {
        "jobs": [],
        "rejected": [{"lead_id": lead_id, "reason": expected}],
    }
