import pytest

from datetime import date

from lead_customer_dashboard import _is_overdue, _parse_due_date


def test_crm_due_date_accepts_iso_date_and_optional_empty_value():
    assert _parse_due_date("2026-12-01") == "2026-12-01"
    assert _parse_due_date("") is None


@pytest.mark.parametrize("value", ["tomorrow", "2026-13-01", "2026-02-30", "20261201"])
def test_crm_due_date_rejects_invalid_date(value):
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        _parse_due_date(value)



def test_crm_overdue_follow_up_requires_action_and_past_due_date():
    today = date(2026, 11, 28)
    assert _is_overdue(
        {"next_action": "Call customer", "next_action_due": "2026-11-27"},
        today=today,
    )
    assert not _is_overdue(
        {"next_action": "Call customer", "next_action_due": "2026-11-28"},
        today=today,
    )
    assert not _is_overdue(
        {"next_action": "", "next_action_due": "2026-11-27"},
        today=today,
    )
    assert not _is_overdue(
        {"next_action": "Call customer", "next_action_due": "not-a-date"},
        today=today,
    )



def test_crm_owner_assignment_migration_is_fail_closed_and_audited():
    from pathlib import Path

    migration = Path(
        "supabase/migrations/20261128120000_crm_owner_assignment.sql"
    ).read_text(encoding="utf-8")
    assert "REFERENCES auth.users(id) ON DELETE SET NULL" in migration
    assert "u.confirmed_at IS NOT NULL" in migration
    assert "u.raw_app_meta_data ->> 'role'" in migration
    assert "crm_user_directory_requires_admin_or_operator" in migration
    assert "crm_owner_assignment_requires_admin_or_operator" in migration
    assert "crm_owner_assignment_target_not_assignable" in migration
    assert "owner_assigned" in migration
    assert "REVOKE ALL ON FUNCTION public.assign_lead_customer_owner" in migration
    assert "GRANT EXECUTE ON FUNCTION public.assign_lead_customer_owner" in migration


@pytest.mark.parametrize(
    ("state", "selected_owner", "expected"),
    [
        ({"assigned_to": "operator-1"}, "all", True),
        ({"assigned_to": "operator-1"}, "operator-1", True),
        ({"assigned_to": "operator-1"}, "operator-2", False),
        ({}, "unassigned", True),
        ({"assigned_to": None}, "unassigned", True),
        ({"assigned_to": "operator-1"}, "unassigned", False),
    ],
)
def test_crm_owner_filter_matches_assigned_and_unassigned_records(state, selected_owner, expected):
    from lead_customer_dashboard import _matches_owner_filter

    assert _matches_owner_filter(state, selected_owner) is expected


def test_crm_inbound_reply_is_a_structured_lifecycle_event_and_advances_responded_stage():
    from pathlib import Path

    migration = Path(
        "supabase/migrations/20261128130000_crm_inbound_reply_events.sql"
    ).read_text(encoding="utf-8")
    assert "record_crm_inbound_reply" in migration
    assert "source_message_id" in migration
    assert "inbound_reply_recorded" in migration
    assert "GRANT EXECUTE ON FUNCTION public.record_crm_inbound_reply" in migration
    assert "TO service_role" in migration
    assert "TO authenticated" not in migration
