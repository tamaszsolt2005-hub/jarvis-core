"""Deterministic admission checks for research job rate and cost guardrails.

The function evaluates a supplied usage snapshot only. It does not reserve
capacity, persist counters, or provide an atomic global budget guarantee.
"""
from __future__ import annotations

from typing import Any


def _integer(value: Any, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        qualifier = "positive" if minimum == 1 else "non-negative"
        raise ValueError(f"{name} must be a {qualifier} integer")
    return value


def evaluate_research_admission(
    *,
    domain: str,
    estimated_cost_microusd: int,
    limits: dict[str, int],
    usage: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate one job against global, per-domain, concurrency and cost limits.

    Cost values use integer micro-USD (1 USD = 1,000,000 micro-USD) to avoid
    floating-point rounding. Usage counters must represent the same windows
    and accounting source as the configured limits.
    """
    if not isinstance(domain, str) or not domain.strip():
        raise ValueError("domain is required")
    domain_key = domain.strip().casefold()
    estimated_cost = _integer(estimated_cost_microusd, "estimated_cost_microusd")

    required_limits = (
        "max_jobs_per_hour",
        "max_jobs_per_domain_per_day",
        "max_concurrent_jobs",
        "max_daily_cost_microusd",
    )
    if not isinstance(limits, dict) or not isinstance(usage, dict):
        raise ValueError("limits and usage must be objects")
    normalized_limits = {
        key: _integer(limits.get(key), key, minimum=1) for key in required_limits
    }

    jobs_last_hour = _integer(usage.get("jobs_last_hour"), "jobs_last_hour")
    jobs_for_domain_today = _integer(
        usage.get("jobs_by_domain_today", {}).get(domain_key, 0)
        if isinstance(usage.get("jobs_by_domain_today", {}), dict) else None,
        "jobs_for_domain_today",
    )
    running_jobs = _integer(usage.get("running_jobs"), "running_jobs")
    spent_today = _integer(usage.get("spent_today_microusd"), "spent_today_microusd")

    checks = (
        (
            jobs_last_hour >= normalized_limits["max_jobs_per_hour"],
            "global_hourly_limit",
        ),
        (
            jobs_for_domain_today >= normalized_limits["max_jobs_per_domain_per_day"],
            "domain_daily_limit",
        ),
        (
            running_jobs >= normalized_limits["max_concurrent_jobs"],
            "concurrency_limit",
        ),
        (
            spent_today + estimated_cost > normalized_limits["max_daily_cost_microusd"],
            "daily_cost_limit",
        ),
    )
    for blocked, reason in checks:
        if blocked:
            return {
                "allowed": False,
                "reason": reason,
                "domain": domain_key,
                "estimated_cost_microusd": estimated_cost,
            }

    return {
        "allowed": True,
        "reason": "within_limits",
        "domain": domain_key,
        "estimated_cost_microusd": estimated_cost,
    }
