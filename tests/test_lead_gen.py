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
    assert db.inserted[0]["status"] == "new"
    assert events and "1 új lead, 2 kihagyva" in events[0][2]
    assert [item["action"] for item in audits] == [
        "import_reviewed_csv", "create_reviewed_lead",
        "create_reviewed_lead", "import_reviewed_csv",
    ]
    assert [item["status"] for item in audits] == ["pending", "pending", "success", "success"]
    assert audits[1]["operation_id"] == audits[2]["operation_id"]
    assert audits[0]["operation_id"] == audits[3]["operation_id"]
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

    monkeypatch.setattr(lead_gen, "get_service_supabase", lambda: DB())
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



def test_csv_run_does_not_audit_success_without_returned_lead_id(tmp_path, monkeypatch):
    import csv
    import pytest
    import lead_gen

    source = tmp_path / "leads.csv"
    row = _row(email="new@example.com")
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)

    class Result:
        data = []

    class Query:
        def select(self, _columns):
            return self

        def ilike(self, *_args):
            return self

        def limit(self, _limit):
            return self

        def insert(self, _payload):
            return self

        def execute(self):
            return Result()

    class DB:
        def table(self, _name):
            return Query()

    audits = []
    monkeypatch.setattr(lead_gen, "get_service_supabase", lambda: DB())
    monkeypatch.setattr(
        lead_gen, "audit_event",
        lambda *_args, **kwargs: audits.append(kwargs) or True,
    )
    monkeypatch.setattr(lead_gen, "report_error", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="nem igazolta vissza"):
        lead_gen.run(str(source))

    lead_events = [event for event in audits if event["action"] == "create_reviewed_lead"]
    assert [event["status"] for event in lead_events] == ["pending", "unknown"]
    assert lead_events[0]["operation_id"] == lead_events[1]["operation_id"]
    assert all(event["status"] != "success" for event in lead_events)


@pytest.mark.parametrize(
    "email, expected",
    [
        ("plain@example.com", "plain@example.com"),
        ("first_last@example.com", "first\\_last@example.com"),
        ("first%last@example.com", "first\\%last@example.com"),
        (r"first\\last@example.com", r"first\\\\last@example.com"),
    ],
)
def test_csv_duplicate_lookup_escapes_like_pattern_metacharacters(email, expected):
    from lead_gen import _escape_like_literal

    assert _escape_like_literal(email) == expected


def test_csv_duplicate_lookup_passes_escaped_email_to_ilike(tmp_path, monkeypatch):
    import csv
    import lead_gen

    source = tmp_path / "leads.csv"
    row = _row(email="first_last@example.com")
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)

    class Result:
        def __init__(self, data=None):
            self.data = data or []

    class Query:
        def __init__(self, db):
            self.db = db
            self.pattern = None
            self.payload = None

        def select(self, _columns):
            return self

        def ilike(self, _column, pattern):
            self.pattern = pattern
            self.db.patterns.append(pattern)
            return self

        def limit(self, _limit):
            return self

        def insert(self, payload):
            self.payload = payload
            return self

        def execute(self):
            if self.payload is not None:
                self.db.inserted.append(self.payload)
                return Result([{"id": "saved-id"}])
            return Result([])

    class DB:
        def __init__(self):
            self.patterns = []
            self.inserted = []

        def table(self, _name):
            return Query(self)

    db = DB()
    monkeypatch.setattr(lead_gen, "get_service_supabase", lambda: db)
    monkeypatch.setattr(lead_gen, "audit_event", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(lead_gen, "log_event", lambda *_args, **_kwargs: None)

    lead_gen.run(str(source))

    assert db.patterns == [r"first\_last@example.com"]
    assert len(db.inserted) == 1


def test_csv_run_treats_database_unique_violation_as_safe_duplicate_skip(tmp_path, monkeypatch, capsys):
    import csv
    import lead_gen

    source = tmp_path / "leads.csv"
    row = _row(email="race@example.com")
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)

    class UniqueViolation(Exception):
        code = "23505"

    class Result:
        data = []

    class Query:
        def __init__(self):
            self.payload = None

        def select(self, _columns):
            return self

        def ilike(self, *_args):
            return self

        def limit(self, _limit):
            return self

        def insert(self, payload):
            self.payload = payload
            return self

        def execute(self):
            if self.payload is not None:
                raise UniqueViolation("duplicate key value violates unique constraint")
            return Result()

    class DB:
        def table(self, _name):
            return Query()

    audits = []
    monkeypatch.setattr(lead_gen, "get_service_supabase", lambda: DB())
    monkeypatch.setattr(
        lead_gen, "audit_event",
        lambda *_args, **kwargs: audits.append(kwargs) or True,
    )
    monkeypatch.setattr(lead_gen, "log_event", lambda *_args, **_kwargs: None)

    lead_gen.run(str(source))

    lead_events = [event for event in audits if event["action"] == "create_reviewed_lead"]
    assert [event["status"] for event in lead_events] == ["pending", "failed"]
    assert lead_events[0]["operation_id"] == lead_events[1]["operation_id"]
    assert [event["status"] for event in audits if event["action"] == "import_reviewed_csv"] == [
        "pending", "success"
    ]
    assert "0 új, 1 kihagyott rekord" in capsys.readouterr().out
