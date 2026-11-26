import pytest

from company_research_admission import evaluate_research_admission


LIMITS = {
    "max_jobs_per_hour": 20,
    "max_jobs_per_domain_per_day": 4,
    "max_concurrent_jobs": 3,
    "max_daily_cost_microusd": 5_000_000,
}
USAGE = {
    "jobs_last_hour": 5,
    "jobs_by_domain_today": {"example.com": 1},
    "running_jobs": 1,
    "spent_today_microusd": 1_000_000,
}


def test_admission_allows_job_inside_all_limits():
    decision = evaluate_research_admission(
        domain="Example.COM", estimated_cost_microusd=500_000,
        limits=LIMITS, usage=USAGE,
    )
    assert decision == {
        "allowed": True, "reason": "within_limits",
        "domain": "example.com", "estimated_cost_microusd": 500_000,
    }


@pytest.mark.parametrize(
    ("usage_override", "cost", "reason"),
    [
        ({"jobs_last_hour": 20}, 1, "global_hourly_limit"),
        ({"jobs_by_domain_today": {"example.com": 4}}, 1, "domain_daily_limit"),
        ({"running_jobs": 3}, 1, "concurrency_limit"),
        ({"spent_today_microusd": 4_900_000}, 100_001, "daily_cost_limit"),
    ],
)
def test_admission_blocks_each_limit(usage_override, cost, reason):
    usage = {**USAGE, **usage_override}
    decision = evaluate_research_admission(
        domain="example.com", estimated_cost_microusd=cost,
        limits=LIMITS, usage=usage,
    )
    assert decision["allowed"] is False
    assert decision["reason"] == reason


def test_exact_daily_cost_boundary_is_allowed():
    decision = evaluate_research_admission(
        domain="example.com", estimated_cost_microusd=4_000_000,
        limits=LIMITS, usage=USAGE,
    )
    assert decision["allowed"] is True


@pytest.mark.parametrize(
    ("domain", "cost", "limits", "usage"),
    [
        ("", 1, LIMITS, USAGE),
        ("example.com", True, LIMITS, USAGE),
        ("example.com", 1, {**LIMITS, "max_jobs_per_hour": 0}, USAGE),
        ("example.com", 1, LIMITS, {**USAGE, "running_jobs": -1}),
        ("example.com", 1, LIMITS, {**USAGE, "jobs_by_domain_today": []}),
    ],
)
def test_admission_rejects_invalid_inputs(domain, cost, limits, usage):
    with pytest.raises(ValueError):
        evaluate_research_admission(
            domain=domain, estimated_cost_microusd=cost,
            limits=limits, usage=usage,
        )
