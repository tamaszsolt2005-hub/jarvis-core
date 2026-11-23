"""Final meaningful coverage pass for remaining defensive branches.

All external effects are replaced with in-memory fakes; no live DB, SMTP or network.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest


def test_dashboard_history_bounds_and_skips_invalid_roles():
    import dashboard

    assert dashboard.format_conversation_history([("system", "ignored")]) == ""
    assert dashboard.format_conversation_history([("user", "x")], max_chars=0) == ""
    result = dashboard.format_conversation_history(
        [("system", "ignore"), ("user", "x" * 100)],
        max_chars=80, max_message_chars=30,
    )
    assert result.startswith("user: ")
    assert len(result) <= 80


def test_dashboard_safe_rows_swallows_error_reporter_failure(monkeypatch):
    import dashboard

    class Query:
        def select(self, *_args):
            return self
        def limit(self, *_args):
            return self
        def execute(self):
            raise OSError("fake read outage")

    class DB:
        def table(self, _name):
            return Query()

    monkeypatch.setattr(
        dashboard, "report_error",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("reporter down")),
    )
    status = {}
    assert dashboard._safe_rows(DB(), "leads", "*", status=status) == []
    assert status == {"ok": False, "error": True, "error_type": "OSError"}


def test_dashboard_public_url_rejects_invalid_ports_without_dns():
    import dashboard

    assert dashboard._public_http_url("https://example.test:70000") is None
    assert dashboard._public_http_url("file:///etc/passwd") is None
    assert dashboard._public_http_url("https://user:pass@example.test") is None


def test_dashboard_website_profile_rejects_unsafe_url_without_request(monkeypatch):
    import dashboard

    monkeypatch.setattr(
        dashboard, "safe_get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not request")),
        raising=False,
    )
    result = dashboard._website_profile("http://localhost/private")
    assert result["score"] == 0
    assert "biztonságos" in result["status"]


def test_dashboard_proactive_signals_ignore_invalid_dates():
    import dashboard

    result = dashboard._proactive_signals(
        [{"status": "open", "due_at": "not-a-date", "title": "bad date"}],
        [{"status": "open", "due_at": "not-a-date", "title": "bad task"}],
    )
    assert isinstance(result, dict)
    assert not result.get("overdue_tasks")


def test_backup_unclassified_subprocess_error_is_sanitized():
    from scripts import supabase_backup as backup

    failure = subprocess.CalledProcessError(
        2, ["pg_dump"], stderr="unexpected private diagnostic token=secret-value\nsecond line"
    )
    with patch.object(backup.subprocess, "run", side_effect=failure):
        with pytest.raises(backup.BackupError) as caught:
            backup.run_checked(["pg_dump"])
    assert "PostgreSQL hiba" in str(caught.value)
    assert "secret-value" not in str(caught.value)


def test_backup_connection_rejects_empty_dns_answer(monkeypatch, tmp_path):
    from scripts import supabase_backup as backup

    monkeypatch.setattr(backup.socket, "getaddrinfo", lambda *_args, **_kwargs: [])
    with pytest.raises(backup.BackupError, match="IPv4-cím"):
        backup._connection_env_and_url(
            "postgresql://postgres:pw@db.example.test/postgres", tmp_path
        )


def test_backup_hashes_empty_file(tmp_path):
    from scripts import supabase_backup as backup

    path = tmp_path / "empty.sql"
    path.write_bytes(b"")
    assert backup.sha256_file(path) == hashlib.sha256(b"").hexdigest()


def test_backup_rejects_directory_member_in_archive(tmp_path):
    import tarfile
    from scripts import supabase_backup as backup

    archive = tmp_path / "directory.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        info = tarfile.TarInfo("manifest.json")
        info.type = tarfile.DIRTYPE
        tar.addfile(info)
    destination = tmp_path / "out"
    destination.mkdir()
    with pytest.raises(backup.BackupError, match="fájlkészlet"):
        backup._safe_extract(archive, destination)


def test_backup_rejects_traversal_member_in_archive(tmp_path):
    import io
    import tarfile
    from scripts import supabase_backup as backup

    archive = tmp_path / "traversal.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name in ("manifest.json", "schema.sql", "data.sql"):
            info = tarfile.TarInfo(name)
            payload = b"{}" if name == "manifest.json" else b"SELECT 1;"
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
        info = tarfile.TarInfo("../escape")
        payload = b"x"
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
    destination = tmp_path / "out"
    destination.mkdir()
    with pytest.raises(backup.BackupError):
        backup._safe_extract(archive, destination)


def test_backup_create_rejects_empty_dump_outputs(monkeypatch, tmp_path):
    from scripts import supabase_backup as backup

    monkeypatch.setenv(
        "SUPABASE_DB_URL",
        "postgresql://postgres:pw@db.kiutreccucbegskxowek.supabase.co:5432/postgres",
    )
    monkeypatch.setenv("BACKUP_AGE_RECIPIENT", "age1mockrecipient")
    monkeypatch.setenv("JARVIS_BACKUP_SOURCE_PROJECT_REF", backup.PRODUCTION_PROJECT_REF)
    monkeypatch.setattr(backup.shutil, "which", lambda _name: "/usr/bin/mock")
    monkeypatch.setattr(
        backup, "_connection_env_and_url",
        lambda *_args: ("postgresql://postgres@db.example.test/postgres", {"PGPASSWORD": "fake"}),
    )
    monkeypatch.setattr(backup, "run_checked", lambda *_args, **_kwargs: "")
    with pytest.raises(backup.BackupError, match="nem készített teljes"):
        backup.create_backup(tmp_path / "private")


def test_backup_create_rejects_missing_encrypted_output(monkeypatch, tmp_path):
    from scripts import supabase_backup as backup

    monkeypatch.setenv(
        "SUPABASE_DB_URL",
        "postgresql://postgres:pw@db.kiutreccucbegskxowek.supabase.co:5432/postgres",
    )
    monkeypatch.setenv("BACKUP_AGE_RECIPIENT", "age1mockrecipient")
    monkeypatch.setenv("JARVIS_BACKUP_SOURCE_PROJECT_REF", backup.PRODUCTION_PROJECT_REF)
    monkeypatch.setattr(backup.shutil, "which", lambda _name: "/usr/bin/mock")
    monkeypatch.setattr(
        backup, "_connection_env_and_url",
        lambda *_args: ("postgresql://postgres@db.example.test/postgres", {"PGPASSWORD": "fake"}),
    )

    def fake_runner(args, **_kwargs):
        if args[0] == "pg_dump":
            Path(args[args.index("--file") + 1]).write_text("mock custom-format dump")
        elif args[0] == "pg_restore":
            Path(args[args.index("--file") + 1]).write_text("-- extracted mock SQL\\n")
        return ""

    monkeypatch.setattr(backup, "run_checked", fake_runner)
    with pytest.raises(backup.BackupError, match="titkosított mentés nem jött létre"):
        backup.create_backup(tmp_path / "private")


def test_backup_restore_rejects_same_source_and_target_before_db_probe(monkeypatch, tmp_path):
    from scripts import supabase_backup as backup

    target_ref = "abcdefghijklmnopqrst"
    monkeypatch.setenv(
        "JARVIS_RESTORE_DB_URL",
        f"postgresql://postgres:pw@db.{target_ref}.supabase.co:5432/postgres",
    )
    monkeypatch.setenv("JARVIS_RESTORE_ALLOWED_PROJECT_REF", target_ref)
    identity = tmp_path / "identity"
    identity.write_text("fake identity")
    identity.chmod(0o600)
    monkeypatch.setenv("AGE_IDENTITY_FILE", str(identity))
    archive = tmp_path / "backup.age"
    archive.write_bytes(b"fake encrypted")
    monkeypatch.setattr(backup.shutil, "which", lambda _name: "/usr/bin/mock")
    monkeypatch.setattr(
        backup, "_safe_extract",
        lambda *_args: {"source_project_ref": target_ref},
    )
    with patch.object(backup, "run_checked", return_value="") as runner:
        with pytest.raises(backup.BackupError, match="forrás és cél projekt"):
            backup.restore_backup(archive, target_ref, confirmed=True)
    assert [call.args[0][0] for call in runner.call_args_list] == ["age"]


def test_backup_main_reports_known_failure_and_exits(monkeypatch):
    from scripts import supabase_backup as backup

    reports = []
    monkeypatch.setattr(backup, "create_backup", lambda *_args: (_ for _ in ()).throw(backup.BackupError("expected")))
    monkeypatch.setattr(backup, "report_error", lambda error, **kwargs: reports.append((error, kwargs)))
    monkeypatch.setattr(sys, "argv", ["supabase_backup.py", "backup"])
    with pytest.raises(SystemExit) as caught:
        backup.main()
    assert caught.value.code == 2
    assert reports[0][1]["severity"] == "error"


def test_backup_main_reports_unexpected_failure_as_critical(monkeypatch):
    from scripts import supabase_backup as backup

    reports = []
    monkeypatch.setattr(backup, "create_backup", lambda *_args: (_ for _ in ()).throw(RuntimeError("unexpected")))
    monkeypatch.setattr(backup, "report_error", lambda error, **kwargs: reports.append((error, kwargs)))
    monkeypatch.setattr(sys, "argv", ["supabase_backup.py", "backup"])
    with pytest.raises(SystemExit) as caught:
        backup.main()
    assert caught.value.code == 2
    assert reports[0][1]["severity"] == "critical"


def test_analytics_fallback_labels_and_empty_sparkline():
    from jarvis_analytics import _activity_label, _module_label, _sparkline_svg

    assert _module_label(None) == "Unknown"
    assert _activity_label({"module": "custom_module", "message": "custom"}) == "Custom Module esemény"
    svg = _sparkline_svg([], "#fff")
    assert "M 4.0,31.0 L 196.0,31.0" in svg


def test_analytics_daily_series_handles_empty_and_filtered_data():
    from jarvis_analytics import _daily_series

    frame = pd.DataFrame({"local_ts": pd.to_datetime([])})
    empty = _daily_series(frame, ["2026-11-22", "2026-11-23"])
    assert list(empty) == [0, 0]
    populated = pd.DataFrame({
        "local_ts": pd.to_datetime(["2026-11-23T10:00:00"]),
        "keep": [False],
    })
    filtered = _daily_series(populated, ["2026-11-23"], populated["keep"])
    assert list(filtered) == [0]


def test_analytics_chat_context_handles_missing_and_invalid_timestamps():
    from jarvis_analytics import build_chat_analytics_context

    missing = build_chat_analytics_context([], now=datetime.now(timezone.utc))
    assert "nem tartalmaz elemezhető" in missing
    invalid = build_chat_analytics_context(
        [{"created_at": "not-a-timestamp"}], now=datetime.now(timezone.utc)
    )
    assert "nincs érvényes időbélyeg" in invalid


def test_analytics_executive_report_discloses_truncated_input():
    from jarvis_analytics import build_executive_analytics_report

    report = build_executive_analytics_report(
        [], now=datetime(2026, 11, 23, tzinfo=timezone.utc), truncated=True
    )
    assert "5000 rekordos korlát" in report


def test_global_research_market_read_failure_returns_default(monkeypatch):
    import global_lead_research as research

    class Query:
        def select(self, *_args):
            return self
        def eq(self, *_args):
            return self
        def limit(self, *_args):
            return self
        def execute(self):
            raise OSError("offline fake")

    class DB:
        def table(self, _name):
            return Query()

    reports = []
    monkeypatch.setattr(
        research, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )
    assert research.get_research_market(DB()) == research.DEFAULT_MARKET
    assert reports[0][1]["severity"] == "warning"


def test_global_research_rejects_unsupported_market_and_ignores_non_commands():
    import global_lead_research as research

    with pytest.raises(ValueError, match="Nem támogatott"):
        research.set_research_market(object(), "Atlantis")
    assert research.detect_market_change("kérlek keress cégeket") is None


def test_global_research_quality_caps_weak_or_missing_evidence():
    from global_lead_research import _research_quality

    confidence, score, evidence = _research_quality({
        "fit_evidence": [], "research_confidence": "high",
        "business_fit_score": 99, "potential_fit": "specific fit",
    })
    assert (confidence, score, evidence) == ("low", 40, [])
    confidence, score, _ = _research_quality({
        "fit_evidence": ["one public signal"], "research_confidence": "high",
        "business_fit_score": 95, "potential_fit": "specific fit",
    })
    assert (confidence, score) == ("medium", 70)


def test_web_auditor_rejects_missing_url_and_handles_dns_failure(monkeypatch):
    import web_auditor as auditor

    assert auditor.audit_company_website(None) == "Nem adott meg weboldalt."
    monkeypatch.setattr(auditor, "_is_public_host", lambda _host: False)
    assert auditor._validated_url("https://private.example") is None


def test_web_auditor_non_html_response_is_closed(monkeypatch):
    import web_auditor as auditor

    monkeypatch.setattr(auditor, "_is_public_host", lambda _host: True)
    closed = []
    response = SimpleNamespace(status_code=200, headers={"Content-Type": "application/pdf"})
    monkeypatch.setattr(auditor, "safe_get", lambda *_args, **_kwargs: response)
    monkeypatch.setattr(auditor, "close_response", lambda value: closed.append(value))
    assert "nem HTML" in auditor.audit_company_website("https://public.example")
    assert closed == [response]


def test_web_auditor_request_failure_is_reported(monkeypatch):
    import requests
    import web_auditor as auditor

    monkeypatch.setattr(auditor, "_is_public_host", lambda _host: True)
    monkeypatch.setattr(
        auditor, "safe_get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(requests.Timeout("fake timeout")),
    )
    reports = []
    monkeypatch.setattr(auditor, "report_error", lambda error, **kwargs: reports.append(kwargs))
    assert "nem volt elérhető" in auditor.audit_company_website("https://public.example")
    assert reports[0]["severity"] == "warning"


def test_web_auditor_parse_failure_is_reported(monkeypatch):
    import web_auditor as auditor

    monkeypatch.setattr(auditor, "_is_public_host", lambda _host: True)
    response = SimpleNamespace(
        status_code=200, headers={"Content-Type": "text/html"},
        raw=SimpleNamespace(read=lambda *_args, **_kwargs: b"<html><title>x</title></html>"),
    )
    monkeypatch.setattr(auditor, "safe_get", lambda *_args, **_kwargs: response)
    monkeypatch.setattr(auditor, "close_response", lambda _response: None)
    monkeypatch.setattr(auditor, "BeautifulSoup", lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad html")))
    reports = []
    monkeypatch.setattr(auditor, "report_error", lambda error, **kwargs: reports.append(kwargs))
    assert "elemzési hiba" in auditor.audit_company_website("https://public.example")
    assert reports[0]["severity"] == "error"


def test_inbox_monitor_missing_credentials_is_safe_noop(monkeypatch, capsys):
    import inbox_monitor

    monkeypatch.setattr(inbox_monitor, "get_secret", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        inbox_monitor, "get_service_supabase",
        lambda: (_ for _ in ()).throw(AssertionError("database must not be opened")),
    )
    inbox_monitor._run()
    assert "hiányzik" in capsys.readouterr().out


def test_inbox_monitor_wrapper_reports_and_reraises(monkeypatch):
    import inbox_monitor

    reports = []
    monkeypatch.setattr(
        inbox_monitor, "_run",
        lambda: (_ for _ in ()).throw(RuntimeError("worker failure")),
    )
    monkeypatch.setattr(inbox_monitor, "report_error", lambda error, **kwargs: reports.append(kwargs))
    with pytest.raises(RuntimeError, match="worker failure"):
        inbox_monitor.run()
    assert reports[0]["operation"] == "process_inbox_monitor"
