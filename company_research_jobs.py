"""Database-independent, lease-aware lifecycle primitives for background jobs.

These pure functions define the worker contract. They do not persist jobs,
schedule work, call external APIs, or perform business side effects.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import re
from typing import Any

JOB_STATES = frozenset({"queued", "running", "retry_wait", "succeeded", "dead_letter"})
_TERMINAL_STATES = frozenset({"succeeded", "dead_letter"})
_OPERATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")


def _now(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return result.astimezone(timezone.utc)


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _owned_active_job(job: dict[str, Any], worker_id: str, now: datetime) -> bool:
    if job.get("status") != "running" or job.get("lease_owner") != worker_id:
        return False
    expiry = job.get("lease_expires_at")
    if not isinstance(expiry, str):
        return False
    try:
        parsed = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.astimezone(timezone.utc) > now



def retry_backoff_seconds(
    attempt_count: int, *, base_delay_seconds: int = 60,
    max_delay_seconds: int = 3600,
) -> int:
    """Return capped exponential retry delay for a 1-based attempt count."""
    attempt_count = _positive_int(attempt_count, "attempt_count")
    base_delay_seconds = _positive_int(base_delay_seconds, "base_delay_seconds")
    max_delay_seconds = _positive_int(max_delay_seconds, "max_delay_seconds")
    if max_delay_seconds < base_delay_seconds:
        raise ValueError("max_delay_seconds must be at least base_delay_seconds")
    # Compare before exponentiation to avoid constructing huge integers.
    exponent = attempt_count - 1
    max_exponent = (max_delay_seconds // base_delay_seconds).bit_length()
    if exponent >= max_exponent:
        return max_delay_seconds
    return min(base_delay_seconds * (2 ** exponent), max_delay_seconds)


def create_research_job(
    *, operation_id: str, lead_id: str, payload: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a new queued job; repositories must enforce unique operation_id."""
    if not isinstance(operation_id, str) or not _OPERATION_ID.fullmatch(operation_id):
        raise ValueError("operation_id must be a stable 8-128 character identifier")
    if not isinstance(lead_id, str) or not lead_id.strip():
        raise ValueError("lead_id is required")
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    copied_payload = deepcopy(payload)
    try:
        json.dumps(copied_payload, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("payload must be JSON-serializable") from exc
    timestamp = _now(now).isoformat()
    return {
        "operation_id": operation_id,
        "job_type": "company_research_refresh",
        "lead_id": lead_id.strip(),
        "payload": copied_payload,
        "status": "queued",
        "attempt_count": 0,
        "max_attempts": 3,
        "created_at": timestamp,
        "updated_at": timestamp,
        "available_at": timestamp,
        "lease_owner": None,
        "lease_expires_at": None,
        "heartbeat_at": None,
        "last_error_code": None,
        "last_error_message": None,
        "result": None,
    }


def claim_research_job(
    job: dict[str, Any], *, worker_id: str, lease_seconds: int = 60,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Claim a queued/due retry job or reclaim an expired lease."""
    if not isinstance(job, dict):
        raise ValueError("job must be an object")
    if not isinstance(worker_id, str) or not worker_id.strip():
        raise ValueError("worker_id is required")
    lease_seconds = _positive_int(lease_seconds, "lease_seconds")
    current = _now(now)
    status = job.get("status")
    if status in _TERMINAL_STATES or status not in JOB_STATES:
        return None
    if status == "retry_wait":
        available = datetime.fromisoformat(str(job.get("available_at", "")).replace("Z", "+00:00"))
        if available.tzinfo is None or available.astimezone(timezone.utc) > current:
            return None
    if status == "running":
        expiry_raw = job.get("lease_expires_at")
        try:
            expiry = datetime.fromisoformat(str(expiry_raw).replace("Z", "+00:00"))
        except ValueError:
            return None
        if expiry.tzinfo is None or expiry.astimezone(timezone.utc) > current:
            return None
    if status == "queued":
        available = datetime.fromisoformat(str(job.get("available_at", "")).replace("Z", "+00:00"))
        if available.tzinfo is None or available.astimezone(timezone.utc) > current:
            return None
    claimed = deepcopy(job)
    claimed["status"] = "running"
    claimed["attempt_count"] = int(job.get("attempt_count", 0)) + 1
    claimed["lease_owner"] = worker_id.strip()
    claimed["lease_expires_at"] = (current + timedelta(seconds=lease_seconds)).isoformat()
    claimed["heartbeat_at"] = current.isoformat()
    claimed["updated_at"] = current.isoformat()
    return claimed


def heartbeat_research_job(
    job: dict[str, Any], *, worker_id: str, lease_seconds: int = 60,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Extend a live lease only for its current owner."""
    lease_seconds = _positive_int(lease_seconds, "lease_seconds")
    current = _now(now)
    if not _owned_active_job(job, worker_id, current):
        return None
    updated = deepcopy(job)
    updated["lease_expires_at"] = (current + timedelta(seconds=lease_seconds)).isoformat()
    updated["heartbeat_at"] = current.isoformat()
    updated["updated_at"] = current.isoformat()
    return updated


def complete_research_job(
    job: dict[str, Any], *, worker_id: str, result: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Mark a job successful only while the caller owns a live lease."""
    current = _now(now)
    if not _owned_active_job(job, worker_id, current):
        return None
    completed = deepcopy(job)
    completed.update({
        "status": "succeeded", "result": deepcopy(result or {}),
        "lease_owner": None, "lease_expires_at": None,
        "updated_at": current.isoformat(),
    })
    return completed


def fail_research_job(
    job: dict[str, Any], *, worker_id: str, error_code: str,
    error_message: str, retryable: bool, retry_delay_seconds: int = 60,
    max_attempts: int = 3, now: datetime | None = None,
) -> dict[str, Any] | None:
    """Schedule a bounded retry or move the job to dead-letter."""
    max_attempts = _positive_int(max_attempts, "max_attempts")
    retry_delay_seconds = _positive_int(retry_delay_seconds, "retry_delay_seconds")
    if not isinstance(retryable, bool):
        raise ValueError("retryable must be boolean")
    current = _now(now)
    if not _owned_active_job(job, worker_id, current):
        return None
    failed = deepcopy(job)
    attempts = int(job.get("attempt_count", 0))
    should_retry = retryable and attempts < min(max_attempts, int(job.get("max_attempts", max_attempts)))
    failed.update({
        "status": "retry_wait" if should_retry else "dead_letter",
        "available_at": (current + timedelta(seconds=retry_delay_seconds)).isoformat(),
        "lease_owner": None, "lease_expires_at": None,
        "last_error_code": str(error_code or "unknown")[:80],
        "last_error_message": str(error_message or "")[:1000],
        "updated_at": current.isoformat(),
    })
    return failed
