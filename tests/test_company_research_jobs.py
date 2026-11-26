from datetime import datetime, timedelta, timezone

import pytest

from company_research_jobs import (
    claim_research_job,
    complete_research_job,
    create_research_job,
    fail_research_job,
    heartbeat_research_job,
    retry_backoff_seconds,
)

NOW = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)


def make_job(**kwargs):
    now = kwargs.pop("now", NOW)
    return create_research_job(
        operation_id="research:lead:123456",
        lead_id="lead-123",
        payload={"reason": "missing_dossier"},
        now=now,
        **kwargs,
    )


def test_create_job_is_queued_json_safe_and_does_not_mutate_payload():
    payload = {"filters": ["stale"]}
    job = create_research_job(
        operation_id="research:lead:123456", lead_id="lead-123",
        payload=payload, now=NOW,
    )
    payload["filters"].append("changed")
    assert job["status"] == "queued"
    assert job["attempt_count"] == 0
    assert job["payload"] == {"filters": ["stale"]}
    assert job["operation_id"] == "research:lead:123456"


@pytest.mark.parametrize("operation_id", ["", "short", "has spaces", "x" * 129])
def test_create_job_rejects_invalid_operation_id(operation_id):
    with pytest.raises(ValueError):
        create_research_job(
            operation_id=operation_id, lead_id="lead", payload={}, now=NOW
        )


def test_create_job_rejects_non_json_payload():
    with pytest.raises(ValueError):
        create_research_job(
            operation_id="research:lead:123456", lead_id="lead",
            payload={"bad": object()}, now=NOW,
        )


def test_claim_sets_lease_and_increments_attempt_once():
    job = make_job()
    claimed = claim_research_job(job, worker_id="worker-a", lease_seconds=30, now=NOW)
    assert claimed["status"] == "running"
    assert claimed["attempt_count"] == 1
    assert claimed["lease_owner"] == "worker-a"
    assert claim_research_job(claimed, worker_id="worker-b", now=NOW) is None


def test_expired_lease_can_be_reclaimed_by_another_worker():
    claimed = claim_research_job(make_job(), worker_id="worker-a", now=NOW)
    reclaimed = claim_research_job(
        claimed, worker_id="worker-b", now=NOW + timedelta(seconds=61)
    )
    assert reclaimed["lease_owner"] == "worker-b"
    assert reclaimed["attempt_count"] == 2


def test_heartbeat_requires_current_live_lease_owner():
    claimed = claim_research_job(make_job(), worker_id="worker-a", now=NOW)
    assert heartbeat_research_job(
        claimed, worker_id="worker-b", now=NOW
    ) is None
    renewed = heartbeat_research_job(
        claimed, worker_id="worker-a", lease_seconds=120, now=NOW
    )
    assert datetime.fromisoformat(renewed["lease_expires_at"]) == NOW + timedelta(seconds=120)


def test_completion_requires_live_lease_and_is_terminal():
    claimed = claim_research_job(make_job(), worker_id="worker-a", now=NOW)
    done = complete_research_job(
        claimed, worker_id="worker-a", result={"snapshot_id": "snap-1"}, now=NOW
    )
    assert done["status"] == "succeeded"
    assert done["result"]["snapshot_id"] == "snap-1"
    assert done["lease_owner"] is None
    assert claim_research_job(done, worker_id="worker-b", now=NOW) is None


def test_retryable_failure_waits_then_can_be_claimed():
    claimed = claim_research_job(make_job(), worker_id="worker-a", now=NOW)
    waiting = fail_research_job(
        claimed, worker_id="worker-a", error_code="upstream_503",
        error_message="Temporary service issue", retryable=True,
        retry_delay_seconds=30, max_attempts=3, now=NOW,
    )
    assert waiting["status"] == "retry_wait"
    assert claim_research_job(waiting, worker_id="worker-b", now=NOW) is None
    retried = claim_research_job(
        waiting, worker_id="worker-b", now=NOW + timedelta(seconds=31)
    )
    assert retried["attempt_count"] == 2


def test_retry_exhaustion_and_non_retryable_failure_go_to_dead_letter():
    claimed = claim_research_job(make_job(), worker_id="worker-a", now=NOW)
    exhausted = {**claimed, "attempt_count": 3}
    dead = fail_research_job(
        exhausted, worker_id="worker-a", error_code="timeout",
        error_message="Timed out", retryable=True, max_attempts=3, now=NOW,
    )
    assert dead["status"] == "dead_letter"
    claimed_again = claim_research_job(make_job(), worker_id="worker-a", now=NOW)
    rejected = fail_research_job(
        claimed_again, worker_id="worker-a", error_code="invalid_input",
        error_message="Bad request", retryable=False, now=NOW,
    )
    assert rejected["status"] == "dead_letter"


def test_stale_worker_cannot_complete_after_lease_expiry():
    claimed = claim_research_job(make_job(), worker_id="worker-a", now=NOW)
    assert complete_research_job(
        claimed, worker_id="worker-a", now=NOW + timedelta(seconds=61)
    ) is None


def test_naive_clock_and_invalid_limits_are_rejected():
    with pytest.raises(ValueError):
        make_job(now=datetime(2026, 11, 26))
    with pytest.raises(ValueError):
        claim_research_job(make_job(), worker_id="worker-a", lease_seconds=0, now=NOW)


@pytest.mark.parametrize(
    ("attempt", "expected"),
    [(1, 60), (2, 120), (3, 240), (4, 480), (20, 3600)],
)
def test_retry_backoff_is_exponential_and_capped(attempt, expected):
    assert retry_backoff_seconds(attempt, base_delay_seconds=60, max_delay_seconds=3600) == expected


def test_retry_backoff_rejects_invalid_limits():
    for kwargs in (
        {"attempt_count": 0},
        {"attempt_count": True},
        {"attempt_count": 1, "base_delay_seconds": 0},
        {"attempt_count": 1, "base_delay_seconds": 60, "max_delay_seconds": 30},
    ):
        with pytest.raises(ValueError):
            retry_backoff_seconds(**kwargs)
