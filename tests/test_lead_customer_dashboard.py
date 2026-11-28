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
