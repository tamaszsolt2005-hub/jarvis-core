"""Single-job worker orchestration for prepared company research jobs.

Execution is dependency-injected. This module has no Gemini/API integration,
scheduler, database client construction, logging of exception text, or outbound
communication. A caller supplies the handler and repository.
"""
from __future__ import annotations

from typing import Any, Callable

from company_research_job_repository import CompanyResearchJobRepository
from company_research_jobs import retry_backoff_seconds

ResearchJobHandler = Callable[[dict[str, Any]], dict[str, Any]]


def run_one_company_research_job(
    repository: CompanyResearchJobRepository,
    *,
    worker_id: str,
    handler: ResearchJobHandler,
    lease_seconds: int = 120,
    retry_delay_seconds: int = 60,
    max_attempts: int = 3,
    max_retry_delay_seconds: int = 3600,
) -> dict[str, Any]:
    """Claim and process at most one prepared job.

    Handler exceptions are reduced to a safe error code and generic message;
    exception text is deliberately not copied into durable job records because
    it may contain credentials, personal data, or provider response fragments.
    """
    if not callable(handler):
        raise ValueError("handler must be callable")
    if not isinstance(worker_id, str) or not worker_id.strip():
        raise ValueError("worker_id is required")
    if isinstance(retry_delay_seconds, bool) or not isinstance(retry_delay_seconds, int) or retry_delay_seconds < 1:
        raise ValueError("retry_delay_seconds must be a positive integer")
    if isinstance(max_retry_delay_seconds, bool) or not isinstance(max_retry_delay_seconds, int) or max_retry_delay_seconds < retry_delay_seconds:
        raise ValueError("max_retry_delay_seconds must be an integer at least retry_delay_seconds")

    job = repository.claim(worker_id=worker_id.strip(), lease_seconds=lease_seconds)
    if job is None:
        return {"status": "idle"}

    operation_id = job.get("operation_id")
    payload = job.get("payload")
    if not isinstance(operation_id, str) or not operation_id.strip():
        return {"status": "invalid_job", "error_code": "missing_operation_id"}
    if not isinstance(payload, dict):
        failed = repository.fail(
            operation_id=operation_id,
            worker_id=worker_id.strip(),
            error_code="invalid_job_payload",
            error_message="Stored job is missing its operation identifier or object payload.",
            retryable=False,
            retry_delay_seconds=retry_delay_seconds,
            max_attempts=max_attempts,
        )
        return {"status": "failed" if failed else "lease_lost", "operation_id": operation_id}

    try:
        result = handler(payload)
        if not isinstance(result, dict):
            raise TypeError("handler_result_must_be_object")
    except Exception as exc:
        error_code = getattr(exc, "code", None)
        if not isinstance(error_code, str) or not error_code.strip():
            error_code = type(exc).__name__.casefold()[:80] or "handler_error"
        retryable = getattr(exc, "retryable", not isinstance(exc, (TypeError, ValueError)))
        if not isinstance(retryable, bool):
            retryable = False
        try:
            attempt_count = int(job.get("attempt_count", 1))
        except (TypeError, ValueError, OverflowError):
            attempt_count = 1
        delay = retry_backoff_seconds(
            max(1, attempt_count), base_delay_seconds=retry_delay_seconds,
            max_delay_seconds=max_retry_delay_seconds,
        )
        failed = repository.fail(
            operation_id=operation_id,
            worker_id=worker_id.strip(),
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
        worker_id=worker_id.strip(),
        result=result,
    )
    if completed is None:
        return {"status": "lease_lost", "operation_id": operation_id}
    return {"status": "succeeded", "operation_id": operation_id, "result": completed.get("result", result)}
