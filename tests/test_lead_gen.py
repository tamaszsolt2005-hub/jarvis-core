from lead_gen import _validated_import_row


def _row(**overrides):
    row = {
        "company_name": "Példa Kft.",
        "email": "Contact@Example.com",
        "consent_basis": "consent",
        "approved_to_contact": "yes",
        "consent_confirmed_at": "2026-11-17T10:00:00+01:00",
        "website": "https://example.com",
        "notes": "Reviewed",
        "source": "reviewed_csv",
    }
    row.update(overrides)
    return row


def test_csv_import_normalizes_email_and_requires_timestamped_consent():
    result = _validated_import_row(_row())
    assert result["email"] == "contact@example.com"
    assert result["approved_to_contact"] is True
    assert result["consent_basis"] == "consent"
    assert result["status"] == "new"


def test_csv_import_rejects_missing_consent_and_approval():
    assert _validated_import_row(_row(consent_basis="legitimate_interest")) is None
    assert _validated_import_row(_row(approved_to_contact="no")) is None


def test_csv_import_rejects_naive_or_invalid_timestamp():
    assert _validated_import_row(_row(consent_confirmed_at="2026-11-17T10:00:00")) is None
    assert _validated_import_row(_row(consent_confirmed_at="not-a-date")) is None


def test_csv_import_rejects_invalid_email_or_empty_company():
    assert _validated_import_row(_row(email="not-an-email")) is None
    assert _validated_import_row(_row(email="a" * 245 + "@example.com")) is None
    assert _validated_import_row(_row(company_name=" ")) is None


def test_csv_import_rejects_future_consent_opt_out_and_existing_reply():
    from datetime import datetime, timedelta, timezone

    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    assert _validated_import_row(_row(consent_confirmed_at=future)) is None
    assert _validated_import_row(_row(opted_out="true")) is None
    assert _validated_import_row(_row(reply_category="opt_out")) is None
    assert _validated_import_row(_row(last_inbound_message_id="<reply>")) is None


def test_csv_import_bounds_free_text_fields():
    result = _validated_import_row(_row(notes="x" * 5000, website="https://example.com/" + "x" * 3000))
    assert len(result["notes"]) == 4000
    assert len(result["website"]) == 2048
