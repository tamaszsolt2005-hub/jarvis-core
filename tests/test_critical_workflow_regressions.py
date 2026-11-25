"""Critical workflow regressions; all persistence and external transports are mocked.

These tests deliberately avoid live Supabase, IMAP, SMTP, and production records.
"""
from datetime import datetime, timezone

import pytest

import email_sender
import jarvis_common
import lead_gen
import task_actions


class Result:
    def __init__(self, data=None):
        self.data = data or []


class SenderQuery:
    def __init__(self, db):
        self.db = db
        self.operation = None
        self.payload = None
        self.filters = {}

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def select(self, _fields):
        if self.operation is None:
            self.operation = "select"
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def limit(self, _limit):
        return self

    def execute(self):
        if self.operation == "select":
            return Result([{
                "id": "lead-1",
                "status": "sending",
                "email": "person@example.test",
                "consent_basis": "consent",
                "consent_confirmed_at": datetime.now(timezone.utc).isoformat(),
                "approved_to_contact": True,
                "opted_out": False,
                "reply_category": None,
                "last_inbound_message_id": None,
            }])
        self.db.updates.append(self.payload)
        if self.payload and self.payload.get("status") in {"sending", "sent", "follow_up_sent"}:
            return Result([{"id": "lead-1"}])
        return Result([])


class SenderDB:
    def __init__(self):
        self.updates = []

    def table(self, name):
        assert name == "leads"
        return SenderQuery(self)


def _approved_lead():
    return {
        "id": "lead-1",
        "email": "person@example.test",
        "company_name": "Example Ltd",
        "status": "new",
        "consent_basis": "consent",
        "consent_confirmed_at": datetime.now(timezone.utc).isoformat(),
        "approved_to_contact": True,
        "opted_out": False,
        "reply_category": None,
        "last_inbound_message_id": None,
    }


def test_sender_does_not_call_smtp_when_pending_audit_cannot_be_saved(monkeypatch):
    db = SenderDB()
    sent = []
    reported = []

    monkeypatch.setattr(email_sender, "_draft", lambda *_args, **_kwargs: ("Subject", "Body"))
    monkeypatch.setattr(email_sender, "audit_event", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(email_sender, "send_email", lambda *args: sent.append(args))
    monkeypatch.setattr(
        email_sender, "report_error",
        lambda error, **kwargs: reported.append((error, kwargs)),
    )

    result = email_sender._send_one(db, _approved_lead(), False, datetime.now(timezone.utc))

    assert result is False
    assert sent == []
    assert any(update and update.get("status") == "send_error" for update in db.updates)
    assert reported
    assert reported[0][1]["module"] == "email_sender"


def test_sender_does_not_draft_or_send_when_atomic_claim_is_lost(monkeypatch):
    class LostClaimQuery(SenderQuery):
        def execute(self):
            return Result([])

    class LostClaimDB:
        def table(self, name):
            assert name == "leads"
            return LostClaimQuery(self)

    monkeypatch.setattr(
        email_sender, "_draft",
        lambda *_args, **_kwargs: pytest.fail("Draft must not be generated without a claim"),
    )
    monkeypatch.setattr(
        email_sender, "send_email",
        lambda *_args: pytest.fail("SMTP must not be called without a claim"),
    )
    monkeypatch.setattr(email_sender, "audit_event", lambda *_args, **_kwargs: True)

    assert email_sender._send_one(
        LostClaimDB(), _approved_lead(), False, datetime.now(timezone.utc)
    ) is False


def test_task_database_write_failure_is_reported_and_original_error_reraised(monkeypatch):
    database_error = RuntimeError("mock database write failure")
    reports = []

    class BrokenRPC:
        def rpc(self, name, _params):
            assert name == "execute_approved_task_action"
            class Query:
                def execute(self):
                    raise database_error
            return Query()

    monkeypatch.setattr(task_actions, "get_enforced_user_supabase", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        task_actions, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )

    with pytest.raises(RuntimeError) as caught:
        task_actions.execute_task_action(
            BrokenRPC(),
            {
                "type": "create", "title": "Mock task", "priority": "normal",
                "due_at": None, "notes": "",
                "operation_id": "223e4567-e89b-42d3-a456-426614174001",
            },
            approved=True,
            approval={
                "token": "test-one-use-approval-token-that-is-long-enough",
                "principal": "legacy:323e4567-e89b-42d3-a456-426614174002",
            },
        )

    assert caught.value is database_error
    assert len(reports) == 1
    assert reports[0][0] is database_error
    assert reports[0][1]["module"] == "task_actions"
    assert reports[0][1]["severity"] == "critical"


def test_database_read_failure_does_not_break_independent_lead_and_task_logic(monkeypatch):
    reports = []

    class BrokenDB:
        def table(self, _name):
            raise RuntimeError("mock database unavailable")

    monkeypatch.setattr(
        jarvis_common, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )

    assert jarvis_common.get_setting(BrokenDB(), "theme", default="light") == "light"
    assert len(reports) == 1
    assert reports[0][1]["operation"] == "read_setting:theme"

    valid_row = {
        "company_name": "Example Ltd",
        "email": "contact@example.test",
        "consent_basis": "consent",
        "approved_to_contact": "yes",
        "consent_confirmed_at": "2026-11-20T10:00:00+00:00",
    }
    assert lead_gen._validated_import_row(valid_row)["email"] == "contact@example.test"
    assert task_actions.parse_task_command("Új feladat: Regressziós ellenőrzés")["type"] == "create"


def test_sender_success_records_pending_and_success_audit_after_smtp_acceptance(monkeypatch):
    db = SenderDB()
    sent = []
    audit_statuses = []

    monkeypatch.setattr(email_sender, "_draft", lambda *_args, **_kwargs: ("Subject", "Body"))
    monkeypatch.setattr(
        email_sender, "audit_event",
        lambda _db, **kwargs: audit_statuses.append(kwargs["status"]) or True,
    )
    monkeypatch.setattr(email_sender, "send_email", lambda *args: sent.append(args) or "smtp-id")
    monkeypatch.setattr(email_sender, "log_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(email_sender, "report_error", lambda *_args, **_kwargs: pytest.fail("unexpected error"))

    result = email_sender._send_one(db, _approved_lead(), False, datetime.now(timezone.utc))

    assert result is True
    assert sent == [("person@example.test", "Subject", "Body", email_sender.email_idempotency_key(_approved_lead(), False))]
    assert audit_statuses == ["pending", "success"]
    assert any(update and update.get("status") == "sending" for update in db.updates)
    assert any(update and update.get("status") == "sent" for update in db.updates)


def test_sender_smtp_exception_marks_lead_as_error_and_never_reports_success(monkeypatch):
    db = SenderDB()
    reports = []
    audit_statuses = []

    monkeypatch.setattr(email_sender, "_draft", lambda *_args, **_kwargs: ("Subject", "Body"))
    monkeypatch.setattr(
        email_sender, "audit_event",
        lambda _db, **kwargs: audit_statuses.append(kwargs["status"]) or True,
    )
    monkeypatch.setattr(
        email_sender, "send_email",
        lambda *_args: (_ for _ in ()).throw(email_sender.EmailDeliveryOutcomeUnknown("mock SMTP DATA outcome unknown")),
    )
    monkeypatch.setattr(
        email_sender, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )

    result = email_sender._send_one(db, _approved_lead(), False, datetime.now(timezone.utc))

    assert result is False
    assert audit_statuses == ["pending", "unknown"]
    assert any(update and update.get("status") == "send_unknown" for update in db.updates)
    assert len(reports) == 1
    assert reports[0][1]["module"] == "email_sender"


def test_sender_rechecks_opt_out_immediately_before_smtp(monkeypatch):
    class RevokedQuery(SenderQuery):
        def execute(self):
            if self.operation == "select":
                return Result([{
                    "id": "lead-1",
                    "status": "sending",
                    "email": "person@example.test",
                    "consent_basis": "consent",
                    "consent_confirmed_at": datetime.now(timezone.utc).isoformat(),
                    "approved_to_contact": True,
                    "opted_out": True,
                    "reply_category": None,
                    "last_inbound_message_id": None,
                }])
            self.db.updates.append(self.payload)
            return Result([{"id": "lead-1"}] if self.payload.get("status") == "sending" else [])

    class RevokedDB(SenderDB):
        def table(self, name):
            assert name == "leads"
            return RevokedQuery(self)

    db = RevokedDB()
    monkeypatch.setattr(email_sender, "_draft", lambda *_args, **_kwargs: ("Subject", "Body"))
    monkeypatch.setattr(email_sender, "audit_event", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(email_sender, "log_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        email_sender, "send_email",
        lambda *_args: pytest.fail("SMTP must not run after consent is revoked"),
    )

    assert email_sender._send_one(db, _approved_lead(), False, datetime.now(timezone.utc)) is False
    assert any(update and update.get("status") == "send_blocked" for update in db.updates)


def test_follow_up_draft_skips_website_audit_and_adds_opt_out(monkeypatch):
    prompts = []
    monkeypatch.setattr(email_sender, "generate_text", lambda prompt: prompts.append(prompt) or "Tárgy: Követés\nKedves Partner!")
    monkeypatch.setattr(
        email_sender, "audit_company_website",
        lambda *_args: pytest.fail("Follow-up draft must not audit the website"),
    )
    monkeypatch.setattr(email_sender, "get_secret", lambda *_args: "mock offer")

    subject, body = email_sender._draft(_approved_lead(), follow_up=True)

    assert subject == "Követés"
    assert "Kedves Partner" in body
    assert "LEIRATKOZOM" in body
    assert "Example Ltd" in prompts[0]


def test_sender_rejects_wrong_send_mode_before_database_access():
    class ForbiddenDB:
        def table(self, _name):
            pytest.fail("Wrong send mode must not access the database")

    lead = _approved_lead()
    lead["status"] = "sent"
    assert email_sender._send_one(
        ForbiddenDB(), lead, False, datetime.now(timezone.utc)
    ) is False

    lead["status"] = "new"
    assert email_sender._send_one(
        ForbiddenDB(), lead, True, datetime.now(timezone.utc)
    ) is False


def test_sender_rejects_replied_or_invalid_address_before_database_access():
    class ForbiddenDB:
        def table(self, _name):
            pytest.fail("Ineligible lead must not access the database")

    lead = _approved_lead()
    lead["reply_category"] = "reply"
    assert email_sender._send_one(
        ForbiddenDB(), lead, False, datetime.now(timezone.utc)
    ) is False

    lead = _approved_lead()
    lead["email"] = "invalid-address"
    assert email_sender._send_one(
        ForbiddenDB(), lead, False, datetime.now(timezone.utc)
    ) is False


def test_sender_pipeline_selects_only_eligible_leads_and_respects_run_limit(monkeypatch):
    now = datetime.now(timezone.utc)
    valid_new = {
        **_approved_lead(),
        "id": "new-lead",
        "status": "new",
    }
    valid_follow_up = {
        **_approved_lead(),
        "id": "follow-up-lead",
        "status": "sent",
        "next_follow_up_at": (now.replace(year=now.year - 1)).isoformat(),
        "follow_up_count": 0,
        "last_inbound_message_id": None,
    }
    invalid_consent = {
        **_approved_lead(),
        "id": "no-consent",
        "approved_to_contact": False,
    }
    invalid_email = {
        **_approved_lead(),
        "id": "bad-email",
        "email": "not-an-email",
    }

    class Result:
        data = [valid_follow_up, invalid_consent, invalid_email, valid_new]

    class Query:
        def select(self, *_args):
            return self

        def limit(self, _limit):
            return self

        def execute(self):
            return Result()

    class DB:
        def table(self, name):
            assert name == "leads"
            return Query()

    sent = []
    monkeypatch.setattr(email_sender, "EMAIL_DELIVERY_ENABLED", True)
    monkeypatch.setattr(email_sender, "env_bool", lambda _name, _default=False: True)
    monkeypatch.setattr(email_sender, "env_int", lambda name, default, *_args: 2 if name == "SEND_MAX_PER_RUN" else default)
    monkeypatch.setattr(email_sender, "get_service_supabase", lambda: DB())
    monkeypatch.setattr(email_sender, "score_lead", lambda _lead: 1)
    monkeypatch.setattr(
        email_sender, "_send_one",
        lambda _db, lead, follow_up, _now: sent.append((lead["id"], follow_up)) or True,
    )
    monkeypatch.setattr(email_sender.time, "sleep", lambda *_args: None)

    email_sender._run()

    assert sent == [("new-lead", False), ("follow-up-lead", True)]
