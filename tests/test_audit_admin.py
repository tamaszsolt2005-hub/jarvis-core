"""Security and failure-path tests for the admin-only audit viewer."""
from types import SimpleNamespace

import pytest

import audit_admin


def _user(role="admin", *, confirmed=True, user_id="admin-1", email="admin@example.com"):
    return SimpleNamespace(
        id=user_id,
        email=email,
        email_confirmed_at="confirmed" if confirmed else None,
        confirmed_at=None,
        app_metadata={"role": role},
    )


def _session(access="access", refresh="refresh"):
    return SimpleNamespace(access_token=access, refresh_token=refresh)


class FakeAuth:
    def __init__(self, user=None, session=None):
        self.user = user
        self.session = session
        self.signed_out = False
        self.set_session_args = None
        self.login_payload = None

    def sign_in_with_password(self, payload):
        self.login_payload = payload
        return SimpleNamespace(session=self.session)

    def get_user(self, *_args):
        return SimpleNamespace(user=self.user)

    def get_session(self):
        return self.session

    def set_session(self, access, refresh):
        self.set_session_args = (access, refresh)

    def sign_out(self):
        self.signed_out = True


class FakeClient:
    def __init__(self, auth=None, data=None):
        self.auth = auth or FakeAuth()
        self.data = data
        self.query = FakeQuery(data)
        self.rpc_name = None

    def table(self, name):
        assert name == "logs"
        return self.query

    def rpc(self, name):
        self.rpc_name = name
        return FakeRPC(self.data)


class FakeQuery:
    def __init__(self, data):
        self.data = data
        self.calls = []

    def select(self, value):
        self.calls.append(("select", value))
        return self

    def order(self, *args, **kwargs):
        self.calls.append(("order", args, kwargs))
        return self

    def limit(self, value):
        self.calls.append(("limit", value))
        return self

    def eq(self, *args):
        self.calls.append(("eq", args))
        return self

    def execute(self):
        return SimpleNamespace(data=self.data)


class FakeRPC:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return SimpleNamespace(data=self.data)


def _client_factory(monkeypatch, client):
    monkeypatch.setattr(audit_admin, "_client", lambda: client)


def test_public_config_uses_publishable_or_anon_and_never_service_role(monkeypatch):
    values = {
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_PUBLISHABLE_KEY": None,
        "SUPABASE_ANON_KEY": "anon-key",
        "SUPABASE_SERVICE_ROLE_KEY": "service-secret",
        "SUPABASE_KEY": "ambiguous-secret",
    }
    monkeypatch.setattr(audit_admin, "get_secret", lambda key: values.get(key))
    assert audit_admin._public_supabase_config() == (
        "https://example.supabase.co", "anon-key"
    )
    values["SUPABASE_PUBLISHABLE_KEY"] = "publishable"
    assert audit_admin._public_supabase_config()[1] == "publishable"
    values["SUPABASE_URL"] = None
    with pytest.raises(RuntimeError):
        audit_admin._public_supabase_config()


def test_user_verification_rejects_missing_unconfirmed_and_non_admin():
    with pytest.raises(PermissionError):
        audit_admin._user_from_verified_response(SimpleNamespace(user=None))
    with pytest.raises(PermissionError):
        audit_admin._user_from_verified_response(SimpleNamespace(user=_user(confirmed=False)))
    with pytest.raises(PermissionError):
        audit_admin._user_from_verified_response(SimpleNamespace(user=_user("operator")))
    with pytest.raises(PermissionError):
        audit_admin._user_from_verified_response(
            SimpleNamespace(user=SimpleNamespace(
                email_confirmed_at="yes", confirmed_at=None, app_metadata=["admin"]
            ))
        )


def test_sign_in_requires_credentials_and_complete_session(monkeypatch):
    client = FakeClient(FakeAuth(user=_user(), session=None))
    _client_factory(monkeypatch, client)
    with pytest.raises(ValueError):
        audit_admin.sign_in_audit_admin("", "pw")
    with pytest.raises(ValueError):
        audit_admin.sign_in_audit_admin("admin@example.com", "")
    with pytest.raises(PermissionError):
        audit_admin.sign_in_audit_admin("admin@example.com", "pw")


@pytest.mark.parametrize(
    "user",
    [_user("operator"), _user(confirmed=False), None],
)
def test_sign_in_revokes_session_when_user_is_not_verified_admin(monkeypatch, user):
    auth = FakeAuth(user=user, session=_session())
    _client_factory(monkeypatch, FakeClient(auth))
    with pytest.raises(PermissionError):
        audit_admin.sign_in_audit_admin(" admin@example.com ", "pw")
    assert auth.signed_out is True


def test_sign_in_returns_only_verified_admin_session(monkeypatch):
    auth = FakeAuth(user=_user(), session=_session())
    _client_factory(monkeypatch, FakeClient(auth))
    result = audit_admin.sign_in_audit_admin(" admin@example.com ", "pw")
    assert auth.login_payload == {"email": "admin@example.com", "password": "pw"}
    assert result == {
        "access_token": "access",
        "refresh_token": "refresh",
        "user_id": "admin-1",
        "email": "admin@example.com",
    }


def test_verified_admin_client_refreshes_and_returns_verified_identity(monkeypatch):
    auth = FakeAuth(user=_user(), session=_session("new-access", "new-refresh"))
    client = FakeClient(auth)
    _client_factory(monkeypatch, client)
    verified, refreshed = audit_admin.verified_admin_client(
        {"access_token": "old-access", "refresh_token": "old-refresh"}
    )
    assert verified is client
    assert auth.set_session_args == ("old-access", "old-refresh")
    assert refreshed["access_token"] == "new-access"
    assert refreshed["refresh_token"] == "new-refresh"
    assert refreshed["user_id"] == "admin-1"


@pytest.mark.parametrize("session", [None, [], {}, {"access_token": "a"}, {"refresh_token": "r"}])
def test_verified_admin_client_rejects_invalid_session(monkeypatch, session):
    _client_factory(monkeypatch, FakeClient())
    with pytest.raises(PermissionError):
        audit_admin.verified_admin_client(session)


def test_verified_admin_client_rejects_expired_or_demoted_session(monkeypatch):
    expired_auth = FakeAuth(user=_user(), session=None)
    _client_factory(monkeypatch, FakeClient(expired_auth))
    with pytest.raises(PermissionError):
        audit_admin.verified_admin_client({"access_token": "a", "refresh_token": "r"})

    demoted_auth = FakeAuth(user=_user("operator"), session=_session())
    _client_factory(monkeypatch, FakeClient(demoted_auth))
    with pytest.raises(PermissionError):
        audit_admin.verified_admin_client({"access_token": "a", "refresh_token": "r"})


def test_sign_out_is_noop_without_tokens_and_revokes_valid_session(monkeypatch):
    audit_admin.sign_out_audit_admin(None)
    audit_admin.sign_out_audit_admin({})
    auth = FakeAuth()
    _client_factory(monkeypatch, FakeClient(auth))
    audit_admin.sign_out_audit_admin({"access_token": "a", "refresh_token": "r"})
    assert auth.set_session_args == ("a", "r")
    assert auth.signed_out is True


def test_fetch_audit_rows_bounds_limit_and_applies_optional_filters():
    client = FakeClient([{"id": 1}, "malformed", {"id": 2}])
    rows = audit_admin.fetch_audit_rows(
        client, module="email", status="failed", limit=900
    )
    assert rows == [{"id": 1}, {"id": 2}]
    assert ("limit", 500) in client.query.calls
    assert ("eq", ("module", "email")) in client.query.calls
    assert ("eq", ("status", "failed")) in client.query.calls
    assert client.query.calls[0] == ("select", audit_admin.AUDIT_COLUMNS)


def test_fetch_audit_rows_omits_all_filters_and_rejects_non_list():
    client = FakeClient([])
    assert audit_admin.fetch_audit_rows(
        client, module="Összes modul", status="Összes státusz", limit=0
    ) == []
    assert ("limit", 1) in client.query.calls
    assert not any(call[0] == "eq" for call in client.query.calls)

    with pytest.raises(TypeError):
        audit_admin.fetch_audit_rows(FakeClient({"not": "a list"}))


def test_fetch_audit_page_clamps_size_and_forwards_filters(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        audit_admin, "get_audit_events_page",
        lambda client, **kwargs: captured.update({"client": client, **kwargs}) or {"rows": []},
    )
    client = FakeClient()
    result = audit_admin.fetch_audit_page(
        client, module="chat", status="failed", operation_id="op-1",
        cursor={"created_at": "2026-01-01", "id": "4"}, page_size=500,
    )
    assert result == {"rows": []}
    assert captured == {
        "client": client, "page_size": 100, "module": "chat",
        "status": "failed", "operation_id": "op-1",
        "cursor": {"created_at": "2026-01-01", "id": "4"},
    }


def test_verify_integrity_requires_a_well_formed_result():
    client = FakeClient([{"valid": True}])
    assert audit_admin.verify_audit_integrity(client) == {"valid": True}
    assert client.rpc_name == "verify_logs_audit_chain"
    for data in (None, [], ["bad"], {"valid": True}):
        with pytest.raises(RuntimeError):
            audit_admin.verify_audit_integrity(FakeClient(data))


def test_csv_export_uses_utf8_bom_and_neutralizes_formula_cells():
    payload = audit_admin.audit_rows_to_csv([
        {"id": 1, "message": " =HYPERLINK(\"https://evil.test\")", "extra": "ignored"},
        {"id": 2, "message": "+cmd"},
        {"id": 3, "message": "-1"},
        {"id": 4, "message": "@SUM(A1:A2)"},
    ])
    assert payload.startswith(b"\\xef\\xbb\\xbf")
    decoded = payload.decode("utf-8-sig")
    assert "' =HYPERLINK" in decoded
    assert "'+cmd" in decoded
    assert "'-1" in decoded
    assert "'@SUM" in decoded
    assert "ignored" not in decoded
