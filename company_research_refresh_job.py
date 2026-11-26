"""Scheduled entry point for bounded company dossier refreshes.

The job only researches public company information and stores dossier snapshots.
It never sends email, changes contact permission, or starts outreach.
"""
from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from company_research_config import (
    CompanyResearchRuntimeConfig,
    enqueue_company_research_refreshes_with_config,
    run_company_research_worker_with_config,
)


def _response_rows(response: Any, *, operation: str) -> list[dict[str, Any]]:
    rows = getattr(response, "data", None)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise RuntimeError(f"Unexpected database response while {operation}.")
    return rows


def load_company_research_refresh_inputs(
    db: Any,
    *,
    lead_page_size: int = 500,
    snapshot_page_size: int = 500,
    lead_chunk_size: int = 100,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Read leads and latest snapshots using bounded, deterministic pagination."""
    for name, value in (
        ("lead_page_size", lead_page_size),
        ("snapshot_page_size", snapshot_page_size),
        ("lead_chunk_size", lead_chunk_size),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 1000:
            raise ValueError(f"{name} must be an integer between 1 and 1000")

    leads: list[dict[str, Any]] = []
    offset = 0
    while True:
        response = (
            db.table("leads")
            .select("id,company_name,website,status,opted_out,reply_category,last_inbound_message_id,follow_up_count,first_sent_at,followed_up_at,last_message_id")
            .order("id")
            .range(offset, offset + lead_page_size - 1)
            .execute()
        )
        page = _response_rows(response, operation="loading leads")
        leads.extend(page)
        if len(page) < lead_page_size:
            break
        offset += lead_page_size

    latest: dict[str, dict[str, Any]] = {}
    lead_ids = [str(row.get("id")) for row in leads if row.get("id")]
    for start in range(0, len(lead_ids), lead_chunk_size):
        chunk = lead_ids[start:start + lead_chunk_size]
        offset = 0
        while True:
            response = (
                db.table("company_research_snapshots")
                .select("snapshot_id,lead_id,researched_at,dossier")
                .in_("lead_id", chunk)
                .order("researched_at", desc=True)
                .order("snapshot_id", desc=True)
                .range(offset, offset + snapshot_page_size - 1)
                .execute()
            )
            page = _response_rows(response, operation="loading company research snapshots")
            for row in page:
                lead_id = str(row.get("lead_id") or "")
                if lead_id and lead_id not in latest:
                    latest[lead_id] = row
            if len(page) < snapshot_page_size:
                break
            offset += snapshot_page_size
    return leads, latest


def run_company_research_refresh_cycle(
    db: Any,
    *,
    client: Any,
    model: str,
    config: CompanyResearchRuntimeConfig,
    worker_id: str | None = None,
) -> dict[str, Any]:
    """Enqueue stale leads, then process at most batch_limit jobs sequentially."""
    config.validate_model(model)
    models = getattr(client, "models", None)
    if not callable(getattr(models, "count_tokens", None)) or not callable(getattr(models, "generate_content", None)):
        raise ValueError("Gemini client must support token counting and content generation")
    leads, latest_dossiers = load_company_research_refresh_inputs(db)
    enqueued = enqueue_company_research_refreshes_with_config(
        _repository(db), leads, latest_dossiers, config=config
    )
    worker_identity = worker_id or f"company-research-{uuid4()}"
    outcomes: dict[str, int] = {}
    processed = 0
    for _ in range(config.batch_limit):
        result = run_company_research_worker_with_config(
            _repository(db),
            client=client,
            model=model,
            snapshot_db=db,
            worker_id=worker_identity,
            config=config,
        )
        status = str(result.get("status") or "unknown")
        if status == "idle":
            break
        outcomes[status] = outcomes.get(status, 0) + 1
        processed += 1
    return {
        "scanned_leads": len(leads),
        "queued": len(enqueued),
        "processed": processed,
        "worker_outcomes": outcomes,
        "contact_permission": "unchanged",
        "outreach": "disabled",
    }


def _repository(db: Any):
    from company_research_job_repository import SupabaseCompanyResearchJobRepository

    return SupabaseCompanyResearchJobRepository(db)


def main() -> None:
    from jarvis_common import get_gemini_client, get_model_name, get_service_supabase

    config = CompanyResearchRuntimeConfig.from_env()
    model = get_model_name()
    config.validate_model(model)
    db = get_service_supabase()
    result = run_company_research_refresh_cycle(
        db,
        client=get_gemini_client(),
        model=model,
        config=config,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
