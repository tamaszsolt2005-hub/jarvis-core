from __future__ import annotations

from types import SimpleNamespace

import pytest


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def select(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


class _DB:
    def __init__(self, tables):
        self.tables = tables
        self.rpc_calls = []

    def table(self, name):
        return _Query(self.tables.get(name, []))

    def rpc(self, name, payload):
        self.rpc_calls.append((name, payload))
        return SimpleNamespace(execute=lambda: SimpleNamespace(data={"ok": True}))


class _Context:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def metric(self, *_args, **_kwargs):
        pass


class _UI:
    def __init__(self):
        self.messages = []
        self.session_state = {}

    def __getattr__(self, name):
        if name in {
            "title", "caption", "info", "error", "warning", "success",
            "markdown", "write", "divider", "metric",
        }:
            return lambda *args, **kwargs: self.messages.append((name, args))
        if name in {"container", "form", "expander"}:
            return lambda *args, **kwargs: _Context()
        raise AttributeError(name)

    def tabs(self, labels):
        return [_Context() for _ in labels]

    def columns(self, spec, **_kwargs):
        count = spec if isinstance(spec, int) else len(spec)
        return [_Context() for _ in range(count)]

    def selectbox(self, _label, *, options, index=0, **_kwargs):
        return options[index]

    def text_input(self, *_args, **_kwargs):
        return ""

    def text_area(self, *_args, **_kwargs):
        return ""

    def form_submit_button(self, *_args, **_kwargs):
        return False

    def button(self, *_args, **_kwargs):
        return False

    def link_button(self, *args, **kwargs):
        self.messages.append(("link_button", args))

    def dataframe(self, *args, **kwargs):
        self.messages.append(("dataframe", args))

    def rerun(self):
        self.messages.append(("rerun", ()))


def test_email_draft_parser_handles_explicit_headers_fallback_and_bounds():
    from lead_email_dashboard import _split_draft

    subject, body = _split_draft("Tárgy: Rövid bemutatkozás\n\nTisztelt Partner! Ez egy levél.")
    assert subject == "Rövid bemutatkozás"
    assert body.startswith("Tisztelt Partner!")
    subject, body = _split_draft("A lehetséges együttműködés\nLevél törzse")
    assert subject == "A lehetséges együttműködés"
    assert body == "Levél törzse"
    subject, body = _split_draft("Ez egy teljes levél, amelynek az első mondata ponttal végződik.\nFolytatás")
    assert subject == "Egy lehetséges fejlesztési irány a vállalatuk számára"
    assert body.startswith("Ez egy teljes levél")
    subject, body = _split_draft("Subject: " + "x" * 250 + "\n\n" + "y" * 21000)
    assert len(subject) == 200
    assert len(body) == 20000


def test_email_rows_tolerate_non_list_and_filter_malformed_records():
    from lead_email_dashboard import _rows

    assert _rows(_DB({"leads": "unexpected"}), "leads", "*") == []
    assert _rows(_DB({"leads": [{"id": "1"}, None, "bad", {"id": "2"}]}), "leads", "*") == [
        {"id": "1"}, {"id": "2"},
    ]


def test_email_center_read_only_renders_inbox_drafts_approvals_permissions_and_feedback(monkeypatch):
    import lead_email_dashboard as email

    ui = _UI()
    monkeypatch.setattr(email, "st", ui)
    db = _DB({
        "leads": [{"id": "lead-1", "company_name": "Example Ltd", "website": "https://example.com", "notes": "Public company notes"}],
        "lead_review_states": [{"lead_id": "lead-1", "review_status": "approved"}],
        "lead_email_drafts": [
            {"id": "draft-1", "lead_id": "lead-1", "subject": "Draft subject", "body": "Draft body text", "recipient_email": "sales@example.com", "recipient_source_url": "https://example.com/team", "status": "draft"},
            {"id": "draft-2", "lead_id": "lead-1", "subject": "Approved subject", "body": "Approved body", "recipient_email": "sales@example.com", "recipient_source_url": "https://example.com/team", "status": "approved", "approved_at": "2026-11-27"},
            {"id": "draft-3", "lead_id": "lead-1", "subject": "Rejected subject", "body": "Rejected body", "status": "rejected"},
        ],
        "email_style_preferences": [{"scope": "global", "formality": "neutral", "concision": "short", "personalization": "high", "assertiveness": "balanced"}],
        "company_research_snapshots": [{
            "lead_id": "lead-1", "researched_at": "2026-11-27",
            "dossier": {"facts": [{"category": "Hiring", "fact": "Hiring engineers", "source_url": "https://example.com/jobs"}]},
        }],
        "lead_email_draft_revisions": [{"id": "rev-1", "draft_id": "draft-1", "subject": "Earlier subject", "body": "Earlier body", "created_at": "2026-11-26"}],
        "lead_email_contact_permissions": [{"lead_id": "lead-1", "email_normalized": "sales@example.com", "status": "authorized", "legal_basis": "explicit_consent", "evidence_note": "Verified consent", "verified_at": "2026-11-27"}],
        "email_suppression_list": [{"email_normalized": "blocked@example.com", "reason": "unsubscribe", "note": "Opted out"}],
        "lead_email_send_queue": [{"id": "queue-1", "draft_id": "draft-2", "lead_id": "lead-1", "recipient_email": "sales@example.com", "status": "blocked", "block_reason": "Missing final review", "evaluated_at": "2026-11-27"}],
        "logs": [{"module": "email_inbox", "level": "INFO", "message": "ÜGYFÉL VÁLASZ: kategória=interested", "created_at": "2026-11-27T10:00:00Z"}],
        "email_style_feedback": [{"category": "too_long", "note": "Use shorter paragraphs", "created_at": "2026-11-27"}],
    })

    email.render_email_center(
        db, auth_enabled=True, role="reader",
        generate_text_fn=None, model_name_fn=lambda: "test-model",
    )

    rendered = " ".join(str(args) for _, args in ui.messages)
    assert "Érdeklődő ügyfél válaszolt" in rendered
    assert "Draft body text" in rendered
    assert "Earlier subject" in rendered
    assert "Approved subject" in rendered
    assert "Rejected subject" in rendered
    assert "Missing final review" in rendered
    assert "Túl hosszú" in rendered
    assert "Küldés nincs bekapcsolva" in rendered
    assert db.rpc_calls == []


def test_email_center_reports_primary_data_failure_without_exposing_exception(monkeypatch):
    import lead_email_dashboard as email

    class BrokenDB:
        def table(self, _name):
            raise OSError("sensitive connection details")

    ui = _UI()
    monkeypatch.setattr(email, "st", ui)
    email.render_email_center(
        BrokenDB(), auth_enabled=False, role=None,
        generate_text_fn=None, model_name_fn=lambda: "test-model",
    )
    rendered = " ".join(str(args) for _, args in ui.messages)
    assert "adatforrása nem érhető el" in rendered
    assert "OSError" in rendered
    assert "sensitive connection details" not in rendered


def test_crm_due_date_parser_accepts_optional_iso_date_and_rejects_invalid_calendar_dates():
    from lead_customer_dashboard import _parse_due_date

    assert _parse_due_date("") is None
    assert _parse_due_date(" 2026-12-01 ") == "2026-12-01"
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        _parse_due_date("2026/12/01")
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        _parse_due_date("2026-02-30")


def test_crm_admin_page_renders_edit_forms_without_submitting_or_writing(monkeypatch):
    import lead_customer_dashboard as crm

    ui = _UI()
    monkeypatch.setattr(crm, "st", ui)
    db = _DB({
        "leads": [{"id": "lead-1", "company_name": "Example Ltd", "website": "https://example.com"}],
        "lead_review_states": [{"lead_id": "lead-1", "review_status": "approved"}],
        "lead_customer_lifecycle": [{"lead_id": "lead-1", "stage": "qualified", "next_action": "Discovery", "next_action_due": "2026-12-01"}],
        "lead_customer_lifecycle_events": [],
    })

    crm.render_lead_customer_page(db, auth_enabled=True, role="admin")

    rendered = " ".join(str(args) for _, args in ui.messages)
    assert "Ügyfélkapcsolatok" in rendered
    assert "Example Ltd" in rendered
    assert "Életciklus-státusz módosítása" in rendered
    assert "Ügyfélinterakció rögzítése" in rendered
    assert "Következő teendő beállítása" in rendered
    assert db.rpc_calls == []


def test_research_enqueue_rejects_lead_without_company_name_before_loading_runtime_config():
    from lead_research_actions import LeadResearchRequestError, enqueue_single_lead_research

    class LeadOnlyDB:
        def table(self, _name):
            return _Query([{"id": "lead-1", "company_name": "  "}])

    with pytest.raises(LeadResearchRequestError, match="lead_company_name_missing"):
        enqueue_single_lead_research(
            "lead-1", auth_session={"token": "fresh"},
            authorize_user=lambda _session: {"role": "admin"},
            service_client_factory=LeadOnlyDB,
        )
