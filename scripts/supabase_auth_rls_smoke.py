#!/usr/bin/env python3
"""Live Supabase Auth/JWT/RLS smoke test for a disposable JARVIS test project.

Creates temporary Auth users and fixture rows in the configured non-production
project. The project is intentionally disposable: audit rows are append-only.
Never point this script at the production project.
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import sys
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

PRODUCTION_PROJECT_REF = "kiutreccucbegskxowek"
ALLOWED_ROLES = {"admin", "operator", "reader"}


class SmokeTestError(RuntimeError):
    pass


def _jwt_claims(token: str) -> dict:
    """Decode claims for assertions only; Supabase/PostgREST verifies signatures."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
    except (IndexError, ValueError, json.JSONDecodeError) as exc:
        raise SmokeTestError("Supabase Auth returned a malformed JWT.") from exc


def _validate_target(url: str, project_ref: str) -> None:
    parsed = urlparse(url)
    if not url.startswith("https://") or not parsed.hostname:
        raise SmokeTestError("SUPABASE_URL must be an HTTPS Supabase project URL.")
    if not project_ref or project_ref == PRODUCTION_PROJECT_REF:
        raise SmokeTestError("Refusing to run live Auth tests against production.")
    if parsed.hostname != f"{project_ref}.supabase.co":
        raise SmokeTestError("SUPABASE_URL does not match SUPABASE_EXPECTED_PROJECT_REF.")


class SupabaseHttp:
    def __init__(self, url: str, publishable_key: str, service_role_key: str):
        self.url = url.rstrip("/")
        self.publishable_key = publishable_key
        self.service_role_key = service_role_key

    def request(self, method: str, path: str, *, key: str, token: str | None = None,
                payload: dict | list | None = None, prefer: str | None = None):
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {token or key}",
            "Accept": "application/json",
        }
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload).encode("utf-8")
        if prefer:
            headers["Prefer"] = prefer
        req = Request(self.url + path, data=body, headers=headers, method=method)
        try:
            with urlopen(req, timeout=30) as response:
                raw = response.read()
                status = response.status
        except HTTPError as exc:
            raw = exc.read()
            status = exc.code
        except URLError as exc:
            raise SmokeTestError(f"Supabase endpoint unavailable ({type(exc.reason).__name__}).") from exc
        if not raw:
            return status, None
        try:
            return status, json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return status, None

    def admin(self, method: str, path: str, payload: dict | None = None):
        return self.request(
            method, path, key=self.service_role_key,
            token=self.service_role_key, payload=payload,
        )

    def auth(self, method: str, path: str, payload: dict, token: str | None = None):
        return self.request(
            method, path, key=self.publishable_key, token=token,
            payload=payload,
        )

    def rest(self, method: str, path: str, *, token: str, payload=None):
        return self.request(
            method, "/rest/v1/" + path,
            key=self.publishable_key, token=token,
            payload=payload, prefer="return=minimal",
        )

    def create_user(self, role: str, marker: str, *, spoof_user_metadata: bool = False):
        email = f"{marker}-{role}-{uuid.uuid4().hex[:8]}@example.invalid"
        password = secrets.token_urlsafe(24)
        metadata = {"role": "admin"} if spoof_user_metadata else {"role": role}
        status, result = self.admin("POST", "/auth/v1/admin/users", {
            "email": email,
            "password": password,
            "email_confirm": True,
            "app_metadata": {"role": role},
            "user_metadata": metadata,
        })
        if status not in (200, 201) or not isinstance(result, dict) or not result.get("id"):
            raise SmokeTestError(f"Could not create disposable {role} test user (HTTP {status}).")
        status, session = self.auth(
            "POST", "/auth/v1/token?grant_type=password",
            {"email": email, "password": password},
        )
        if status != 200 or not isinstance(session, dict) or not session.get("access_token"):
            raise SmokeTestError(f"Could not sign in disposable {role} test user (HTTP {status}).")
        claims = _jwt_claims(session["access_token"])
        if claims.get("app_metadata", {}).get("role") != role:
            raise SmokeTestError("Auth-issued JWT does not contain the expected trusted app_metadata.role.")
        if claims.get("user_metadata", {}).get("role") == "admin" and role != "admin":
            if claims.get("app_metadata", {}).get("role") != "reader":
                raise SmokeTestError("The user_metadata spoofing fixture is not configured as expected.")
        return {"id": result["id"], "session": session, "claims": claims}

    @staticmethod
    def _expect_status(status: int, expected: tuple[int, ...], operation: str):
        if status not in expected:
            raise SmokeTestError(f"{operation}: expected HTTP {expected}, received {status}.")

    def _get_rows(self, path: str, token: str):
        status, result = self.rest("GET", path, token=token)
        self._expect_status(status, (200,), "PostgREST SELECT")
        return result if isinstance(result, list) else []

    def run(self) -> dict:
        marker = "jarvis_live_" + uuid.uuid4().hex
        admin = self.create_user("admin", marker)
        operator = self.create_user("operator", marker)
        reader = self.create_user("reader", marker)
        spoof = self.create_user("reader", marker, spoof_user_metadata=True)

        admin_token = admin["session"]["access_token"]
        operator_token = operator["session"]["access_token"]
        reader_token = reader["session"]["access_token"]
        spoof_token = spoof["session"]["access_token"]

        # Seed only synthetic rows through service_role on this disposable project.
        lead_name = marker + "_lead"
        market_key = marker + "_market"
        secret_key = marker + "_secret"
        status, _ = self.admin("POST", "/rest/v1/leads", {
            "company_name": lead_name,
        })
        self._expect_status(status, (201,), "Seed lead fixture")
        status, _ = self.admin("POST", "/rest/v1/settings", [
            {"key": market_key, "value": {"country": "HU"}},
            {"key": secret_key, "value": {"fixture": "admin-only"}},
        ])
        self._expect_status(status, (201,), "Seed settings fixtures")

        lead_query = urlencode({"select": "id,company_name", "company_name": f"eq.{lead_name}"})
        for role, token in (
            ("admin", admin_token), ("operator", operator_token),
            ("reader", reader_token), ("spoofed_reader", spoof_token),
        ):
            rows = self._get_rows("leads?" + lead_query, token)
            if len(rows) != 1:
                raise SmokeTestError(f"{role} could not read the shared-workspace lead fixture.")

        # Reader and user_metadata-admin spoof must not gain write access.
        denied_lead = {"company_name": marker + "_reader_write_denied"}
        for role, token in (("reader", reader_token), ("spoofed_reader", spoof_token)):
            status, _ = self.rest("POST", "leads", token=token, payload=denied_lead)
            self._expect_status(status, (401, 403), f"{role} lead INSERT denial")

        # Admin can read all settings; operator only the designated market key; reader none.
        def settings_for(token: str, key_name: str):
            query = urlencode({"select": "key", "key": f"eq.{key_name}"})
            return self._get_rows("settings?" + query, token)

        if len(settings_for(admin_token, market_key)) != 1 or len(settings_for(admin_token, secret_key)) != 1:
            raise SmokeTestError("Admin could not read both settings fixtures.")
        if len(settings_for(operator_token, market_key)) != 1:
            raise SmokeTestError("Operator could not read the lead-research market setting.")
        if settings_for(operator_token, secret_key):
            raise SmokeTestError("Operator read an admin-only setting.")
        if settings_for(reader_token, market_key) or settings_for(reader_token, secret_key):
            raise SmokeTestError("Reader unexpectedly read settings.")
        if settings_for(spoof_token, secret_key):
            raise SmokeTestError("user_metadata.role spoof unexpectedly read an admin-only setting.")

        # Operator may append an audit event but may not read audit history.
        audit_action = marker + "_operator_append"
        status, _ = self.rest("POST", "logs", token=operator_token, payload={
            "module": "live_auth_rls_smoke",
            "message": "Disposable operator append fixture",
            "level": "info",
            "action": audit_action,
            "status": "success",
        })
        self._expect_status(status, (201,), "Operator audit append")
        for role, token in (("operator", operator_token), ("reader", reader_token), ("spoofed_reader", spoof_token)):
            query = urlencode({"select": "id", "action": f"eq.{audit_action}"})
            if self._get_rows("logs?" + query, token):
                raise SmokeTestError(f"{role} unexpectedly read audit history.")
        query = urlencode({"select": "id,actor_user_id", "action": f"eq.{audit_action}"})
        admin_audit = self._get_rows("logs?" + query, admin_token)
        if len(admin_audit) != 1 or admin_audit[0].get("actor_user_id") != operator["id"]:
            raise SmokeTestError("Admin could not verify operator audit append/actor binding.")

        # The hash-chain head is visible to admin only.
        if len(self._get_rows("audit_chain_state?select=singleton", admin_token)) != 1:
            raise SmokeTestError("Admin could not read audit_chain_state.")
        if self._get_rows("audit_chain_state?select=singleton", operator_token):
            raise SmokeTestError("Operator unexpectedly read audit_chain_state.")
        if self._get_rows("audit_chain_state?select=singleton", reader_token):
            raise SmokeTestError("Reader unexpectedly read audit_chain_state.")

        # Refresh must carry server-updated app_metadata into a new signed JWT.
        refreshed_role = "operator"
        status, _ = self.admin("PUT", f"/auth/v1/admin/users/{reader['id']}", {
            "app_metadata": {"role": refreshed_role},
        })
        self._expect_status(status, (200,), "Admin role metadata update")
        old_claims = _jwt_claims(reader_token)
        if old_claims.get("app_metadata", {}).get("role") != "reader":
            raise SmokeTestError("Existing access token unexpectedly changed before refresh.")
        refresh_token = reader["session"].get("refresh_token")
        status, refreshed = self.auth(
            "POST", "/auth/v1/token?grant_type=refresh_token",
            {"refresh_token": refresh_token},
        )
        self._expect_status(status, (200,), "JWT refresh after role change")
        if _jwt_claims(refreshed["access_token"]).get("app_metadata", {}).get("role") != "operator":
            raise SmokeTestError("Refreshed JWT did not contain the updated app_metadata.role.")

        # Logout revokes the refresh token; do not rely on it to instantly invalidate an issued access JWT.
        status, _ = self.auth("POST", "/auth/v1/logout", {}, token=refreshed["access_token"])
        self._expect_status(status, (200, 204), "Auth logout")
        status, _ = self.auth(
            "POST", "/auth/v1/token?grant_type=refresh_token",
            {"refresh_token": refreshed.get("refresh_token", refresh_token)},
        )
        self._expect_status(status, (400, 401), "Refresh token rejection after logout")

        status, _ = self.rest("GET", "leads?select=id", token="not.a.valid.jwt")
        self._expect_status(status, (401,), "Invalid JWT rejection")

        return {
            "project_ref": os.environ["SUPABASE_EXPECTED_PROJECT_REF"],
            "roles_created": ["admin", "operator", "reader", "reader_with_user_metadata_admin_spoof"],
            "checks": [
                "Auth admin user creation and email/password sign-in",
                "real Auth-issued JWT app_metadata role claims",
                "shared lead SELECT and reader INSERT denial",
                "user_metadata role spoofing denied",
                "admin/operator/reader settings visibility",
                "operator audit append and actor_user_id binding",
                "admin-only audit and audit-chain reads",
                "role change observed only after JWT refresh",
                "logout refresh-token revocation",
                "invalid JWT rejected by PostgREST",
            ],
        }


def main() -> int:
    url = os.environ.get("SUPABASE_URL", "")
    publishable = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
    service_role = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    expected_ref = os.environ.get("SUPABASE_EXPECTED_PROJECT_REF", "")
    if not all((url, publishable, service_role, expected_ref)):
        print("Missing live-test configuration; set SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, SUPABASE_SERVICE_ROLE_KEY and SUPABASE_EXPECTED_PROJECT_REF.", file=sys.stderr)
        return 2
    try:
        _validate_target(url, expected_ref)
        result = SupabaseHttp(url, publishable, service_role).run()
    except SmokeTestError as exc:
        print(f"Live Supabase Auth/RLS smoke test failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
