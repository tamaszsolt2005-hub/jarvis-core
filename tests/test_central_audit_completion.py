"""Fail-closed lifecycle tests for the shared operational audit trail."""
from email.message import EmailMessage

import pytest


def test_lead_csv_import_stops_before_database_writes_when_pending_audit_fails(tmp_path, monkeypatch):
    import lead_gen

    source = tmp_path / "leads.csv"
    source.write_text("company_name,email,consent_basis,approved_to_contact,consent_confirmed_at\n", encoding="utf-8")

    class DB:
        def table(self, _name):
            raise AssertionError("lead DB access must not happen without pending audit")

    events = []
    monkeypatch.setattr(lead_gen, "get_service_supabase", lambda: DB())
    monkeypatch.setattr(lead_gen, "audit_event", lambda _db, **kwargs: events.append(kwargs) or False)
    monkeypatch.setattr(lead_gen, "report_error", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="pending audit"):
        lead_gen.run(str(source))

    assert events[0]["status"] == "pending"
    assert events[0]["action"] == "import_reviewed_csv"
    assert events[-1]["status"] == "failed"


def test_global_research_automation_stops_when_pending_audit_fails(monkeypatch):
    import global_lead_research_job as job

    events = []
    monkeypatch.setattr(job, "get_service_supabase", lambda: object())
    monkeypatch.setattr(job, "audit_event", lambda _db, **kwargs: events.append(kwargs) or False)
    monkeypatch.setattr(job, "research_global_companies", lambda *_args, **_kwargs: pytest.fail("research must not start"))
    monkeypatch.setattr(job, "report_error", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="pending audit"):
        job.main()

    assert events[0]["status"] == "pending"
    assert events[0]["action"] == "daily_global_research"
    assert events[-1]["status"] == "failed"


def test_inbound_email_does_not_change_lead_when_pending_audit_fails(monkeypatch):
    import email_inbox

    message = EmailMessage()
    message["Message-ID"] = "<inbound-1@example.test>"
    message["From"] = "contact@example.test"
    message["Subject"] = "Visszajelzés"
    message.set_content("Köszönöm, megkaptam.")
    lead = {
        "id": "lead-1",
        "email": "contact@example.test",
        "status": "sent",
        "opted_out": False,
        "last_inbound_message_id": None,
    }

    class Result:
        def __init__(self, data=None):
            self.data = data or []

    class Query:
        def __init__(self, table):
            self.table_name = table
            self.payload = None

        @property
        def not_(self):
            return self

        def select(self, *_args):
            return self

        def eq(self, *_args):
            return self

        def limit(self, *_args):
            return self

        def is_(self, *_args):
            return self

        def update(self, payload):
            self.payload = payload
            raise AssertionError("lead update must not happen without pending audit")

        def execute(self):
            return Result([] if self.table_name == "settings" else [lead])

    class DB:
        def table(self, name):
            return Query(name)

    class Mailbox:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def login(self, *_args):
            return "OK", []

        def select(self, *_args, **_kwargs):
            return "OK", []

        def uid(self, operation, *_args):
            if operation == "search":
                return "OK", [b"1"]
            return "OK", [(b"1 (RFC822)", message.as_bytes())]

        def response(self, _name):
            return "UIDVALIDITY", [b"77"]

    monkeypatch.setattr(email_inbox, "env_bool", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(email_inbox, "get_secret", lambda _name, default=None: default)
    monkeypatch.setattr(email_inbox, "required_secret", lambda _name: "test-only")
    monkeypatch.setattr(email_inbox, "get_service_supabase", lambda: DB())
    monkeypatch.setattr(email_inbox.imaplib, "IMAP4_SSL", lambda *_args: Mailbox())
    monkeypatch.setattr(email_inbox, "audit_event", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(email_inbox, "report_error", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="pending audit"):
        email_inbox._run()



def test_individual_lead_insert_stops_when_its_own_pending_audit_fails(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    import csv
    import lead_gen

    source = tmp_path / "one-lead.csv"
    row = {
        "company_name": "Példa Kft.",
        "email": "contact@example.test",
        "consent_basis": "consent",
        "approved_to_contact": "yes",
        "consent_confirmed_at": datetime.now(timezone.utc).isoformat(),
    }
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)

    class Result:
        data = []

    class Query:
        def __init__(self, db):
            self.db = db
            self.payload = None

        def select(self, *_args):
            return self

        def ilike(self, *_args):
            return self

        def limit(self, *_args):
            return self

        def insert(self, payload):
            self.payload = payload
            return self

        def execute(self):
            if self.payload is not None:
                self.db.inserted.append(self.payload)
            return Result()

    class DB:
        def __init__(self):
            self.inserted = []

        def table(self, _name):
            return Query(self)

    db = DB()
    audits = []

    def audit(_db, **kwargs):
        audits.append(kwargs)
        return kwargs["action"] != "create_reviewed_lead"

    monkeypatch.setattr(lead_gen, "get_service_supabase", lambda: db)
    monkeypatch.setattr(lead_gen, "audit_event", audit)
    monkeypatch.setattr(lead_gen, "report_error", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="pending audit"):
        lead_gen.run(str(source))

    assert db.inserted == []
    assert [item["status"] for item in audits] == ["pending", "pending", "failed", "failed"]
    assert audits[1]["operation_id"] == audits[2]["operation_id"]
