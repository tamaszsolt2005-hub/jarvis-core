"""Supabase Auth primitives and fail-closed RBAC policy helpers.

This module provides verified Supabase Auth sessions and fail-closed role
checks. The dashboard Auth path remains opt-in until users and RLS policies
are provisioned. It never creates a service-role client.
"""
from __future__ import annotations

from typing import Any, Callable

from supabase import Client, create_client

from jarvis_common import get_secret


ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "admin": frozenset({
        "leads.read", "leads.write",
        "tasks.read", "tasks.write",
        "email_drafts.read", "email_drafts.write", "email.send",
        "analytics.read",
        "settings.read", "settings.write",
        "users.manage", "audit.read",
        "memory.read", "memory.write",
    }),
    "operator": frozenset({
        "leads.read", "leads.write",
        "tasks.read", "tasks.write",
        "email_drafts.read", "email_drafts.write", "email.send",
        "settings.read",
        "memory.read", "memory.write",
    }),
    "reader": frozenset({
        "leads.read", "tasks.read", "email_drafts.read", "memory.read",
    }),
}

PUBLIC_AUTH_KEY_NAMES = ("SUPABASE_PUBLISHABLE_KEY", "SUPABASE_ANON_KEY")


def public_supabase_config() -> tuple[str, str]:
    """Return only the project URL and a publishable/legacy anon key."""
    url = get_secret("SUPABASE_URL")
    key = next((get_secret(name) for name in PUBLIC_AUTH_KEY_NAMES if get_secret(name)), None)
    if not url or not key:
        raise RuntimeError(
            "Supabase Auth requires SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY "
            "(or the legacy SUPABASE_ANON_KEY)."
        )
    return url, key


def create_user_client() -> Client:
    """Create a public-key client; never fall back to service-role credentials."""
    url, key = public_supabase_config()
    return create_client(url, key)


def _verified_user(response: Any) -> Any:
    user = getattr(response, "user", None)
    if user is None or not getattr(user, "id", None):
        raise PermissionError("Supabase Auth did not return a verified user.")
    if not (
        getattr(user, "email_confirmed_at", None)
        or getattr(user, "confirmed_at", None)
    ):
        raise PermissionError("The account email address must be confirmed.")
    metadata = getattr(user, "app_metadata", None)
    if not isinstance(metadata, dict):
        raise PermissionError("A trusted application role is required.")
    role = metadata.get("role")
    # app_metadata is server-managed, but malformed claims must still fail closed.
    # Check the type before dictionary membership to avoid TypeError for list/dict claims.
    if not isinstance(role, str) or role not in ROLE_PERMISSIONS:
        raise PermissionError("The account has no valid trusted application role.")
    return user


def _session_payload(auth_session: Any, user: Any) -> dict[str, str]:
    access_token = getattr(auth_session, "access_token", None)
    refresh_token = getattr(auth_session, "refresh_token", None)
    if not access_token or not refresh_token:
        raise PermissionError("Supabase Auth did not return a complete session.")
    return {
        "access_token": str(access_token),
        "refresh_token": str(refresh_token),
        "user_id": str(user.id),
        "email": str(getattr(user, "email", "") or ""),
        "role": str(user.app_metadata["role"]),
    }


def sign_in_user(
    email: str,
    password: str,
    *,
    client_factory: Callable[[], Client] = create_user_client,
) -> dict[str, str]:
    """Authenticate an individual user and authorize only trusted app_metadata."""
    normalized_email = str(email or "").strip()
    if not normalized_email or not password:
        raise ValueError("Email address and password are required.")
    client = client_factory()
    response = client.auth.sign_in_with_password({
        "email": normalized_email,
        "password": password,
    })
    auth_session = getattr(response, "session", None)
    access_token = getattr(auth_session, "access_token", None)
    if not access_token:
        raise PermissionError("Supabase Auth did not issue a valid session.")
    try:
        user = _verified_user(client.auth.get_user(access_token))
        return _session_payload(auth_session, user)
    except Exception:
        try:
            client.auth.sign_out()
        except Exception:
            pass
        raise


def verified_user_client(
    session: dict[str, str],
    *,
    allowed_roles: set[str] | frozenset[str] | None = None,
    client_factory: Callable[[], Client] = create_user_client,
) -> tuple[Client, dict[str, str]]:
    """Refresh a session, verify the user with Auth, and re-read app_metadata."""
    if not isinstance(session, dict):
        raise PermissionError("Missing Supabase Auth session.")
    access_token = session.get("access_token")
    refresh_token = session.get("refresh_token")
    expected_user_id = session.get("user_id")
    if not access_token or not refresh_token or not expected_user_id:
        raise PermissionError("Incomplete Supabase Auth session.")

    client = client_factory()
    client.auth.set_session(access_token, refresh_token)
    user = _verified_user(client.auth.get_user())
    if str(user.id) != str(expected_user_id):
        raise PermissionError("The authenticated user does not match this session.")
    role = str(user.app_metadata["role"])
    if allowed_roles is not None and role not in allowed_roles:
        raise PermissionError("This action is not permitted for the current role.")
    current_session = client.auth.get_session()
    refreshed = _session_payload(current_session, user)
    return client, refreshed


def sign_out_user(
    session: dict[str, str] | None,
    *,
    client_factory: Callable[[], Client] = create_user_client,
) -> None:
    """Revoke the current Auth session; missing sessions are a no-op."""
    if not isinstance(session, dict):
        return
    access_token = session.get("access_token")
    refresh_token = session.get("refresh_token")
    if not access_token or not refresh_token:
        return
    client = client_factory()
    client.auth.set_session(access_token, refresh_token)
    client.auth.sign_out()


def has_permission(role: str | None, permission: str) -> bool:
    """Return False for unknown roles and permissions."""
    return permission in ROLE_PERMISSIONS.get(str(role or ""), frozenset())


def require_permission(role: str | None, permission: str) -> None:
    """Raise instead of silently allowing unknown or missing roles."""
    if not has_permission(role, permission):
        raise PermissionError(f"Permission denied: {permission}")
