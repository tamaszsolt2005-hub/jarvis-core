"""Planner-to-repository bridge for idempotently enqueueing refresh jobs.

This module only creates durable queue records. It never performs research,
starts a worker, calls Gemini, or sends outbound communications.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from company_research_job_repository import (
    CompanyResearchAdmissionRejected,
    CompanyResearchBudgetExceeded,
    CompanyResearchJobRepository,
)
from company_research_admission import (
    estimate_research_cost_ceiling_microusd,
    evaluate_research_admission,
)
from company_research_refresh_planner import plan_company_research_refresh_candidates


def _operation_id(candidate: dict[str, Any]) -> str:
    lead_id = str(candidate.get("lead_id") or "").strip()
    if not lead_id:
        raise ValueError("candidate lead_id is required")
    # A new dossier version creates a new idempotency key. A missing dossier
    # has a stable key until the first snapshot is successfully persisted.
    snapshot_marker = str(candidate.get("researched_at") or "missing")
    digest = hashlib.sha256(snapshot_marker.encode("utf-8")).hexdigest()[:20]
    return f"research-refresh:{lead_id}:{digest}"


def enqueue_company_research_refreshes(
    repository: CompanyResearchJobRepository,
    leads: list[dict[str, Any]],
    latest_dossiers: dict[str, Any],
    *,
    limits: dict[str, int],
    input_price_microusd_per_million_tokens: int,
    output_price_microusd_per_million_tokens: int,
    search_price_microusd_per_thousand_queries: int = 0,
    max_search_queries_per_attempt: int = 0,
    max_input_tokens_per_attempt: int = 12000,
    max_output_tokens_per_attempt: int = 2048,
    max_attempts: int = 1,
    now: datetime | None = None,
    max_age_days: int = 30,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Plan and enqueue using mandatory database-enforced cost/rate limits.

    Pricing is mandatory and must match the worker's actual-cost extractor.
    The reservation is computed here from the provider's hard token/attempt
    limits; callers cannot supply an arbitrarily low estimate.
    """
    estimated_cost_microusd_per_job = estimate_research_cost_ceiling_microusd(
        input_price_microusd_per_million_tokens=input_price_microusd_per_million_tokens,
        output_price_microusd_per_million_tokens=output_price_microusd_per_million_tokens,
        max_input_tokens_per_attempt=max_input_tokens_per_attempt,
        max_output_tokens_per_attempt=max_output_tokens_per_attempt,
        max_attempts=max_attempts,
        search_price_microusd_per_thousand_queries=search_price_microusd_per_thousand_queries,
        max_search_queries_per_attempt=max_search_queries_per_attempt,
    )
    candidates = plan_company_research_refresh_candidates(
        leads, latest_dossiers, now=now, max_age_days=max_age_days, limit=limit
    )
    jobs = []
    for candidate in candidates:
        jobs.append(repository.create(
            operation_id=_operation_id(candidate),
            lead_id=candidate["lead_id"],
            payload={
                "lead_id": candidate["lead_id"],
                "company_domain": candidate["company_domain"],
                "company_name": candidate["company_name"],
                "reason": candidate["reason"],
                "researched_at": candidate["researched_at"],
                "estimated_cost_microusd": estimated_cost_microusd_per_job,
            },
            estimated_cost_microusd=estimated_cost_microusd_per_job,
            daily_budget_microusd=limits["max_daily_cost_microusd"],
            max_jobs_per_hour=limits["max_jobs_per_hour"],
            max_jobs_per_domain_per_day=limits["max_jobs_per_domain_per_day"],
        ))
    return jobs



def enqueue_company_research_refreshes_with_admission(
    repository: CompanyResearchJobRepository,
    leads: list[dict[str, Any]],
    latest_dossiers: dict[str, Any],
    *,
    limits: dict[str, int],
    usage_snapshot: dict[str, Any],
    input_price_microusd_per_million_tokens: int,
    output_price_microusd_per_million_tokens: int,
    max_input_tokens_per_attempt: int = 12000,
    max_output_tokens_per_attempt: int = 2048,
    max_attempts: int = 1,
    now: datetime | None = None,
    max_age_days: int = 30,
    limit: int = 50,
) -> dict[str, list[dict[str, Any]]]:
    """Enqueue candidates through snapshot admission and atomic DB quotas.

    Pricing is mandatory and must match the worker's actual-cost extractor.
    The reservation is computed here from the provider's hard token/attempt
    limits; callers cannot supply an arbitrarily low estimate.

    The database is authoritative for hourly, per-domain daily and daily cost
    ceilings across concurrent enqueue calls. The local snapshot still provides
    early rejection and in-batch accounting for the concurrency estimate.
    """
    estimated_cost_microusd_per_job = estimate_research_cost_ceiling_microusd(
        input_price_microusd_per_million_tokens=input_price_microusd_per_million_tokens,
        output_price_microusd_per_million_tokens=output_price_microusd_per_million_tokens,
        max_input_tokens_per_attempt=max_input_tokens_per_attempt,
        max_output_tokens_per_attempt=max_output_tokens_per_attempt,
        max_attempts=max_attempts,
    )
    if not isinstance(usage_snapshot, dict):
        raise ValueError("usage_snapshot must be an object")
    domain_usage = usage_snapshot.get("jobs_by_domain_today", {})
    if not isinstance(domain_usage, dict):
        raise ValueError("jobs_by_domain_today must be an object")
    candidates = plan_company_research_refresh_candidates(
        leads, latest_dossiers, now=now, max_age_days=max_age_days, limit=limit
    )
    usage = {
        "jobs_last_hour": usage_snapshot.get("jobs_last_hour", 0),
        "jobs_by_domain_today": {str(key).strip().casefold(): value for key, value in domain_usage.items()},
        "running_jobs": usage_snapshot.get("running_jobs", 0),
        "spent_today_microusd": usage_snapshot.get("spent_today_microusd", 0),
    }
    jobs: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for candidate in candidates:
        domain = candidate["company_domain"]
        decision = evaluate_research_admission(
            domain=domain,
            estimated_cost_microusd=estimated_cost_microusd_per_job,
            limits=limits,
            usage=usage,
        )
        if not decision["allowed"]:
            rejected.append({"lead_id": candidate["lead_id"], "reason": decision["reason"]})
            continue
        try:
            job = repository.create(
                operation_id=_operation_id(candidate),
                lead_id=candidate["lead_id"],
                payload={
                    "lead_id": candidate["lead_id"],
                    "company_domain": domain,
                    "company_name": candidate["company_name"],
                    "reason": candidate["reason"],
                    "researched_at": candidate["researched_at"],
                    "estimated_cost_microusd": estimated_cost_microusd_per_job,
                },
                estimated_cost_microusd=estimated_cost_microusd_per_job,
                daily_budget_microusd=limits["max_daily_cost_microusd"],
                max_jobs_per_hour=limits["max_jobs_per_hour"],
                max_jobs_per_domain_per_day=limits["max_jobs_per_domain_per_day"],
            )
        except CompanyResearchBudgetExceeded:
            rejected.append({"lead_id": candidate["lead_id"], "reason": "daily_cost_limit"})
            continue
        except CompanyResearchAdmissionRejected as exc:
            rejected.append({"lead_id": candidate["lead_id"], "reason": exc.reason})
            continue
        jobs.append(job)
        usage["jobs_last_hour"] += 1
        usage["jobs_by_domain_today"][domain] = usage["jobs_by_domain_today"].get(domain, 0) + 1
        usage["spent_today_microusd"] += estimated_cost_microusd_per_job
    return {"jobs": jobs, "rejected": rejected}
