import sys
from unittest.mock import patch

import pytest

import scripts.supabase_backup as backup


def test_backup_cli_reports_expected_failure_without_leaking_secret(monkeypatch, capsys):
    captured = []
    monkeypatch.setattr(sys, "argv", ["supabase_backup.py", "backup"])
    monkeypatch.setattr(backup, "create_backup", lambda _path: (_ for _ in ()).throw(
        backup.BackupError("backup failed password=do-not-print-this")
    ))
    monkeypatch.setattr(backup, "report_error", lambda *args, **kwargs: captured.append((args, kwargs)))

    with pytest.raises(SystemExit) as exc:
        backup.main()

    assert exc.value.code == 2
    assert captured[0][1]["module"] == "supabase_backup"
    assert captured[0][1]["operation"] == "backup_backup"
    assert captured[0][1]["severity"] == "error"
    assert "do-not-print-this" not in capsys.readouterr().err


def test_backup_cli_reports_unexpected_failure_as_critical(monkeypatch, capsys):
    captured = []
    monkeypatch.setattr(sys, "argv", ["supabase_backup.py", "restore", "--archive", "x.age", "--target-project-ref", "abcdefghijklmnopqrst", "--confirm-restore"])
    monkeypatch.setattr(backup, "restore_backup", lambda *_args, **_kwargs: (_ for _ in ()).throw(
        RuntimeError("api_key=unexpected-secret")
    ))
    monkeypatch.setattr(backup, "report_error", lambda *args, **kwargs: captured.append((args, kwargs)))

    with pytest.raises(SystemExit) as exc:
        backup.main()

    assert exc.value.code == 2
    assert captured[0][1]["module"] == "supabase_backup"
    assert captured[0][1]["operation"] == "restore_backup"
    assert captured[0][1]["severity"] == "critical"
    assert "unexpected-secret" not in capsys.readouterr().err
