"""Admin-only audit viewer using a verified Supabase Auth JWT and RLS.

The application service-role client is deliberately never used for audit reads.
"""
from __future__ import annotations

import csv
import io
from typing import Any

from supabase import Client, create_client

from jarvis_common import get_secret, get_audit_events_page


AUDIT_COLUMNS = (
    "id,created_at,module,action,status,result,error,approved,"
    "recipient,subject,delivery_id,level,message,operation_id,"
    "previous_hash,entry_hash,actor_user_id"
)


def _public_supabase_config() -> tuple[str, str]:
    url = get_secret("SUPABASE_URL")
    # Never fall back to SUPABASE_SERVICE_ROLE_KEY or the ambiguous legacy
    # SUPABASE_KEY here. This client must authenticate as the signed-in user.
    key = get_secret("SUPABASE_PUBLISHABLE_KEY") or get_secret("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError(
            "Audit belépéshez SUPABASE_URL és SUPABASE_PUBLISHABLE_KEY "
            "(vagy SUPABASE_ANON_KEY) szükséges."
        )
    return url, key


def _client() -> Client:
    url, key = _public_supabase_config()
    return create_client(url, key)


def _user_from_verified_response(response: Any) -> Any:
    user = getattr(response, "user", None)
    if user is None:
        raise PermissionError("A Supabase Auth nem adott vissza ellenőrzött felhasználót.")
    metadata = getattr(user, "app_metadata", None) or {}
    if not isinstance(metadata, dict) or metadata.get("role") != "admin":
        raise PermissionError("Az auditnapló megtekintéséhez admin szerepkör szükséges.")
    return user


def sign_in_audit_admin(email: str, password: str) -> dict[str, str]:
    """Sign in and verify admin role from server-validated app_metadata."""
    normalized_email = str(email or "").strip()
    if not normalized_email or not password:
        raise ValueError("E-mail-cím és jelszó megadása kötelező.")

    client = _client()
    response = client.auth.sign_in_with_password(
        {"email": normalized_email, "password": password}
    )
    auth_session = getattr(response, "session", None)
    access_token = getattr(auth_session, "access_token", None)
    refresh_token = getattr(auth_session, "refresh_token", None)
    if not access_token or not refresh_token:
        raise PermissionError("A Supabase Auth nem adott érvényes munkamenetet.")

    try:
        user = _user_from_verified_response(client.auth.get_user(access_token))
    except Exception:
        try:
            client.auth.sign_out()
        except Exception:
            pass
        raise

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user_id": str(getattr(user, "id", "")),
        "email": str(getattr(user, "email", "") or normalized_email),
    }


def verified_admin_client(session: dict[str, str]) -> tuple[Client, dict[str, str]]:
    """Refresh/validate the session and re-check the trusted admin claim."""
    if not isinstance(session, dict):
        raise PermissionError("Hiányzó audit munkamenet.")
    access_token = session.get("access_token")
    refresh_token = session.get("refresh_token")
    if not access_token or not refresh_token:
        raise PermissionError("Hiányos audit munkamenet.")

    client = _client()
    client.auth.set_session(access_token, refresh_token)
    user = _user_from_verified_response(client.auth.get_user())
    current = client.auth.get_session()
    refreshed = getattr(current, "access_token", None)
    refreshed_refresh = getattr(current, "refresh_token", None)
    if not refreshed or not refreshed_refresh:
        raise PermissionError("Az audit munkamenet lejárt.")
    return client, {
        "access_token": refreshed,
        "refresh_token": refreshed_refresh,
        "user_id": str(getattr(user, "id", "")),
        "email": str(getattr(user, "email", "") or ""),
    }


def sign_out_audit_admin(session: dict[str, str]) -> None:
    """Revoke the current Supabase Auth session where possible."""
    if not isinstance(session, dict):
        return
    access_token = session.get("access_token")
    refresh_token = session.get("refresh_token")
    if not access_token or not refresh_token:
        return
    client = _client()
    client.auth.set_session(access_token, refresh_token)
    client.auth.sign_out()


def fetch_audit_rows(
    client: Client,
    *,
    module: str | None = None,
    status: str | None = None,
    limit: int = 250,
) -> list[dict[str, Any]]:
    """Read audit records through the admin user's JWT, so PostgreSQL RLS applies."""
    bounded_limit = max(1, min(int(limit), 500))
    query = (
        client.table("logs")
        .select(AUDIT_COLUMNS)
        .order("created_at", desc=True)
        .order("id", desc=True)
        .limit(bounded_limit)
    )
    if module and module != "Összes modul":
        query = query.eq("module", module)
    if status and status != "Összes státusz":
        query = query.eq("status", status)
    rows = query.execute().data or []
    if not isinstance(rows, list):
        raise TypeError("Az auditlekérdezés nem lista eredményt adott.")
    return [row for row in rows if isinstance(row, dict)]


def fetch_audit_page(
    client: Client,
    *,
    module: str | None = None,
    status: str | None = None,
    operation_id: str | None = None,
    cursor: dict[str, str] | None = None,
    page_size: int = 100,
) -> dict[str, Any]:
    """Fetch a bounded cursor page through the verified admin JWT client."""
    return get_audit_events_page(
        client,
        page_size=max(1, min(int(page_size), 100)),
        module=module,
        status=status,
        operation_id=operation_id,
        cursor=cursor,
    )


def audit_rows_to_csv(rows: list[dict[str, Any]]) -> bytes:
    """Serialize only the selected audit rows; no secrets or request bodies are added."""
    output = io.StringIO(newline="")
    fields = list(AUDIT_COLUMNS.split(","))
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")
