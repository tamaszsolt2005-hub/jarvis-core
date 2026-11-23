"""Final focused checks for remaining mail, research, backup and redirect failure paths."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_email_sender_success_audit_failure_is_marked_unknown_after_smtp(monkeypatch):
    import email_sender
    from test_email_sender_coverage_edges import _DB, _lead, _configure

    db = _DB([_lead()])
    statuses, reports = [], []

    def audit(*_args, **kwargs):
        statuses.append(kwargs["status"])
        return kwargs["status"] != "success"

    _configure(monkeypatch, db, audit=audit)
    monkeypatch.setattr(
        email_sender, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )

    assert email_sender._send_one(db, db.rows[0], False, email_sender.datetime.now(email_sender.timezone.utc)) is False
    assert statuses == ["pending", "success", "unknown"]
    # SMTP was accepted and the DB status was updated before audit persistence failed.
    assert db.rows[0]["status"] == "sent"
    assert reports[0][1]["operation"] == "send_one"


def test_email_sender_reports_critical_when_send_error_state_cannot_be_persisted(monkeypatch):
    import email_sender
    from test_email_sender_coverage_edges import _DB, _Query, _lead, _configure

    class BrokenQuery(_Query):
        def execute(self):
            if self.operation == "update" and self.values == {"status": "send_error"}:
                raise OSError("mock state recovery failure")
            return super().execute()

    class BrokenDB(_DB):
        def table(self, _name):
            return BrokenQuery(self)

    db = BrokenDB([_lead()])
    reports = []
    _configure(
        monkeypatch, db,
        send=lambda *_args: (_ for _ in ()).throw(OSError("mock SMTP outage")),
    )
    monkeypatch.setattr(
        email_sender, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )

    assert email_sender._send_one(db, db.rows[0], False, email_sender.datetime.now(email_sender.timezone.utc)) is False
    assert any(item[1]["severity"] == "critical" and item[1]["operation"] == "mark_send_error" for item in reports)


def test_email_sender_disabled_gate_does_not_initialize_database(monkeypatch, capsys):
    import email_sender

    monkeypatch.setattr(email_sender, "EMAIL_DELIVERY_ENABLED", False)
    monkeypatch.setattr(email_sender, "env_bool", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        email_sender, "get_service_supabase",
        lambda: (_ for _ in ()).throw(AssertionError("disabled sender must not connect")),
    )
    email_sender._run()
    assert "Biztonsági mód" in capsys.readouterr().out


def test_email_sender_run_reports_and_reraises_unexpected_worker_failure(monkeypatch):
    import email_sender

    reports = []
    monkeypatch.setattr(
        email_sender, "_run",
        lambda: (_ for _ in ()).throw(RuntimeError("mock sender failure")),
    )
    monkeypatch.setattr(
        email_sender, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )
    with pytest.raises(RuntimeError, match="mock sender failure"):
        email_sender.run()
    assert reports[0][1]["operation"] == "run_sender"
    assert reports[0][1]["severity"] == "critical"


def test_global_research_handles_malformed_authority_and_unknown_market_alias():
    from global_lead_research import _valid_http_url, detect_market_change

    assert _valid_http_url("https://[malformed") is None
    assert detect_market_change("válts az Atlantisz piacra") is None


def test_global_research_defaults_when_setting_value_has_unexpected_shape(monkeypatch):
    import global_lead_research as research

    class Query:
        def select(self, *_args):
            return self
        def eq(self, *_args):
            return self
        def limit(self, *_args):
            return self
        def execute(self):
            return SimpleNamespace(data=[{"value": "not-an-object"}])

    class DB:
        def table(self, _name):
            return Query()

    assert research.get_research_market(DB()) == research.DEFAULT_MARKET


def test_global_research_skips_missing_and_ungrounded_company_urls_without_inserts(monkeypatch):
    import global_lead_research as research

    response = SimpleNamespace(
        text=json.dumps({"companies": [
            {
                "company_name": "Missing official URL",
                "website": "",
                "source_url": "https://trusted-source.example/story",
            },
            {
                "company_name": "Unverified source",
                "website": "https://official.example",
                "source_url": "https://not-grounded.example/story",
            },
        ]}),
        candidates=[{
            "grounding_metadata": {
                "grounding_chunks": [
                    {"web": {"uri": "https://official.example/about"}},
                    {"web": {"uri": "https://trusted-source.example/story"}},
                ]
            }
        }],
    )

    class Models:
        def generate_content(self, **_kwargs):
            return response

    class Query:
        def select(self, *_args):
            return self
        def limit(self, *_args):
            return self
        def execute(self):
            return SimpleNamespace(data=[])
        def insert(self, _payload):
            raise AssertionError("unverified research must not be inserted")

    class DB:
        def table(self, _name):
            return Query()

    monkeypatch.setattr(research, "get_model_name", lambda: "test-model")
    monkeypatch.setattr(research, "audit_event", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(research, "log_event", lambda *_args, **_kwargs: None)

    result = research.research_global_companies(
        DB(), "test brief", client=SimpleNamespace(models=Models()),
        max_results=5, market_country="Worldwide",
    )
    assert result["saved_count"] == 0
    assert result["skipped_count"] == 2
    assert result["contact_permission"] == "not_granted"


def test_web_auditor_dns_resolution_error_is_rejected(monkeypatch):
    import socket
    import web_auditor

    monkeypatch.setattr(
        web_auditor.socket, "getaddrinfo",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("mock DNS failure")),
    )
    assert web_auditor._is_public_host("public.example") is False


def test_web_auditor_redirect_without_location_and_redirect_limit_are_closed(monkeypatch):
    import web_auditor

    monkeypatch.setattr(web_auditor, "_is_public_host", lambda _host: True)
    closed = []
    missing = SimpleNamespace(status_code=302, headers={})
    monkeypatch.setattr(web_auditor, "safe_get", lambda *_args, **_kwargs: missing)
    monkeypatch.setattr(web_auditor, "close_response", lambda response: closed.append(response))
    assert "nem adott célcímet" in web_auditor.audit_company_website("https://public.example")
    assert closed == [missing]

    redirect = SimpleNamespace(status_code=302, headers={"Location": "/next"})
    monkeypatch.setattr(web_auditor, "MAX_REDIRECTS", 0)
    monkeypatch.setattr(web_auditor, "safe_get", lambda *_args, **_kwargs: redirect)
    assert "túl sok átirányítást" in web_auditor.audit_company_website("https://public.example")
    assert closed[-1] is redirect


def test_web_auditor_closes_open_response_after_stream_read_failure(monkeypatch):
    import requests
    import web_auditor

    monkeypatch.setattr(web_auditor, "_is_public_host", lambda _host: True)
    response = SimpleNamespace(
        status_code=200,
        headers={"Content-Type": "text/html"},
        raw=SimpleNamespace(read=lambda *_args, **_kwargs: (_ for _ in ()).throw(requests.Timeout("stream timeout"))),
    )
    closed, reports = [], []
    monkeypatch.setattr(web_auditor, "safe_get", lambda *_args, **_kwargs: response)
    monkeypatch.setattr(web_auditor, "close_response", lambda value: closed.append(value))
    monkeypatch.setattr(web_auditor, "report_error", lambda error, **kwargs: reports.append(kwargs))

    result = web_auditor.audit_company_website("https://public.example")

    assert "nem volt elérhető" in result
    assert closed == [response]
    assert reports[0]["severity"] == "warning"


def test_backup_restore_rejects_db_url_identity_permission_and_missing_tools(monkeypatch, tmp_path):
    from scripts import supabase_backup as backup

    target = "abcdefghijklmnopqrst"
    other = "bcdefghijklmnopqrstu"
    archive = tmp_path / "backup.age"
    archive.write_bytes(b"encrypted")
    identity = tmp_path / "identity"
    identity.write_text("private identity")
    monkeypatch.setenv("JARVIS_RESTORE_ALLOWED_PROJECT_REF", target)
    monkeypatch.setenv("AGE_IDENTITY_FILE", str(identity))
    monkeypatch.setattr(backup.shutil, "which", lambda _name: "/usr/bin/mock")

    monkeypatch.setenv(
        "JARVIS_RESTORE_DB_URL",
        f"postgresql://postgres:pw@db.{other}.supabase.co:5432/postgres",
    )
    identity.chmod(0o600)
    with pytest.raises(backup.BackupError, match="DB URL"):
        backup.restore_backup(archive, target, confirmed=True)

    monkeypatch.setenv(
        "JARVIS_RESTORE_DB_URL",
        f"postgresql://postgres:pw@db.{target}.supabase.co:5432/postgres",
    )
    identity.chmod(0o644)
    with pytest.raises(backup.BackupError, match="jogosultsága túl nyitott"):
        backup.restore_backup(archive, target, confirmed=True)

    identity.chmod(0o600)
    monkeypatch.setattr(backup.shutil, "which", lambda name: None if name == "psql" else "/usr/bin/mock")
    with pytest.raises(backup.BackupError, match="age és a psql"):
        backup.restore_backup(archive, target, confirmed=True)
