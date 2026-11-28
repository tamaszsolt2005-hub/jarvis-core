"""Trusted one-shot entrypoint for exactly one company-research queue claim.

Run only in a private backend environment with the required server secrets.
This module is inert on import and is intentionally not called by Streamlit.
"""
from __future__ import annotations

import json
import sys
from uuid import uuid4


def run_once() -> dict[str, object]:
    """Claim and execute at most one job; fail closed if runtime control is absent."""
    from company_research_config import (
        CompanyResearchRuntimeConfig,
        run_company_research_worker_with_config,
    )
    from jarvis_common import get_gemini_client, get_model_name, get_service_supabase

    config = CompanyResearchRuntimeConfig.from_env()
    model = get_model_name()
    config.validate_model(model)

    # The control row is readable only with the trusted backend client. Missing
    # or inaccessible control state must never be interpreted as "unpaused".
    db = get_service_supabase()
    control_response = (
        db.table("company_research_runtime_control")
        .select("paused")
        .eq("singleton", True)
        .limit(1)
        .execute()
    )
    control_rows = getattr(control_response, "data", None)
    if not isinstance(control_rows, list) or len(control_rows) != 1:
        raise RuntimeError("research_runtime_control_unavailable")
    if control_rows[0].get("paused") is not False:
        return {"status": "paused"}

    client = get_gemini_client()
    from company_research_job_repository import SupabaseCompanyResearchJobRepository

    repository = SupabaseCompanyResearchJobRepository(db)
    worker_id = f"jarvis-once-{uuid4().hex}"
    result = run_company_research_worker_with_config(
        repository,
        client=client,
        model=model,
        snapshot_db=db,
        worker_id=worker_id,
        config=config,
        lease_seconds=180,
        retry_delay_seconds=60,
        max_attempts=1,
    )
    # Never print provider output, company dossier content, or exception data
    # from this operational command.
    return {
        "status": str(result.get("status") or "unknown"),
        "operation_id": str(result.get("operation_id") or ""),
        "error_code": str(result.get("error_code") or ""),
    }


def main() -> int:
    try:
        result = run_once()
    except Exception as exc:
        print(json.dumps({
            "status": "error",
            "error_type": type(exc).__name__,
        }, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("status") in {"succeeded", "idle", "paused"} else 1


if __name__ == "__main__":
    sys.exit(main())
