from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from scripts.supabase_auth_rls_smoke import (
    PRODUCTION_PROJECT_REF,
    SmokeTestError,
    _jwt_claims,
    _validate_target,
)


def _token(payload: dict) -> str:
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return "header." + encoded + ".signature"


def test_jwt_claim_decoder_reads_app_metadata_role():
    claims = _jwt_claims(_token({"app_metadata": {"role": "operator"}, "exp": 2_000_000_000}))
    assert claims["app_metadata"]["role"] == "operator"


@pytest.mark.parametrize(
    ("url", "ref"),
    [
        ("https://kiutreccucbegskxowek.supabase.co", PRODUCTION_PROJECT_REF),
        ("http://testproject.supabase.co", "testproject"),
        ("https://otherproject.supabase.co", "testproject"),
        ("not-a-url", "testproject"),
    ],
)
def test_live_test_target_guard_rejects_production_or_mismatched_project(url, ref):
    with pytest.raises(SmokeTestError):
        _validate_target(url, ref)


def test_live_test_target_guard_accepts_explicit_nonproduction_project():
    _validate_target("https://jarvis-test-branch.supabase.co", "jarvis-test-branch")


def test_live_auth_workflow_requires_isolated_environment_and_secret_key():
    workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "supabase-auth-rls-live.yml").read_text()
    assert "environment: supabase-integration" in workflow
    assert "JARVIS_TEST_SUPABASE_SERVICE_ROLE_KEY" in workflow
    assert "JARVIS_TEST_SUPABASE_PROJECT_REF" in workflow



def test_live_smoke_uses_the_policy_designated_market_key_and_cleans_fixtures():
    source = (Path(__file__).resolve().parents[1] / "scripts" / "supabase_auth_rls_smoke.py").read_text()
    assert 'market_key = "lead_research_market"' in source
    assert 'market_key = marker + "_market"' not in source
    assert "def _cleanup(" in source
    assert "finally:" in source
    assert "self._cleanup(lead_name, secret_key, market_created)" in source
    assert "/auth/v1/admin/users/" in source
    assert "/rest/v1/leads?company_name=eq." in source


def test_live_smoke_exercises_database_backed_approval_rpcs_and_role_denial():
    source = (Path(__file__).resolve().parents[1] / "scripts" / "supabase_auth_rls_smoke.py").read_text()
    assert '"rpc/issue_pending_approval"' in source
    assert '"rpc/consume_pending_approval"' in source
    assert '"Operator direct approval issuance denial"' in source
    assert '"Server-only approval issuance"' in source
    assert '"Reader task approval denial"' in source
    assert 'prefer="return=representation"' in source
    workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "supabase-auth-rls-live.yml").read_text()
    assert "cancel-in-progress: false" in workflow


def test_live_smoke_cleanup_preserves_existing_market_setting_and_only_removes_test_owned_rows():
    source = (Path(__file__).resolve().parents[1] / "scripts" / "supabase_auth_rls_smoke.py").read_text()
    assert "market_created = not (isinstance(existing_market, list) and existing_market)" in source
    assert "if market_created:" in source
    assert 'quote(secret_key, safe="")' in source
