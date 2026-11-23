"""Last-pass tests for backup utility success and filesystem fallback paths."""
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_backup_run_checked_returns_trimmed_stdout(monkeypatch):
    from scripts import supabase_backup as backup

    monkeypatch.setattr(
        backup.subprocess, "run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout="  completed  "),
    )
    assert backup.run_checked(["mock-tool"]) == "completed"


def test_backup_connection_brackets_ipv6_host_in_libpq_url(monkeypatch, tmp_path):
    from scripts import supabase_backup as backup

    monkeypatch.setattr(
        backup.socket, "getaddrinfo",
        lambda host, port, family, socktype: [
            (family, socktype, 6, "", ("203.0.113.25", port))
        ],
    )
    url, _env = backup._connection_env_and_url(
        "postgresql://postgres:pw@[2001:db8::1]:5432/postgres", tmp_path
    )
    assert "[2001:db8::1]" in url
    assert "hostaddr=203.0.113.25" in url


def test_backup_create_ignores_filesystem_permission_hardening_errors(monkeypatch, tmp_path):
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

    def denied_chmod(_self, _mode):
        raise OSError("chmod not supported by test filesystem")

    monkeypatch.setattr(Path, "chmod", denied_chmod)

    def fake_runner(args, **_kwargs):
        if args[0] == "pg_dump":
            Path(args[args.index("--file") + 1]).write_text("SELECT 1;")
        elif args[0] == "age":
            Path(args[args.index("--output") + 1]).write_bytes(b"encrypted")
        return ""

    monkeypatch.setattr(backup, "run_checked", fake_runner)
    result = backup.create_backup(tmp_path / "private")

    assert result.is_file()
    assert result.read_bytes() == b"encrypted"


def test_backup_cli_success_paths_return_zero(monkeypatch, tmp_path, capsys):
    import sys
    from scripts import supabase_backup as backup

    output = tmp_path / "jarvis-db-mock.tar.gz.age"
    output.write_bytes(b"encrypted")
    monkeypatch.setattr(backup, "create_backup", lambda _directory: output)
    monkeypatch.setattr(sys, "argv", ["supabase_backup.py", "backup"])
    assert backup.main() == 0
    assert "Titkosított mentés elkészült" in capsys.readouterr().out

    restore_calls = []
    monkeypatch.setattr(
        backup, "restore_backup",
        lambda archive, target_ref, confirmed: restore_calls.append(
            (archive, target_ref, confirmed)
        ),
    )
    monkeypatch.setattr(
        sys, "argv",
        ["supabase_backup.py", "restore", "--archive", str(output),
         "--target-project-ref", "abcdefghijklmnopqrst", "--confirm-restore"],
    )
    assert backup.main() == 0
    assert restore_calls == [(output, "abcdefghijklmnopqrst", True)]
    assert "elkülönített célprojektben" in capsys.readouterr().out
