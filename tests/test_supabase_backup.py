import json
import os
import tarfile
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import supabase_backup as backup


def test_extract_direct_project_ref():
    assert backup.project_ref_from_db_url(
        "postgresql://postgres:password@db.kiutreccucbegskxowek.supabase.co:5432/postgres"
    ) == backup.PRODUCTION_PROJECT_REF


def test_extract_pooler_project_ref():
    assert backup.project_ref_from_db_url(
        "postgresql://postgres.kiutreccucbegskxowek:password@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"
    ) == backup.PRODUCTION_PROJECT_REF


def test_reject_unknown_db_url():
    with pytest.raises(backup.BackupError):
        backup.project_ref_from_db_url("postgresql://user:password@localhost:5432/postgres")


def test_restore_refuses_production_before_any_external_command(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_RESTORE_DB_URL", "postgresql://postgres:pw@db.kiutreccucbegskxowek.supabase.co:5432/postgres")
    monkeypatch.setenv("JARVIS_RESTORE_ALLOWED_PROJECT_REF", backup.PRODUCTION_PROJECT_REF)
    monkeypatch.setenv("AGE_IDENTITY_FILE", str(tmp_path / "identity.txt"))
    (tmp_path / "identity.txt").write_text("not-a-real-key")
    with patch.object(backup, "run_checked") as runner:
        with pytest.raises(backup.BackupError, match="éles JARVIS"):
            backup.restore_backup(tmp_path / "backup.tar.gz.age", backup.PRODUCTION_PROJECT_REF, confirmed=True)
        runner.assert_not_called()


def test_restore_requires_explicit_allowlisted_sandbox(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_RESTORE_DB_URL", "postgresql://postgres:pw@db.abcdefghijklmnopqrst.supabase.co:5432/postgres")
    monkeypatch.setenv("JARVIS_RESTORE_ALLOWED_PROJECT_REF", "abcdefghijklmnopqrst")
    monkeypatch.setenv("AGE_IDENTITY_FILE", str(tmp_path / "identity.txt"))
    (tmp_path / "identity.txt").write_text("not-a-real-key")
    with patch.object(backup, "run_checked") as runner:
        with pytest.raises(backup.BackupError, match="nem található"):
            backup.restore_backup(tmp_path / "missing.tar.gz.age", "abcdefghijklmnopqrst", confirmed=True)
        runner.assert_not_called()


def test_archive_rejects_unexpected_files(tmp_path):
    archive = tmp_path / "bad.tar.gz"
    (tmp_path / "schema.sql").write_text("SELECT 1;")
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(tmp_path / "schema.sql", arcname="schema.sql")
    with pytest.raises(backup.BackupError, match="fájlkészlet"):
        backup._safe_extract(archive, tmp_path / "out")


def test_archive_manifest_and_hashes_are_verified(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    schema = work / "schema.sql"
    data = work / "data.sql"
    schema.write_text("CREATE TABLE public.example(id int);")
    data.write_text("COPY public.example (id) FROM stdin;\n1\n\\.\n")
    manifest = {
        "format_version": 1,
        "backup_id": "jarvis-db-test",
        "source_project_ref": backup.PRODUCTION_PROJECT_REF,
        "files": {
            "schema.sql": {"sha256": backup.sha256_file(schema)},
            "data.sql": {"sha256": backup.sha256_file(data)},
        },
    }
    (work / "manifest.json").write_text(json.dumps(manifest))
    archive = tmp_path / "valid.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name in ("manifest.json", "schema.sql", "data.sql"):
            tar.add(work / name, arcname=name)
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    result = backup._safe_extract(archive, extracted)
    assert result["backup_id"] == "jarvis-db-test"
    (extracted / "data.sql").write_text("tampered")
    tampered_extract = tmp_path / "tampered_extract"
    tampered_extract.mkdir()
    with pytest.raises(backup.BackupError, match="ellenőrzőösszege"):
        backup._safe_extract(archive, tampered_extract)


def test_restore_refuses_nonempty_sandbox_without_running_restore(monkeypatch, tmp_path):
    target_ref = "abcdefghijklmnopqrst"
    monkeypatch.setenv("JARVIS_RESTORE_DB_URL", f"postgresql://postgres:pw@db.{target_ref}.supabase.co:5432/postgres")
    monkeypatch.setenv("JARVIS_RESTORE_ALLOWED_PROJECT_REF", target_ref)
    identity = tmp_path / "identity.txt"
    identity.write_text("test-only-placeholder")
    monkeypatch.setenv("AGE_IDENTITY_FILE", str(identity))
    archive = tmp_path / "backup.tar.gz.age"
    archive.write_bytes(b"encrypted-placeholder")
    monkeypatch.setattr(backup.shutil, "which", lambda _: "/usr/bin/fake")
    monkeypatch.setattr(backup, "_safe_extract", lambda *_: {"source_project_ref": backup.PRODUCTION_PROJECT_REF})
    with patch.object(backup, "run_checked", side_effect=["", "2"]) as runner:
        with pytest.raises(backup.BackupError, match="nem üres"):
            backup.restore_backup(archive, target_ref, confirmed=True)
        assert runner.call_count == 2
        assert runner.call_args_list[-1].args[0][0] == "psql"
        assert "--file" not in runner.call_args_list[-1].args[0]


def test_restore_rejects_db_url_allowlist_mismatch(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_RESTORE_DB_URL", "postgresql://postgres:pw@db.abcdefghijklmnopqrst.supabase.co:5432/postgres")
    monkeypatch.setenv("JARVIS_RESTORE_ALLOWED_PROJECT_REF", "abcdefghijklmnopqrst")
    monkeypatch.setenv("AGE_IDENTITY_FILE", str(tmp_path / "identity.txt"))
    (tmp_path / "identity.txt").write_text("test-only-placeholder")
    with patch.object(backup, "run_checked") as runner:
        with pytest.raises(backup.BackupError, match="nem egyezik"):
            backup.restore_backup(tmp_path / "backup.tar.gz.age", "bcdefghijklmnopqrstu", confirmed=True)
        runner.assert_not_called()

def test_restore_requires_explicit_confirmation(monkeypatch, tmp_path):
    with pytest.raises(backup.BackupError, match="confirm-restore"):
        backup.restore_backup(tmp_path / "backup.tar.gz.age", "abcdefghijklmnopqrst")


def test_database_password_is_not_in_connection_argument(tmp_path):
    url = "postgresql://postgres:secret%3Avalue@db.kiutreccucbegskxowek.supabase.co:5432/postgres?sslmode=require"
    safe_url, env = backup._connection_env_and_url(url, tmp_path)
    assert "secret" not in safe_url
    assert "postgres@" in safe_url
    passfile = Path(env["PGPASSFILE"])
    assert passfile.exists()
    assert passfile.stat().st_mode & 0o777 == 0o600
    assert "secret\\:value" in passfile.read_text()


def test_connection_password_is_removed_from_url_and_written_privately(tmp_path):
    raw = "postgresql://postgres:pa%3Ass%40word@db.kiutreccucbegskxowek.supabase.co:5432/postgres?sslmode=require"
    safe_url, env = backup._connection_env_and_url(raw, tmp_path)
    assert "pa%3Ass%40word" not in safe_url
    assert "postgres@" in safe_url
    assert env["PGPASSWORD"] == "pa:ss@word"
    pgpass = Path(env["PGPASSFILE"])
    assert pgpass.stat().st_mode & 0o777 == 0o600
    assert "pa\\:ss@word" in pgpass.read_text()
