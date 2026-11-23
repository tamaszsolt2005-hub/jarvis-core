"""End-to-end encrypted backup/restore test against an ephemeral local PostgreSQL.

The test is enabled only in the dedicated CI service job. It never connects to
Supabase or any remote host and uses a fresh database for the restore target.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts import supabase_backup as backup


pytestmark = [
    pytest.mark.backup_restore_integration,
    pytest.mark.skipif(
        os.environ.get("JARVIS_BACKUP_INTEGRATION_TEST") != "1",
        reason="requires the isolated PostgreSQL + age CI service",
    ),
]


def _psql(db_url: str, sql: str) -> str:
    safe_url, env = backup._connection_env_and_url(db_url, Path("."))
    return backup.run_checked([
        "psql", "--no-psqlrc", "--set", "ON_ERROR_STOP=1",
        "--tuples-only", "--no-align", "--command", sql, "--dbname", safe_url,
    ], env=env)


def test_encrypted_backup_can_be_decrypted_verified_and_restored(tmp_path, monkeypatch):
    source_url = os.environ["SUPABASE_DB_URL"]
    target_url = os.environ["JARVIS_RESTORE_DB_URL"]
    identity = Path(os.environ["AGE_IDENTITY_FILE"])

    assert shutil.which("pg_dump")
    assert shutil.which("pg_restore")
    assert shutil.which("psql")
    assert shutil.which("age")
    assert identity.is_file()
    assert identity.stat().st_mode & 0o077 == 0

    _psql(
        source_url,
        "CREATE TABLE public.backup_fixture (id bigint PRIMARY KEY, payload text NOT NULL);"
        "CREATE INDEX backup_fixture_payload_idx ON public.backup_fixture(payload);"
        "INSERT INTO public.backup_fixture(id, payload) VALUES (1, 'jarvis-backup-roundtrip'), (2, 'unicode-áéő');",
    )
    target_count = _psql(
        target_url,
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f','S');",
    )
    assert target_count.strip() == "0"

    monkeypatch.setenv("JARVIS_BACKUP_ALLOW_LOCAL_TEST_DB", "true")
    monkeypatch.setenv("JARVIS_BACKUP_SOURCE_PROJECT_REF", "local-test")
    monkeypatch.setenv("JARVIS_RESTORE_ALLOW_LOCAL_TEST_DB", "true")
    monkeypatch.setenv("JARVIS_RESTORE_ALLOWED_PROJECT_REF", "local-test")
    monkeypatch.setenv("AGE_IDENTITY_FILE", str(identity))

    archive = backup.create_backup(tmp_path / "encrypted")
    assert archive.is_file() and archive.stat().st_size > 0

    manifest = backup.verify_backup(archive)
    assert manifest["source_project_ref"] == "local-test"
    assert manifest["files"]["schema.sql"]["sha256"]
    assert manifest["files"]["data.sql"]["sha256"]

    backup.restore_backup(archive, "local-test", confirmed=True)
    restored = _psql(
        target_url,
        "SELECT string_agg(id::text || ':' || payload, ',' ORDER BY id) "
        "FROM public.backup_fixture;",
    )
    assert restored.strip() == "1:jarvis-backup-roundtrip,2:unicode-áéő"
    index_count = _psql(
        target_url,
        "SELECT count(*) FROM pg_indexes WHERE schemaname='public' "
        "AND indexname='backup_fixture_payload_idx';",
    )
    assert index_count.strip() == "1"
