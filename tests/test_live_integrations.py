"""Opt-in, read-only live integration smoke tests.

Enable explicitly with JARVIS_LIVE_INTEGRATION_TESTS=1 in a trusted environment
that already has the normal server-side JARVIS secrets configured. These tests
never write business data, send email, or modify checkpoints.
"""
import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("JARVIS_LIVE_INTEGRATION_TESTS") != "1",
    reason="Live integrations are opt-in; set JARVIS_LIVE_INTEGRATION_TESTS=1.",
)


def test_live_supabase_read_only_connection():
    from jarvis_common import get_supabase

    db = get_supabase()
    result = db.table("logs").select("level").limit(1).execute()
    assert result is not None


def test_live_gemini_minimal_generation():
    from jarvis_common import get_gemini_client, get_model_name

    client = get_gemini_client()
    response = client.models.generate_content(
        model=get_model_name(),
        contents="Reply with exactly: OK",
    )
    assert (getattr(response, "text", None) or "").strip()
