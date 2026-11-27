"""Explicit, authenticated enqueue path for a single existing lead research refresh.

This module never starts a worker or calls an external provider. Privileged
storage is resolved only after a fresh Supabase Auth + RBAC authorization.
"""
from __future__ import annotations

from typing import Any, Callable

from company_research_config import CompanyResearchRuntimeConfig
from company_research_job_repository import SupabaseCompanyResearchJobRepository
from company_research_refresh_queue import enqueue_company_research_refreshes


class LeadResearchRequestError(RuntimeError):
    """Raised when a single-lead research request cannot be safely queued."""


def enqueue_single_lead_research(
    lead_id: str,
    *,
    auth_session: dict[str, str] | None,
    authorize_user: Callable[[dict[str, str] | None], Any],
    service_client_factory: Callable[[], Any],
) -> dict[str, Any]:
    """Authorize admin/operator, then enqueue one existing lead with DB quotas.

    The caller must provide an authorization callback that revalidates the
    current Auth session and the research.manage permission. The service client
    is deliberately created only after that callback succeeds.
    """
    normalized_id = str(lead_id or "").strip()
    if not normalized_id or len(normalized_id) > 64:
        raise LeadResearchRequestError("invalid_lead_id")

    authorization = authorize_user(auth_session)
    if authorization is None:
        raise PermissionError("research_manage_permission_required")

    # Pricing, token limits, retry policy and quotas are mandatory deployment
    # configuration. Missing settings fail closed before any job is created.
    config = CompanyResearchRuntimeConfig.from_env()
    db = service_client_factory()

    lead_response = (
        db.table("leads")
        .select("*")
        .eq("id", normalized_id)
        .limit(1)
        .execute()
    )
    lead_rows = getattr(lead_response, "data", None)
    if not isinstance(lead_rows, list) or len(lead_rows) != 1 or not isinstance(lead_rows[0], dict):
        raise LeadResearchRequestError("lead_not_found_or_unavailable")
    lead = lead_rows[0]

    snapshot_response = (
        db.table("company_research_snapshots")
        .select("lead_id,researched_at,dossier")
        .eq("lead_id", normalized_id)
        .order("researched_at", desc=True)
        .limit(1)
        .execute()
    )
    snapshot_rows = getattr(snapshot_response, "data", None) or []
    latest_dossiers: dict[str, Any] = {}
    if isinstance(snapshot_rows, list) and snapshot_rows and isinstance(snapshot_rows[0], dict):
        latest_dossiers[normalized_id] = snapshot_rows[0]

    repository = SupabaseCompanyResearchJobRepository(db)
    jobs = enqueue_company_research_refreshes(
        repository,
        [lead],
        latest_dossiers,
        limits=config.limits,
        input_price_microusd_per_million_tokens=config.input_price_microusd_per_million_tokens,
        output_price_microusd_per_million_tokens=config.output_price_microusd_per_million_tokens,
        search_price_microusd_per_thousand_queries=config.search_price_microusd_per_thousand_queries,
        max_search_queries_per_attempt=config.max_search_queries_per_attempt,
        max_input_tokens_per_attempt=config.max_input_tokens_per_attempt,
        max_output_tokens_per_attempt=config.max_output_tokens_per_attempt,
        max_attempts=config.max_attempts,
        max_age_days=config.max_age_days,
        limit=1,
    )
    if not jobs:
        return {
            "status": "not_eligible",
            "lead_id": normalized_id,
            "reason": "lead_is_not_eligible_or_dossier_is_fresh_or_website_is_invalid",
        }
    job = jobs[0]
    return {
        "status": str(job.get("status") or "queued"),
        "lead_id": normalized_id,
        "operation_id": str(job.get("operation_id") or ""),
        "created_at": str(job.get("created_at") or ""),
        "reason": str((job.get("payload") or {}).get("reason") or ""),
    }
