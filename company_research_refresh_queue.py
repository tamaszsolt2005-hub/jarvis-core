"""Planner-to-repository bridge for idempotently enqueueing refresh jobs.

This module only creates durable queue records. It never performs research,
starts a worker, calls Gemini, or sends outbound communications.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from company_research_job_repository import CompanyResearchJobRepository
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
    now: datetime | None = None,
    max_age_days: int = 30,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Plan eligible stale dossiers and idempotently persist their queue jobs."""
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
            },
        ))
    return jobs
