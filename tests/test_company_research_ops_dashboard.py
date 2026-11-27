from types import SimpleNamespace

import pytest

from company_research_ops_dashboard import (
    load_worker_control_state,
    set_worker_paused,
)


class FakeRPC:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=self.response))


def test_load_worker_control_state_uses_authenticated_rpc_payload():
    db = FakeRPC({"paused": True, "counts": {"queued": 3}})
    assert load_worker_control_state(db)["paused"] is True
    assert db.calls == [("company_research_worker_control_state", {})]


def test_set_worker_paused_requires_reason_and_uses_guarded_rpc():
    db = FakeRPC({"paused": True})
    with pytest.raises(ValueError, match="reason"):
        set_worker_paused(db, paused=True, note="no")
    result = set_worker_paused(db, paused=True, note="Scheduled maintenance")
    assert result["paused"] is True
    assert db.calls == [(
        "company_research_worker_set_paused",
        {"p_paused": True, "p_note": "Scheduled maintenance"},
    )]


def test_ops_dashboard_rpc_fails_closed_on_unexpected_shape():
    db = FakeRPC([])
    with pytest.raises(RuntimeError, match="unexpected response"):
        load_worker_control_state(db)
