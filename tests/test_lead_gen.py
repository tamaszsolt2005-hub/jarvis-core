import pytest

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


def test_csv_run_imports_only_valid_non_duplicate_rows(tmp_path, monkeypatch, capsys):
    import csv
    import lead_gen

    source = tmp_path / "leads.csv"
    rows = [
        _row(email="new@example.com"),
        _row(email="existing@example.com"),
        _row(email="bad", approved_to_contact="no"),
    ]
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    class DB:
        def __init__(self):
            self.inserted = []

    db = DB()

    def fake_upsert(_db, **kwargs):
        if kwargs["email"] == "existing@example.com":
            return {
                "lead_id": "existing-id",
                "outcome": "existing",
                "selected_email": kwargs["email"],
            }
        db.inserted.append(kwargs)
        return {
            "lead_id": "new-id",
            "outcome": "created",
            "selected_email": kwargs["email"],
        }

    monkeypatch.setattr(lead_gen, "upsert_company_lead", fake_upsert)
    events, audits = [], []
    monkeypatch.setattr(lead_gen, "get_service_supabase", lambda: db)
    monkeypatch.setattr(
        lead_gen, "audit_event",
        lambda *args, **kwargs: audits.append(kwargs) or True,
    )
    monkeypatch.setattr(lead_gen, "log_event", lambda *args: events.append(args))

    lead_gen.run(str(source))

    assert len(db.inserted) == 1
    assert db.inserted[0]["email"] == "new@example.com"
    assert db.inserted[0]["approved_to_contact"] is True
    assert events and "2 kapcsolattartói rekord feldolgozva, 1 kihagyva" in events[0][2]
    assert [item["action"] for item in audits] == [
        "import_reviewed_csv", "create_reviewed_lead",
        "create_reviewed_lead", "create_reviewed_lead",
        "create_reviewed_lead", "import_reviewed_csv",
    ]
    assert [item["status"] for item in audits] == ["pending", "pending", "success", "pending", "success", "success"]
    assert audits[1]["operation_id"] == audits[2]["operation_id"]
    assert audits[3]["operation_id"] == audits[4]["operation_id"]
    assert audits[0]["operation_id"] == audits[-1]["operation_id"]
    assert "Import kész: 2 kapcsolattartói rekord feldolgozva, 1 kihagyva." in capsys.readouterr().out


def test_csv_run_reports_and_reraises_insert_failure(tmp_path, monkeypatch):
    import csv
    import lead_gen

    source = tmp_path / "leads.csv"
    row = _row(email="new@example.com")
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)

    database_error = RuntimeError("mock insert failure")
    reports = []

    class DB:
        pass

    monkeypatch.setattr(lead_gen, "get_service_supabase", lambda: DB())
    monkeypatch.setattr(
        lead_gen, "upsert_company_lead",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(database_error),
    )
    monkeypatch.setattr(lead_gen, "audit_event", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        lead_gen, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )

    import pytest
    with pytest.raises(RuntimeError, match="mock insert failure"):
        lead_gen.run(str(source))

    assert reports[0][0] is database_error
    assert reports[0][1]["module"] == "lead_gen"
    assert reports[0][1]["severity"] == "error"

