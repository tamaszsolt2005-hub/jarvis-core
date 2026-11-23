from types import SimpleNamespace

import pytest

import jarvis_auth


class FakeAuth:
    def __init__(self, user=None, session=None):
        self.user = user
        self.session = session
        self.signed_out = False
        self.set_session_args = None
        self.sign_in_args = None

    def sign_in_with_password(self, payload):
        self.sign_in_args = payload
        return SimpleNamespace(session=self.session)

    def get_user(self, *_args):
        return SimpleNamespace(user=self.user)

    def get_session(self):
        return self.session

    def set_session(self, access_token, refresh_token):
        self.set_session_args = (access_token, refresh_token)

    def sign_out(self):
        self.signed_out = True


class FakeClient:
    def __init__(self, auth):
        self.auth = auth


def user(role="operator", *, confirmed=True, user_metadata=None, user_id="user-1"):
    return SimpleNamespace(
        id=user_id,
        email="operator@example.com",
        email_confirmed_at="2026-01-01T00:00:00Z" if confirmed else None,
        confirmed_at=None,
        app_metadata={"role": role},
        user_metadata=user_metadata or {},
    )


def session():
    return SimpleNamespace(access_token="access-token", refresh_token="refresh-token")


def test_public_config_never_falls_back_to_service_role(monkeypatch):
    values = {
        "SUPABASE_URL": "https://project.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "must-not-be-used",
        "SUPABASE_KEY": "ambiguous-secret",
        "SUPABASE_PUBLISHABLE_KEY": None,
        "SUPABASE_ANON_KEY": None,
    }
    monkeypatch.setattr(jarvis_auth, "get_secret", lambda name: values.get(name))
    with pytest.raises(RuntimeError):
        jarvis_auth.public_supabase_config()


def test_public_config_accepts_publishable_or_legacy_anon(monkeypatch):
    values = {
        "SUPABASE_URL": "https://project.supabase.co",
        "SUPABASE_PUBLISHABLE_KEY": "publishable",
        "SUPABASE_ANON_KEY": "anon",
    }
    monkeypatch.setattr(jarvis_auth, "get_secret", lambda name: values.get(name))
    assert jarvis_auth.public_supabase_config() == (
        "https://project.supabase.co", "publishable"
    )
    values["SUPABASE_PUBLISHABLE_KEY"] = None
    assert jarvis_auth.public_supabase_config()[1] == "anon"


def test_sign_in_uses_auth_user_and_trusted_app_metadata_role():
    auth = FakeAuth(user=user("operator", user_metadata={"role": "admin"}), session=session())
    client = FakeClient(auth)
    result = jarvis_auth.sign_in_user(
        " operator@example.com ", "password", client_factory=lambda: client
    )
    assert result == {
        "access_token": "access-token",
        "refresh_token": "refresh-token",
        "user_id": "user-1",
        "email": "operator@example.com",
        "role": "operator",
    }
    assert auth.sign_in_args == {
        "email": "operator@example.com", "password": "password"
    }


@pytest.mark.parametrize("role", [None, "superuser", ""])
def test_sign_in_rejects_missing_or_unknown_trusted_role(role):
    metadata = {} if role is None else {"role": role}
    auth = FakeAuth(
        user=SimpleNamespace(
            id="user-1", email="operator@example.com",
            email_confirmed_at="confirmed", app_metadata=metadata,
        ),
        session=session(),
    )
    client = FakeClient(auth)
    with pytest.raises(PermissionError):
        jarvis_auth.sign_in_user(
            "operator@example.com", "password", client_factory=lambda: client
        )
    assert auth.signed_out is True


def test_sign_in_rejects_unconfirmed_email():
    auth = FakeAuth(user=user(confirmed=False), session=session())
    client = FakeClient(auth)
    with pytest.raises(PermissionError):
        jarvis_auth.sign_in_user(
            "operator@example.com", "password", client_factory=lambda: client
        )
    assert auth.signed_out is True


def test_verified_session_refreshes_and_rechecks_role():
    auth = FakeAuth(user=user("reader"), session=session())
    client = FakeClient(auth)
    verified, refreshed = jarvis_auth.verified_user_client(
        {
            "access_token": "old-access",
            "refresh_token": "old-refresh",
            "user_id": "user-1",
            "role": "admin",
        },
        allowed_roles={"reader"},
        client_factory=lambda: client,
    )
    assert verified is client
    assert auth.set_session_args == ("old-access", "old-refresh")
    assert refreshed["role"] == "reader"


def test_verified_session_rejects_user_id_mismatch():
    auth = FakeAuth(user=user("admin", user_id="different-user"), session=session())
    with pytest.raises(PermissionError):
        jarvis_auth.verified_user_client(
            {"access_token": "a", "refresh_token": "r", "user_id": "expected"},
            client_factory=lambda: FakeClient(auth),
        )


def test_verified_session_rejects_disallowed_role():
    auth = FakeAuth(user=user("operator"), session=session())
    with pytest.raises(PermissionError):
        jarvis_auth.verified_user_client(
            {"access_token": "a", "refresh_token": "r", "user_id": "user-1"},
            allowed_roles={"admin"},
            client_factory=lambda: FakeClient(auth),
        )


@pytest.mark.parametrize(
    ("role", "permission", "allowed"),
    [
        ("admin", "settings.write", True),
        ("operator", "leads.write", True),
        ("operator", "settings.write", False),
        ("reader", "leads.read", True),
        ("reader", "leads.write", False),
        (None, "leads.read", False),
        ("unknown", "audit.read", False),
    ],
)
def test_role_permission_matrix_fails_closed(role, permission, allowed):
    assert jarvis_auth.has_permission(role, permission) is allowed
    if allowed:
        jarvis_auth.require_permission(role, permission)
    else:
        with pytest.raises(PermissionError):
            jarvis_auth.require_permission(role, permission)


def test_sign_in_rejects_missing_credentials():
    with pytest.raises(ValueError):
        jarvis_auth.sign_in_user("", "password")
    with pytest.raises(ValueError):
        jarvis_auth.sign_in_user("user@example.com", "")
