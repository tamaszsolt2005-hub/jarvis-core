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
            backup.restore_backup(tmp_path / "backup.tar.gz.age", backup.PRODUCTION_PROJECT_REF)
        runner.assert_not_called()


def test_restore_requires_explicit_allowlisted_sandbox(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_RESTORE_DB_URL", "postgresql://postgres:pw@db.abcdefghijklmnopqrst.supabase.co:5432/postgres")
    monkeypatch.setenv("JARVIS_RESTORE_ALLOWED_PROJECT_REF", "abcdefghijklmnopqrst")
    monkeypatch.setenv("AGE_IDENTITY_FILE", str(tmp_path / "identity.txt"))
    (tmp_path / "identity.txt").write_text("not-a-real-key")
    with patch.object(backup, "run_checked") as runner:
        with pytest.raises(backup.BackupError, match="nem található"):
            backup.restore_backup(tmp_path / "missing.tar.gz.age", "abcdefghijklmnopqrst")
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
    with pytest.raises(backup.BackupError, match="ellenőrzőösszege"):
        backup._safe_extract(archive, tmp_path / "tampered_extract")
