from copy import deepcopy

from company_research_worker import run_one_company_research_job


class FakeRepository:
    def __init__(self, job=None, complete_result=None, fail_result=None, lose_lease=False):
        self.job = deepcopy(job)
        self.complete_result = complete_result
        self.fail_result = fail_result
        self.lose_lease = lose_lease
        self.calls = []

    def claim(self, *, worker_id, lease_seconds=60):
        self.calls.append(("claim", worker_id, lease_seconds))
        job, self.job = self.job, None
        return deepcopy(job)

    def complete(self, *, operation_id, worker_id, result=None):
        self.calls.append(("complete", operation_id, worker_id, deepcopy(result)))
        if self.lose_lease:
            return None
        return deepcopy(self.complete_result if self.complete_result is not None else {
            "operation_id": operation_id, "status": "succeeded", "result": result,
        })

    def fail(self, *, operation_id, worker_id, error_code, error_message,
             retryable, retry_delay_seconds=60, max_attempts=3):
        self.calls.append(("fail", operation_id, worker_id, error_code, error_message, retryable))
        return deepcopy(self.fail_result if self.fail_result is not None else {
            "operation_id": operation_id,
            "status": "retry_wait" if retryable else "dead_letter",
        })


def sample_job(payload=None):
    return {
        "operation_id": "research:lead:123456",
        "payload": payload if payload is not None else {"lead_id": "lead-1"},
        "status": "running",
    }


def test_worker_claims_at_most_one_job_and_completes_handler_result():
    repository = FakeRepository(sample_job())
    result = run_one_company_research_job(
        repository, worker_id="worker-a",
        handler=lambda payload: {"snapshot_id": "snap-1", "lead_id": payload["lead_id"]},
    )
    assert result == {
        "status": "succeeded", "operation_id": "research:lead:123456",
        "result": {"snapshot_id": "snap-1", "lead_id": "lead-1"},
    }
    assert repository.calls[0] == ("claim", "worker-a", 120)
    assert repository.calls[1][0] == "complete"


def test_worker_returns_idle_without_calling_handler():
    repository = FakeRepository()
    result = run_one_company_research_job(
        repository, worker_id="worker-a",
        handler=lambda payload: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    assert result == {"status": "idle"}
    assert repository.calls == [("claim", "worker-a", 120)]


def test_worker_schedules_bounded_retry_without_persisting_exception_text():
    repository = FakeRepository(sample_job(), fail_result={
        "status": "retry_wait", "operation_id": "research:lead:123456",
    })

    def handler(_payload):
        raise RuntimeError("secret=do-not-persist")

    result = run_one_company_research_job(repository, worker_id="worker-a", handler=handler)
    assert result["status"] == "retry_scheduled"
    failure = next(call for call in repository.calls if call[0] == "fail")
    assert failure[4] == "Research job handler failed; sensitive exception details were not persisted."
    assert "secret" not in failure[4]


def test_worker_dead_letters_non_retryable_validation_errors():
    repository = FakeRepository(sample_job(), fail_result={
        "status": "dead_letter", "operation_id": "research:lead:123456",
    })
    result = run_one_company_research_job(
        repository, worker_id="worker-a",
        handler=lambda _payload: (_ for _ in ()).throw(ValueError("invalid input")),
    )
    assert result["status"] == "dead_letter"
    assert repository.calls[-1][-1] is False


def test_worker_rejects_non_object_handler_result():
    repository = FakeRepository(sample_job())
    result = run_one_company_research_job(
        repository, worker_id="worker-a", handler=lambda _payload: ["not", "an", "object"],
    )
    assert result["status"] == "dead_letter"


def test_worker_does_not_report_success_if_lease_was_lost():
    repository = FakeRepository(sample_job(), lose_lease=True)
    result = run_one_company_research_job(
        repository, worker_id="worker-a", handler=lambda _payload: {"ok": True},
    )
    assert result["status"] == "lease_lost"


def test_worker_requires_callable_handler_and_worker_id():
    repository = FakeRepository()
    try:
        run_one_company_research_job(repository, worker_id="worker-a", handler=None)
    except ValueError as exc:
        assert "callable" in str(exc)
    else:
        raise AssertionError("expected validation error")
