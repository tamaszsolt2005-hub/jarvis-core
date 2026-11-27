import pytest

from lead_customer_dashboard import _parse_due_date


def test_crm_due_date_accepts_iso_date_and_optional_empty_value():
    assert _parse_due_date("2026-12-01") == "2026-12-01"
    assert _parse_due_date("") is None


@pytest.mark.parametrize("value", ["tomorrow", "2026-13-01", "2026-02-30", "20261201"])
def test_crm_due_date_rejects_invalid_date(value):
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        _parse_due_date(value)
