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



def estimate_research_cost_microusd(
    *,
    input_tokens: int,
    output_tokens: int,
    input_price_microusd_per_million_tokens: int,
    output_price_microusd_per_million_tokens: int,
) -> int:
    """Estimate provider cost in micro-USD using integer-only ceiling math.

    Prices are supplied by the caller from its explicitly configured provider
    pricing schedule; this function embeds no vendor/model pricing assumptions.
    """
    input_tokens = _integer(input_tokens, "input_tokens")
    output_tokens = _integer(output_tokens, "output_tokens")
    input_price = _integer(
        input_price_microusd_per_million_tokens,
        "input_price_microusd_per_million_tokens",
        minimum=1,
    )
    output_price = _integer(
        output_price_microusd_per_million_tokens,
        "output_price_microusd_per_million_tokens",
        minimum=1,
    )
    numerator = input_tokens * input_price + output_tokens * output_price
    return (numerator + 999_999) // 1_000_000



def estimate_research_cost_ceiling_microusd(
    *,
    input_price_microusd_per_million_tokens: int,
    output_price_microusd_per_million_tokens: int,
    max_input_tokens_per_attempt: int = 12000,
    max_output_tokens_per_attempt: int = 2048,
    max_attempts: int = 1,
) -> int:
    """Return a conservative per-job reservation ceiling for bounded provider calls.

    The default input-token ceiling is deliberately conservative and matches
    the research adapter's 12,000-character prompt limit. Retries are included
    in both input and output exposure; callers enabling retries must pass the
    same attempt limit to this function and to the provider adapter.
    """
    max_input_tokens = _integer(
        max_input_tokens_per_attempt, "max_input_tokens_per_attempt", minimum=1
    )
    max_output_tokens = _integer(
        max_output_tokens_per_attempt, "max_output_tokens_per_attempt", minimum=128
    )
    attempts = _integer(max_attempts, "max_attempts", minimum=1)
    if max_output_tokens > 4096 or attempts > 3:
        raise ValueError("provider cost ceiling exceeds supported hard limits")
    return estimate_research_cost_microusd(
        input_tokens=max_input_tokens * attempts,
        output_tokens=max_output_tokens * attempts,
        input_price_microusd_per_million_tokens=input_price_microusd_per_million_tokens,
        output_price_microusd_per_million_tokens=output_price_microusd_per_million_tokens,
    )
