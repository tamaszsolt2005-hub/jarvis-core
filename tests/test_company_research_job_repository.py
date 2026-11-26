from __future__ import annotations

from copy import deepcopy

import pytest

from company_research_job_repository import (
    CompanyResearchJobRepositoryError,
    RPC_CLAIM,
    RPC_COMPLETE,
    RPC_CREATE,
    RPC_FAIL,
    RPC_HEARTBEAT,
    SupabaseCompanyResearchJobRepository,
)


class Response:
    def __init__(self, data):
        self.data = data


class FakeRpcCall:
    def __init__(self, client, name, params):
        self.client, self.name, self.params = client, name, params

    def execute(self):
        self.client.calls.append((self.name, deepcopy(self.params)))
        value = self.client.responses.get(self.name)
        if isinstance(value, Exception):
            raise value
        return Response(deepcopy(value))


class FakeSupabaseClient:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    def rpc(self, name, params):
        return FakeRpcCall(self, name, params)


def sample_job(operation_id="research:lead-123"):
    return {
        "operation_id": operation_id,
        "job_type": "company_research_refresh",
        "lead_id": "00000000-0000-4000-8000-000000000001",
        "payload": {"source": "planner"},
        "status": "queued",
    }


def test_create_uses_injected_client_and_is_idempotent_by_rpc_contract():
    client = FakeSupabaseClient({RPC_CREATE: sample_job()})
    repository = SupabaseCompanyResearchJobRepository(client)
    payload = {"source": "planner"}
    result = repository.create(operation_id="research:lead-123", lead_id="00000000-0000-4000-8000-000000000001", payload=payload)
    payload["source"] = "mutated"
    assert result["operation_id"] == "research:lead-123"
    assert client.calls[0][0] == RPC_CREATE
    assert client.calls[0][1]["p_job"]["payload"] == {"source": "planner"}


@pytest.mark.parametrize("operation_id", ["short", "", None])
def test_create_validates_operation_id_before_rpc(operation_id):
    client = FakeSupabaseClient()
    repository = SupabaseCompanyResearchJobRepository(client)
    with pytest.raises(ValueError):
        repository.create(operation_id=operation_id, lead_id="00000000-0000-4000-8000-000000000001", payload={})
    assert client.calls == []


def test_create_rejects_mismatched_operation_id_from_database():
    client = FakeSupabaseClient({RPC_CREATE: sample_job("different:operation")})
    repository = SupabaseCompanyResearchJobRepository(client)
    with pytest.raises(CompanyResearchJobRepositoryError, match="different operation_id"):
        repository.create(operation_id="research:lead-123", lead_id="00000000-0000-4000-8000-000000000001", payload={"source": "planner"})


def test_claim_calls_single_atomic_database_rpc_and_returns_none_when_empty():
    client = FakeSupabaseClient({RPC_CLAIM: []})
    repository = SupabaseCompanyResearchJobRepository(client)
    assert repository.claim(worker_id="worker-a", lease_seconds=45) is None
    assert client.calls == [(RPC_CLAIM, {"p_worker_id": "worker-a", "p_lease_seconds": 45})]


def test_heartbeat_complete_and_fail_are_delegated_to_conditional_rpcs():
    job = sample_job()
    client = FakeSupabaseClient({
        RPC_HEARTBEAT: [job], RPC_COMPLETE: [job], RPC_FAIL: [job],
    })
    repository = SupabaseCompanyResearchJobRepository(client)
    assert repository.heartbeat(operation_id=job["operation_id"], worker_id="worker-a")
    assert repository.complete(operation_id=job["operation_id"], worker_id="worker-a", result={"ok": True})
    assert repository.fail(
        operation_id=job["operation_id"], worker_id="worker-a",
        error_code="temporary", error_message="retry", retryable=True,
        retry_delay_seconds=30, max_attempts=4,
    )
    assert [call[0] for call in client.calls] == [RPC_HEARTBEAT, RPC_COMPLETE, RPC_FAIL]
    assert client.calls[1][1]["p_result"] == {"ok": True}
    assert client.calls[2][1]["p_retryable"] is True


def test_transition_rpc_empty_result_means_lease_or_state_conflict():
    client = FakeSupabaseClient({RPC_COMPLETE: []})
    repository = SupabaseCompanyResearchJobRepository(client)
    assert repository.complete(operation_id="research:lead-123", worker_id="stale-worker") is None


def test_unexpected_rpc_shape_and_database_errors_are_wrapped():
    client = FakeSupabaseClient({RPC_CLAIM: [{"a": 1}, {"b": 2}]})
    repository = SupabaseCompanyResearchJobRepository(client)
    with pytest.raises(CompanyResearchJobRepositoryError, match="response shape"):
        repository.claim(worker_id="worker-a")
    client = FakeSupabaseClient({RPC_CLAIM: RuntimeError("private connection detail")})
    repository = SupabaseCompanyResearchJobRepository(client)
    with pytest.raises(CompanyResearchJobRepositoryError, match="RPC failed"):
        repository.claim(worker_id="worker-a")


def test_adapter_requires_injected_rpc_client_and_validates_limits():
    with pytest.raises(ValueError, match="injected"):
        SupabaseCompanyResearchJobRepository(None)
    repository = SupabaseCompanyResearchJobRepository(FakeSupabaseClient())
    with pytest.raises(ValueError, match="positive integer"):
        repository.claim(worker_id="worker-a", lease_seconds=True)
    with pytest.raises(ValueError, match="worker_id"):
        repository.claim(worker_id=" ")



@pytest.mark.parametrize(
    ("field", "conflicting_value"),
    [
        ("lead_id", "00000000-0000-4000-8000-000000000002"),
        ("payload", {"source": "different"}),
        ("job_type", "other_job"),
    ],
)
def test_create_rejects_operation_id_reuse_with_conflicting_immutable_data(field, conflicting_value):
    existing = sample_job()
    existing[field] = conflicting_value
    client = FakeSupabaseClient({RPC_CREATE: existing})
    repository = SupabaseCompanyResearchJobRepository(client)
    with pytest.raises(CompanyResearchJobRepositoryError, match="idempotency conflict"):
        repository.create(
            operation_id="research:lead-123",
            lead_id="00000000-0000-4000-8000-000000000001",
            payload={"source": "planner"},
        )
