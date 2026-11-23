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

    class Result:
        def __init__(self, data=None):
            self.data = data or []

    class Query:
        def __init__(self, db):
            self.db = db
            self.email = None
            self.payload = None

        def select(self, _columns):
            return self

        def ilike(self, _column, email):
            self.email = email
            return self

        def limit(self, _limit):
            return self

        def insert(self, payload):
            self.payload = payload
            return self

        def execute(self):
            if self.payload is not None:
                self.db.inserted.append(self.payload)
                return Result([{"id": "new-id"}])
            return Result([{"id": "existing-id"}] if self.email == "existing@example.com" else [])

    class DB:
        def __init__(self):
            self.inserted = []

        def table(self, _name):
            return Query(self)

    db = DB()
    events = []
    monkeypatch.setattr(lead_gen, "get_supabase", lambda: db)
    monkeypatch.setattr(lead_gen, "audit_event", lambda *args, **kwargs: True)
    monkeypatch.setattr(lead_gen, "log_event", lambda *args: events.append(args))

    lead_gen.run(str(source))

    assert len(db.inserted) == 1
    assert db.inserted[0]["email"] == "new@example.com"
    assert db.inserted[0]["status"] == "new"
    assert events and "1 új lead, 2 kihagyva" in events[0][2]
    assert "Import kész: 1 új, 2 kihagyott rekord." in capsys.readouterr().out


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

    class Result:
        data = []

    class Query:
        def select(self, _columns):
            return self

        def ilike(self, *_args):
            return self

        def limit(self, _limit):
            return self

        def execute(self):
            return Result()

        def insert(self, _payload):
            return self

    class DB:
        def table(self, _name):
            class InsertQuery(Query):
                def execute(self):
                    raise database_error
            return InsertQuery()

    monkeypatch.setattr(lead_gen, "get_supabase", lambda: DB())
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
