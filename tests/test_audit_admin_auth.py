import csv
import io
from types import SimpleNamespace

import pytest

import audit_admin


class FakeAuth:
    def __init__(self, role="admin"):
        self.role = role
        self.signed_out = False
        self.session = SimpleNamespace(
            access_token="access-token",
            refresh_token="refresh-token",
        )

    def sign_in_with_password(self, credentials):
        assert credentials == {"email": "admin@example.test", "password": "secret"}
        return SimpleNamespace(session=self.session)

    def get_user(self, *_args):
        return SimpleNamespace(
            user=SimpleNamespace(
                id="user-123",
                email="admin@example.test",
                email_confirmed_at="2026-11-01T00:00:00Z",
                app_metadata={"role": self.role},
            )
        )

    def set_session(self, access_token, refresh_token):
        assert access_token == "access-token"
        assert refresh_token == "refresh-token"

    def get_session(self):
        return self.session

    def sign_out(self):
        self.signed_out = True


class FakeClient:
    def __init__(self, role="admin"):
        self.auth = FakeAuth(role)


def test_sign_in_requires_verified_admin_role(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(audit_admin, "_client", lambda: client)
    result = audit_admin.sign_in_audit_admin("admin@example.test", "secret")
    assert result == {
        "access_token": "access-token",
        "refresh_token": "refresh-token",
        "user_id": "user-123",
        "email": "admin@example.test",
    }


def test_sign_in_rejects_non_admin_and_signs_out(monkeypatch):
    client = FakeClient(role="operator")
    monkeypatch.setattr(audit_admin, "_client", lambda: client)
    with pytest.raises(PermissionError, match="admin"):
        audit_admin.sign_in_audit_admin("admin@example.test", "secret")
    assert client.auth.signed_out is True


def test_sign_in_rejects_missing_credentials(monkeypatch):
    monkeypatch.setattr(audit_admin, "_client", lambda: pytest.fail("client must not be created"))
    with pytest.raises(ValueError):
        audit_admin.sign_in_audit_admin("", "secret")


def test_public_client_never_uses_legacy_or_service_role_key(monkeypatch):
    values = {
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_PUBLISHABLE_KEY": None,
        "SUPABASE_ANON_KEY": None,
        "SUPABASE_KEY": "legacy-key",
        "SUPABASE_SERVICE_ROLE_KEY": "service-role-secret",
    }
    monkeypatch.setattr(audit_admin, "get_secret", lambda name: values.get(name))
    with pytest.raises(RuntimeError, match="SUPABASE_PUBLISHABLE_KEY"):
        audit_admin._public_supabase_config()


def test_verified_client_rechecks_admin_claim_and_refreshes_tokens(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(audit_admin, "_client", lambda: client)
    verified, session = audit_admin.verified_admin_client({
        "access_token": "access-token",
        "refresh_token": "refresh-token",
    })
    assert verified is client
    assert session["user_id"] == "user-123"
    assert session["access_token"] == "access-token"


def test_verified_client_rejects_non_admin(monkeypatch):
    client = FakeClient(role="reader")
    monkeypatch.setattr(audit_admin, "_client", lambda: client)
    with pytest.raises(PermissionError, match="admin"):
        audit_admin.verified_admin_client({
            "access_token": "access-token",
            "refresh_token": "refresh-token",
        })


def test_audit_csv_has_headers_and_no_unrequested_payload():
    data = audit_admin.audit_rows_to_csv([{
        "id": "1",
        "created_at": "2026-11-23T00:00:00Z",
        "module": "test",
        "message": "ok",
        "unexpected_secret": "must-not-export",
    }])
    decoded = data.decode("utf-8-sig")
    assert "operation_id" in decoded
    assert "unexpected_secret" not in decoded
    assert "must-not-export" not in decoded


def test_integrity_verifier_uses_authenticated_rpc():
    class RpcClient:
        def rpc(self, name):
            assert name == "verify_logs_audit_chain"
            return SimpleNamespace(execute=lambda: SimpleNamespace(data=[{
                "ok": True,
                "total_entries": 3,
                "invalid_hashes": 0,
                "missing_predecessors": 0,
                "forks": 0,
                "disconnected_entries": 0,
                "state_matches": True,
            }]))

    result = audit_admin.verify_audit_integrity(RpcClient())
    assert result["ok"] is True
    assert result["total_entries"] == 3


def test_sign_in_rejects_unverified_email(monkeypatch):
    client = FakeClient()
    original = client.auth.get_user

    def unverified(*args):
        response = original(*args)
        response.user.email_confirmed_at = None
        return response

    client.auth.get_user = unverified
    monkeypatch.setattr(audit_admin, "_client", lambda: client)
    with pytest.raises(PermissionError, match="e-mail-címét"):
        audit_admin.sign_in_audit_admin("admin@example.test", "secret")
    assert client.auth.signed_out is True


def test_audit_csv_neutralizes_spreadsheet_formula_cells():
    payload = "=HYPERLINK(\"https://example.invalid\",\"click\")"
    raw = audit_admin.audit_rows_to_csv([{"subject": payload}]).decode("utf-8-sig")
    row = next(csv.DictReader(io.StringIO(raw)))
    assert row["subject"] == "'" + payload
