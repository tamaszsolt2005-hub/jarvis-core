import pytest

from lead_identity import upsert_company_lead


class RPCResult:
    def __init__(self, data):
        self.data = data


class RPCQuery:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return RPCResult(self.data)


class DB:
    def __init__(self, data):
        self.data = data
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        return RPCQuery(self.data)


def test_company_lead_client_passes_consent_and_returns_rpc_result():
    db = DB([{
        "lead_id": "lead-123",
        "outcome": "existing",
        "selected_email": "xy@gmail.com",
    }])

    result = upsert_company_lead(
        db,
        company_name="Példa Kft.",
        website="https://cukraszda.hu",
        email="xy@gmail.com",
        notes="reviewed",
        source="reviewed_csv",
        consent_basis="consent",
        approved_to_contact=True,
        consent_confirmed_at="2026-11-26T10:00:00+01:00",
    )

    assert result == {
        "lead_id": "lead-123",
        "outcome": "existing",
        "selected_email": "xy@gmail.com",
    }
    name, params = db.calls[0]
    assert name == "upsert_company_lead"
    assert params["p_email"] == "xy@gmail.com"
    assert params["p_consent_basis"] == "consent"
    assert params["p_approved_to_contact"] is True
    assert params["p_consent_confirmed_at"] == "2026-11-26T10:00:00+01:00"


@pytest.mark.parametrize(
    "data",
    [
        [],
        [{"outcome": "created", "lead_id": None}],
        [{"outcome": "unknown", "lead_id": "lead-123"}],
        [{"outcome": "created", "lead_id": "lead-123"}],
    ],
)
def test_company_lead_client_fails_closed_on_unconfirmed_rpc_result(data):
    with pytest.raises(RuntimeError):
        upsert_company_lead(DB(data), company_name="Példa Kft.")


def test_all_lead_creation_modules_use_the_atomic_company_rpc():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for filename in ("global_lead_research.py", "lead_gen.py"):
        source = (root / filename).read_text(encoding="utf-8")
        assert "upsert_company_lead" in source
        assert '.table("leads").insert(' not in source
