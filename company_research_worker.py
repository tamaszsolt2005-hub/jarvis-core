"""Single-job worker orchestration for prepared company research jobs.

Execution is dependency-injected. This module has no Gemini/API integration,
scheduler, database client construction, or outbound communication.
"""
from __future__ import annotations

from copy import deepcopy
from inspect import Parameter, signature
import json
import re
from typing import Any, Callable

from company_research_job_repository import CompanyResearchJobRepository
from company_research_jobs import retry_backoff_seconds

ResearchJobHandler = Callable[..., dict[str, Any]]


def run_one_company_research_job(
    repository: CompanyResearchJobRepository,
    *,
    worker_id: str,
    handler: ResearchJobHandler,
    lease_seconds: int = 120,
    max_concurrent_jobs: int = 3,
    retry_delay_seconds: int = 60,
    max_attempts: int = 3,
    max_retry_delay_seconds: int = 3600,
    max_result_bytes: int = 262144,
    actual_cost_extractor: Callable[[dict[str, Any]], int] | None = None,
) -> dict[str, Any]:
    """Claim and process at most one prepared job."""
    if not callable(handler):
        raise ValueError("handler must be callable")
    if actual_cost_extractor is not None and not callable(actual_cost_extractor):
        raise ValueError("actual_cost_extractor must be callable or None")
    if not isinstance(worker_id, str) or not worker_id.strip():
        raise ValueError("worker_id is required")
    if isinstance(retry_delay_seconds, bool) or not isinstance(retry_delay_seconds, int) or retry_delay_seconds < 1:
        raise ValueError("retry_delay_seconds must be a positive integer")
    if isinstance(max_retry_delay_seconds, bool) or not isinstance(max_retry_delay_seconds, int) or max_retry_delay_seconds < retry_delay_seconds:
        raise ValueError("max_retry_delay_seconds must be an integer at least retry_delay_seconds")
    if isinstance(max_result_bytes, bool) or not isinstance(max_result_bytes, int) or max_result_bytes < 1:
        raise ValueError("max_result_bytes must be a positive integer")

    if isinstance(max_concurrent_jobs, bool) or not isinstance(max_concurrent_jobs, int) or max_concurrent_jobs < 1:
        raise ValueError("max_concurrent_jobs must be a positive integer")

    worker_id = worker_id.strip()
    job = repository.claim(
        worker_id=worker_id,
        lease_seconds=lease_seconds,
        max_concurrent_jobs=max_concurrent_jobs,
    )
    if job is None:
        return {"status": "idle"}
    if not isinstance(job, dict):
        return {"status": "invalid_job", "error_code": "invalid_claim_response"}

    operation_id = job.get("operation_id")
    if not isinstance(operation_id, str) or not operation_id.strip():
        return {"status": "invalid_job", "error_code": "missing_operation_id"}
    payload = job.get("payload")
    if not isinstance(payload, dict):
        failed = repository.fail(
            operation_id=operation_id,
            worker_id=worker_id,
            error_code="invalid_job_payload",
            error_message="Stored job payload is not an object.",
            retryable=False,
            retry_delay_seconds=retry_delay_seconds,
            max_attempts=max_attempts,
        )
        return {"status": "failed" if failed else "lease_lost", "operation_id": operation_id}

    def heartbeat() -> bool:
        """Renew this job's lease at an explicit handler checkpoint."""
        renewed = repository.heartbeat(
            operation_id=operation_id,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
        )
        return renewed is not None

    try:
        try:
            parameters = signature(handler).parameters.values()
            accepts_heartbeat = any(
                parameter.kind == Parameter.VAR_POSITIONAL for parameter in parameters
            ) or len([
                parameter for parameter in parameters
                if parameter.kind in (Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD)
            ]) >= 2
        except (TypeError, ValueError):
            accepts_heartbeat = False

        handler_payload = deepcopy(payload)
        result = handler(handler_payload, heartbeat) if accepts_heartbeat else handler(handler_payload)
        if not isinstance(result, dict):
            raise TypeError("handler_result_must_be_object")
        try:
            serialized_result = json.dumps(
                result, ensure_ascii=False, allow_nan=False, separators=(",", ":")
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("handler_result_must_be_json_serializable") from exc
        if len(serialized_result.encode("utf-8")) > max_result_bytes:
            raise ValueError("handler_result_exceeds_size_limit")
        result = json.loads(serialized_result)
        actual_cost_microusd = (
            actual_cost_extractor(result) if actual_cost_extractor is not None else None
        )
        if actual_cost_microusd is not None and (
            isinstance(actual_cost_microusd, bool)
            or not isinstance(actual_cost_microusd, int)
            or actual_cost_microusd < 0
        ):
            raise ValueError("actual_cost_extractor_must_return_non_negative_integer")
    except Exception as exc:
        error_code = getattr(exc, "code", None)
        if not isinstance(error_code, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", error_code):
            error_code = re.sub(r"[^a-z0-9_.-]", "_", type(exc).__name__.casefold())[:80]
            error_code = error_code or "handler_error"
        retryable = getattr(exc, "retryable", not isinstance(exc, (TypeError, ValueError)))
        if not isinstance(retryable, bool):
            retryable = False
        attempt_count = job.get("attempt_count", 1)
        if isinstance(attempt_count, bool) or not isinstance(attempt_count, int) or attempt_count < 1:
            attempt_count = 1
        delay = retry_backoff_seconds(
            attempt_count,
            base_delay_seconds=retry_delay_seconds,
            max_delay_seconds=max_retry_delay_seconds,
        )
        failed = repository.fail(
            operation_id=operation_id,
            worker_id=worker_id,
            error_code=error_code,
            error_message="Research job handler failed; sensitive exception details were not persisted.",
            retryable=retryable,
            retry_delay_seconds=delay,
            max_attempts=max_attempts,
        )
        return {
            "status": "retry_scheduled" if failed and failed.get("status") == "retry_wait"
                      else "dead_letter" if failed else "lease_lost",
            "operation_id": operation_id,
            "error_code": error_code,
        }

    completed = repository.complete(
        operation_id=operation_id,
        worker_id=worker_id,
        result=result,
        actual_cost_microusd=actual_cost_microusd,
    )
    if completed is None:
        return {"status": "lease_lost", "operation_id": operation_id}
    if not isinstance(completed, dict):
        return {"status": "invalid_repository_response", "operation_id": operation_id}
    return {
        "status": "succeeded",
        "operation_id": operation_id,
        "result": completed.get("result", result),
    }
