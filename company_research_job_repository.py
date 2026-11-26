"""Repository contracts and Supabase adapter for durable company research jobs.

The adapter only uses an explicitly injected Supabase client. All state transitions
that require concurrency safety are delegated to database RPCs.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from company_research_jobs import create_research_job

TABLE_NAME = "company_research_jobs"
RPC_CREATE = "company_research_job_create"
RPC_CLAIM = "company_research_job_claim"
RPC_HEARTBEAT = "company_research_job_heartbeat"
RPC_COMPLETE = "company_research_job_complete"
RPC_FAIL = "company_research_job_fail"
RPC_AUDIT_LIST = "company_research_job_audit_list"


class CompanyResearchJobRepositoryError(RuntimeError):
    """Raised when durable job storage returns an invalid or failed response."""


class CompanyResearchBudgetExceeded(CompanyResearchJobRepositoryError):
    """Raised when the atomic daily cost reservation would exceed its ceiling."""


class CompanyResearchAdmissionRejected(CompanyResearchJobRepositoryError):
    """Raised when an atomic database-backed admission quota is exhausted."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


@runtime_checkable
class CompanyResearchJobRepository(Protocol):
    def create(self, *, operation_id: str, lead_id: str, payload: dict[str, Any], estimated_cost_microusd: int = 0, daily_budget_microusd: int | None = None, max_jobs_per_hour: int | None = None, max_jobs_per_domain_per_day: int | None = None) -> dict[str, Any]: ...
    def claim(self, *, worker_id: str, lease_seconds: int = 60, max_concurrent_jobs: int = 3) -> dict[str, Any] | None: ...
    def heartbeat(self, *, operation_id: str, worker_id: str, lease_seconds: int = 60) -> dict[str, Any] | None: ...
    def complete(self, *, operation_id: str, worker_id: str, result: dict[str, Any] | None = None) -> dict[str, Any] | None: ...
    def list_audit(self, *, operation_id: str, limit: int = 100) -> list[dict[str, Any]]: ...
    def fail(
        self, *, operation_id: str, worker_id: str, error_code: str,
        error_message: str, retryable: bool, retry_delay_seconds: int = 60,
        max_attempts: int = 3,
    ) -> dict[str, Any] | None: ...


def _one_row(response: Any, *, operation: str, allow_none: bool = False) -> dict[str, Any] | None:
    data = getattr(response, "data", None)
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        if not data and allow_none:
            return None
        if len(data) == 1 and isinstance(data[0], dict):
            return data[0]
    if data is None and allow_none:
        return None
    raise CompanyResearchJobRepositoryError(
        f"{operation} RPC returned an unexpected response shape."
    )


def _operation_id(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("operation_id is required")
    return value.strip()


class SupabaseCompanyResearchJobRepository:
    """Durable repository backed by explicitly injected Supabase client.

    The client is expected to use a backend credential. No client or secret is
    created/read by this module. Atomicity is provided by the SQL RPC functions,
    never by a Python read-then-write sequence.
    """

    def __init__(self, client: Any):
        if client is None or not callable(getattr(client, "rpc", None)):
            raise ValueError("An injected Supabase client with rpc() is required.")
        self._client = client

    def _rpc(self, name: str, params: dict[str, Any], *, allow_none: bool = False):
        try:
            response = self._client.rpc(name, params).execute()
        except Exception as exc:
            # Expose only this fixed, non-sensitive database error marker.
            message = str(exc)
            if "research_daily_budget_exceeded" in message:
                raise CompanyResearchBudgetExceeded("Daily research budget exceeded.") from exc
            if "research_hourly_limit_exceeded" in message:
                raise CompanyResearchAdmissionRejected("global_hourly_limit") from exc
            if "research_domain_daily_limit_exceeded" in message:
                raise CompanyResearchAdmissionRejected("domain_daily_limit") from exc
            raise CompanyResearchJobRepositoryError(f"{name} RPC failed.") from exc
        return _one_row(response, operation=name, allow_none=allow_none)

    def create(self, *, operation_id: str, lead_id: str, payload: dict[str, Any], estimated_cost_microusd: int = 0, daily_budget_microusd: int | None = None, max_jobs_per_hour: int | None = None, max_jobs_per_domain_per_day: int | None = None) -> dict[str, Any]:
        # Reuse the canonical validation and serialization rules.
        job = create_research_job(operation_id=operation_id, lead_id=lead_id, payload=payload)
        try:
            job["lead_id"] = str(UUID(job["lead_id"]))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("lead_id must be a UUID for durable storage") from exc
        if isinstance(estimated_cost_microusd, bool) or not isinstance(estimated_cost_microusd, int) or estimated_cost_microusd < 0:
            raise ValueError("estimated_cost_microusd must be a non-negative integer")
        if daily_budget_microusd is not None and (
            isinstance(daily_budget_microusd, bool)
            or not isinstance(daily_budget_microusd, int)
            or daily_budget_microusd < 1
        ):
            raise ValueError("daily_budget_microusd must be a positive integer or None")
        for value, name in (
            (max_jobs_per_hour, "max_jobs_per_hour"),
            (max_jobs_per_domain_per_day, "max_jobs_per_domain_per_day"),
        ):
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 1
            ):
                raise ValueError(f"{name} must be a positive integer or None")
        row = self._rpc(RPC_CREATE, {
            "p_job": job,
            "p_estimated_cost_microusd": estimated_cost_microusd,
            "p_daily_budget_microusd": daily_budget_microusd,
            "p_max_jobs_per_hour": max_jobs_per_hour,
            "p_max_jobs_per_domain_per_day": max_jobs_per_domain_per_day,
        })
        if row.get("operation_id") != job["operation_id"]:
            raise CompanyResearchJobRepositoryError("Create RPC returned a different operation_id.")
        # ON CONFLICT(operation_id) returns the existing row. An idempotency
        # key reused for different immutable input must be surfaced, not silently
        # treated as a successful enqueue of the caller's requested job.
        expected = {
            "job_type": job["job_type"],
            "lead_id": job["lead_id"],
            "payload": job["payload"],
        }
        for field, expected_value in expected.items():
            if row.get(field) != expected_value:
                raise CompanyResearchJobRepositoryError(
                    f"Create RPC idempotency conflict: existing {field} differs."
                )
        return row

    def claim(self, *, worker_id: str, lease_seconds: int = 60, max_concurrent_jobs: int = 3) -> dict[str, Any] | None:
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError("worker_id is required")
        if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int) or lease_seconds < 1:
            raise ValueError("lease_seconds must be a positive integer")
        if isinstance(max_concurrent_jobs, bool) or not isinstance(max_concurrent_jobs, int) or max_concurrent_jobs < 1:
            raise ValueError("max_concurrent_jobs must be a positive integer")
        return self._rpc(
            RPC_CLAIM,
            {"p_worker_id": worker_id.strip(), "p_lease_seconds": lease_seconds,
             "p_max_concurrent_jobs": max_concurrent_jobs},
            allow_none=True,
        )

    def heartbeat(self, *, operation_id: str, worker_id: str, lease_seconds: int = 60) -> dict[str, Any] | None:
        operation_id = _operation_id(operation_id)
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError("worker_id is required")
        if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int) or lease_seconds < 1:
            raise ValueError("lease_seconds must be a positive integer")
        return self._rpc(
            RPC_HEARTBEAT,
            {"p_operation_id": operation_id, "p_worker_id": worker_id.strip(),
             "p_lease_seconds": lease_seconds},
            allow_none=True,
        )

    def complete(
        self, *, operation_id: str, worker_id: str, result: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        operation_id = _operation_id(operation_id)
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError("worker_id is required")
        if result is not None and not isinstance(result, dict):
            raise ValueError("result must be an object or None")
        return self._rpc(
            RPC_COMPLETE,
            {"p_operation_id": operation_id, "p_worker_id": worker_id.strip(),
             "p_result": result or {}},
            allow_none=True,
        )

    def list_audit(self, *, operation_id: str, limit: int = 100) -> list[dict[str, Any]]:
        operation_id = _operation_id(operation_id)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError("limit must be an integer between 1 and 1000")
        try:
            response = self._client.rpc(
                RPC_AUDIT_LIST,
                {"p_operation_id": operation_id, "p_limit": limit},
            ).execute()
        except Exception as exc:
            raise CompanyResearchJobRepositoryError("Audit list RPC failed.") from exc
        data = getattr(response, "data", None)
        if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
            raise CompanyResearchJobRepositoryError("Audit list RPC returned an unexpected response shape.")
        return data

    def fail(
        self, *, operation_id: str, worker_id: str, error_code: str,
        error_message: str, retryable: bool, retry_delay_seconds: int = 60,
        max_attempts: int = 3,
    ) -> dict[str, Any] | None:
        operation_id = _operation_id(operation_id)
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError("worker_id is required")
        if not isinstance(retryable, bool):
            raise ValueError("retryable must be boolean")
        if any(isinstance(v, bool) or not isinstance(v, int) or v < 1
               for v in (retry_delay_seconds, max_attempts)):
            raise ValueError("retry_delay_seconds and max_attempts must be positive integers")
        return self._rpc(
            RPC_FAIL,
            {"p_operation_id": operation_id, "p_worker_id": worker_id.strip(),
             "p_error_code": str(error_code or "unknown")[:80],
             "p_error_message": str(error_message or "")[:1000],
             "p_retryable": retryable, "p_retry_delay_seconds": retry_delay_seconds,
             "p_max_attempts": max_attempts},
            allow_none=True,
        )
