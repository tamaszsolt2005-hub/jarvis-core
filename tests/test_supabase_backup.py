import json
import os
import subprocess
import tarfile
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import supabase_backup as backup


@pytest.fixture(autouse=True)
def mock_ipv4_dns(monkeypatch):
    monkeypatch.setattr(
        backup.socket,
        "getaddrinfo",
        lambda host, port, family, socktype: [
            (family, socktype, 6, "", ("203.0.113.10", port))
        ],
    )


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
    (tmp_path / "identity.txt").chmod(0o600)
    with patch.object(backup, "run_checked") as runner:
        with pytest.raises(backup.BackupError, match="éles JARVIS"):
            backup.restore_backup(tmp_path / "backup.tar.gz.age", backup.PRODUCTION_PROJECT_REF, confirmed=True)
        runner.assert_not_called()


def test_restore_requires_explicit_allowlisted_sandbox(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_RESTORE_DB_URL", "postgresql://postgres:pw@db.abcdefghijklmnopqrst.supabase.co:5432/postgres")
    monkeypatch.setenv("JARVIS_RESTORE_ALLOWED_PROJECT_REF", "abcdefghijklmnopqrst")
    monkeypatch.setenv("AGE_IDENTITY_FILE", str(tmp_path / "identity.txt"))
    (tmp_path / "identity.txt").write_text("not-a-real-key")
    (tmp_path / "identity.txt").chmod(0o600)
    monkeypatch.setattr(backup.shutil, "which", lambda _: "/usr/bin/fake")
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
    tampered_data = tmp_path / "tampered_data.sql"
    tampered_data.write_text("tampered")
    tampered_archive = tmp_path / "tampered.tar.gz"
    with tarfile.open(tampered_archive, "w:gz") as tar:
        tar.add(work / "manifest.json", arcname="manifest.json")
        tar.add(work / "schema.sql", arcname="schema.sql")
        tar.add(tampered_data, arcname="data.sql")
    tampered_extract = tmp_path / "tampered_extract"
    tampered_extract.mkdir()
    with pytest.raises(backup.BackupError, match="ellenőrzőösszege"):
        backup._safe_extract(tampered_archive, tampered_extract)


def test_restore_refuses_nonempty_sandbox_without_running_restore(monkeypatch, tmp_path):
    target_ref = "abcdefghijklmnopqrst"
    monkeypatch.setenv("JARVIS_RESTORE_DB_URL", f"postgresql://postgres:pw@db.{target_ref}.supabase.co:5432/postgres")
    monkeypatch.setenv("JARVIS_RESTORE_ALLOWED_PROJECT_REF", target_ref)
    identity = tmp_path / "identity.txt"
    identity.write_text("test-only-placeholder")
    identity.chmod(0o600)
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
    (tmp_path / "identity.txt").chmod(0o600)
    with patch.object(backup, "run_checked") as runner:
        with pytest.raises(backup.BackupError, match="nem egyezik"):
            backup.restore_backup(tmp_path / "backup.tar.gz.age", "bcdefghijklmnopqrstu", confirmed=True)
        runner.assert_not_called()

def test_restore_requires_explicit_confirmation(monkeypatch, tmp_path):
    with pytest.raises(backup.BackupError, match="confirm-restore"):
        backup.restore_backup(tmp_path / "backup.tar.gz.age", "abcdefghijklmnopqrst")


def test_database_password_is_passed_via_environment_not_url(tmp_path):
    url = "postgresql://postgres:secret%3Avalue%40%7Btest%7D@db.kiutreccucbegskxowek.supabase.co:5432/postgres?sslmode=require"
    safe_url, env = backup._connection_env_and_url(url, tmp_path)
    assert "secret" not in safe_url
    assert "postgres@" in safe_url
    assert "sslmode=require" in safe_url
    assert "hostaddr=203.0.113.10" in safe_url
    assert env["PGPASSWORD"] == "secret:value@{test}"


def test_connection_password_special_characters_are_decoded_once(tmp_path):
    raw = "postgresql://postgres:pa%3Ass%40word@db.kiutreccucbegskxowek.supabase.co:5432/postgres?sslmode=require"
    safe_url, env = backup._connection_env_and_url(raw, tmp_path)
    assert "pa:ss@word" not in safe_url
    assert env["PGPASSWORD"] == "pa:ss@word"


def test_restore_sql_reuses_existing_public_schema():
    schema = "CREATE SCHEMA public;" + chr(10) + "ALTER SCHEMA public OWNER TO postgres;" + chr(10) + "CREATE TABLE public.sample(id integer);"
    data = "COPY public.sample (id) FROM stdin;" + chr(10) + "1" + chr(10) + "\\." + chr(10)
    restored = backup._restore_sql_text(schema, data)
    assert "CREATE SCHEMA public" not in restored
    assert "ALTER SCHEMA public OWNER" not in restored
    assert "CREATE TABLE public.sample" in restored
    assert "COPY public.sample" in restored


def test_create_backup_uses_mocked_tools_and_writes_encrypted_output(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "SUPABASE_DB_URL",
        "postgresql://postgres:mock-password@db.kiutreccucbegskxowek.supabase.co:5432/postgres",
    )
    monkeypatch.setenv("BACKUP_AGE_RECIPIENT", "age1mockrecipient")
    monkeypatch.setenv("JARVIS_BACKUP_SOURCE_PROJECT_REF", backup.PRODUCTION_PROJECT_REF)
    monkeypatch.setattr(backup.shutil, "which", lambda _name: "/usr/bin/mock")
    monkeypatch.setattr(
        backup, "_connection_env_and_url",
        lambda *_args: ("postgresql://postgres@db.example.test/postgres", {"PGPASSWORD": "mock-password"}),
    )
    commands = []

    def fake_run_checked(args, *, env=None):
        commands.append((args, env))
        if args[0] == "pg_dump":
            output = Path(args[args.index("--file") + 1])
            output.write_bytes(b"mock custom-format snapshot")
        elif args[0] == "pg_restore":
            output = Path(args[args.index("--file") + 1])
            output.write_text("CREATE TABLE public.sample(id integer);" if "--schema-only" in args else "COPY public.sample (id) FROM stdin;\n1\n\\.\n")
        elif args[0] == "age":
            output = Path(args[args.index("--output") + 1])
            output.write_bytes(b"mock encrypted backup")
        return ""

    monkeypatch.setattr(backup, "run_checked", fake_run_checked)

    result = backup.create_backup(tmp_path / "private")

    assert result.is_file()
    assert result.read_bytes() == b"mock encrypted backup"
    assert result.suffix == ".age"
    assert [args[0] for args, _env in commands] == ["pg_dump", "pg_restore", "pg_restore", "age"]
    assert "--format=custom" in commands[0][0]
    assert "--schema-only" in commands[1][0]
    assert "--data-only" in commands[2][0]
    assert "--no-password" in commands[0][0]
    assert all("mock-password" not in " ".join(args) for args, _env in commands)
    assert commands[0][1]["PGPASSWORD"] == "mock-password"
    if os.name == "posix":
        assert result.stat().st_mode & 0o777 == 0o600
        assert (tmp_path / "private").stat().st_mode & 0o777 == 0o700


def test_create_backup_rejects_wrong_source_before_running_external_tools(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "SUPABASE_DB_URL",
        "postgresql://postgres:pw@db.kiutreccucbegskxowek.supabase.co:5432/postgres",
    )
    monkeypatch.setenv("BACKUP_AGE_RECIPIENT", "age1mockrecipient")
    monkeypatch.setenv("JARVIS_BACKUP_SOURCE_PROJECT_REF", "abcdefghijklmnopqrst")
    monkeypatch.setattr(backup.shutil, "which", lambda _name: "/usr/bin/mock")
    with patch.object(backup, "run_checked") as runner:
        with pytest.raises(backup.BackupError, match="forrásazonosító"):
            backup.create_backup(tmp_path / "private")
        runner.assert_not_called()


@pytest.mark.parametrize(
    ("stderr", "expected"),
    [
        ("password authentication failed", "hitelesítés sikertelen"),
        ("could not translate host name", "hosztnév nem oldható fel"),
        ("connection timed out", "nem érhető el"),
        ("SSL certificate verify failed", "SSL/TLS"),
        ("docker daemon is unavailable", "futtatókörnyezete hibázott"),
    ],
)
def test_run_checked_maps_known_postgres_failures_without_raw_diagnostics(stderr, expected):
    failure = subprocess.CalledProcessError(1, ["pg_dump"], stderr=stderr)
    with patch.object(backup.subprocess, "run", side_effect=failure):
        with pytest.raises(backup.BackupError) as exc:
            backup.run_checked(["pg_dump"])
    assert expected in str(exc.value)
    assert stderr not in str(exc.value)


def test_run_checked_reports_missing_external_program():
    with patch.object(backup.subprocess, "run", side_effect=FileNotFoundError):
        with pytest.raises(backup.BackupError, match="Hiányzó külső program"):
            backup.run_checked(["pg_dump"])


def test_connection_url_requires_credentials_and_available_ipv4(tmp_path, monkeypatch):
    with pytest.raises(backup.BackupError, match="hostot, felhasználót és jelszót"):
        backup._connection_env_and_url("postgresql://postgres@db.example.test/postgres", tmp_path)

    monkeypatch.setattr(
        backup.socket, "getaddrinfo",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("DNS unavailable")),
    )
    with pytest.raises(backup.BackupError, match="IPv4-cím"):
        backup._connection_env_and_url(
            "postgresql://postgres:pw@db.example.test/postgres", tmp_path
        )


def test_archive_rejects_unknown_manifest_version(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    schema = work / "schema.sql"
    data = work / "data.sql"
    schema.write_text("SELECT 1;")
    data.write_text("SELECT 2;")
    manifest = {
        "format_version": 99,
        "source_project_ref": backup.PRODUCTION_PROJECT_REF,
        "files": {
            "schema.sql": {"sha256": backup.sha256_file(schema)},
            "data.sql": {"sha256": backup.sha256_file(data)},
        },
    }
    (work / "manifest.json").write_text(json.dumps(manifest))
    archive = tmp_path / "unknown-version.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name in ("manifest.json", "schema.sql", "data.sql"):
            tar.add(work / name, arcname=name)
    destination = tmp_path / "out"
    destination.mkdir()
    with pytest.raises(backup.BackupError, match="Ismeretlen formátum"):
        backup._safe_extract(archive, destination)


def test_create_backup_requires_all_secrets_before_any_external_command(monkeypatch, tmp_path):
    for name in ("SUPABASE_DB_URL", "BACKUP_AGE_RECIPIENT", "JARVIS_BACKUP_SOURCE_PROJECT_REF"):
        monkeypatch.delenv(name, raising=False)
    with patch.object(backup, "run_checked") as runner:
        with pytest.raises(backup.BackupError, match="Hiányzó konfiguráció"):
            backup.create_backup(tmp_path / "private")
        runner.assert_not_called()


def test_create_backup_requires_both_external_programs(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "SUPABASE_DB_URL",
        "postgresql://postgres:pw@db.kiutreccucbegskxowek.supabase.co:5432/postgres",
    )
    monkeypatch.setenv("BACKUP_AGE_RECIPIENT", "age1mockrecipient")
    monkeypatch.setenv("JARVIS_BACKUP_SOURCE_PROJECT_REF", backup.PRODUCTION_PROJECT_REF)
    monkeypatch.setattr(backup.shutil, "which", lambda name: None if name == "age" else "/usr/bin/pg_dump")
    with pytest.raises(backup.BackupError, match="pg_dump, pg_restore és age"):
        backup.create_backup(tmp_path / "private")


def test_restore_success_is_mocked_and_uses_single_transaction(monkeypatch, tmp_path):
    target_ref = "abcdefghijklmnopqrst"
    monkeypatch.setenv(
        "JARVIS_RESTORE_DB_URL",
        f"postgresql://postgres:mock-password@db.{target_ref}.supabase.co:5432/postgres",
    )
    monkeypatch.setenv("JARVIS_RESTORE_ALLOWED_PROJECT_REF", target_ref)
    identity = tmp_path / "identity.txt"
    identity.write_text("mock identity")
    identity.chmod(0o600)
    monkeypatch.setenv("AGE_IDENTITY_FILE", str(identity))
    archive = tmp_path / "backup.tar.gz.age"
    archive.write_bytes(b"mock encrypted data")
    monkeypatch.setattr(backup.shutil, "which", lambda _name: "/usr/bin/mock")
    monkeypatch.setattr(
        backup, "_connection_env_and_url",
        lambda *_args: ("postgresql://postgres@db.example.test/postgres", {"PGPASSWORD": "mock-password"}),
    )

    def fake_extract(_archive, destination):
        (destination / "schema.sql").write_text(
            "CREATE SCHEMA public;\nCREATE TABLE public.sample(id integer);"
        )
        (destination / "data.sql").write_text("COPY public.sample (id) FROM stdin;\n1\n\\.\n")
        return {"source_project_ref": backup.PRODUCTION_PROJECT_REF}

    monkeypatch.setattr(backup, "_safe_extract", fake_extract)
    commands = []

    def fake_run_checked(args, *, env=None):
        commands.append(args)
        if args[0] == "age":
            Path(args[args.index("--output") + 1]).write_bytes(b"decrypted archive")
            return ""
        if args[0] == "psql" and "--command" in args:
            return "0"
        if args[0] == "psql" and "--file" in args:
            sql = Path(args[args.index("--file") + 1]).read_text()
            assert "CREATE SCHEMA public" not in sql
            assert "CREATE TABLE public.sample" in sql
            assert "ALTER DEFAULT PRIVILEGES IN SCHEMA public" in sql
            return ""
        raise AssertionError(f"unexpected mocked command: {args[0]}")

    monkeypatch.setattr(backup, "run_checked", fake_run_checked)

    backup.restore_backup(archive, target_ref, confirmed=True)

    assert [command[0] for command in commands] == ["age", "psql", "psql"]
    assert "--single-transaction" in commands[-1]
    assert "--set" in commands[-1]
    assert "ON_ERROR_STOP=1" in commands[-1]


def test_restore_rejects_overly_permissive_age_identity_file(monkeypatch, tmp_path):
    target_ref = "abcdefghijklmnopqrst"
    monkeypatch.setenv(
        "JARVIS_RESTORE_DB_URL",
        f"postgresql://postgres:pw@db.{target_ref}.supabase.co:5432/postgres",
    )
    monkeypatch.setenv("JARVIS_RESTORE_ALLOWED_PROJECT_REF", target_ref)
    identity = tmp_path / "identity.txt"
    identity.write_text("mock identity")
    identity.chmod(0o644)
    monkeypatch.setenv("AGE_IDENTITY_FILE", str(identity))
    archive = tmp_path / "backup.age"
    archive.write_bytes(b"mock")
    monkeypatch.setattr(backup.shutil, "which", lambda _name: "/usr/bin/mock")

    with pytest.raises(backup.BackupError, match="jogosultsága túl nyitott"):
        backup.restore_backup(archive, target_ref, confirmed=True)


def test_restore_rejects_unparseable_empty_schema_count(monkeypatch, tmp_path):
    target_ref = "abcdefghijklmnopqrst"
    monkeypatch.setenv(
        "JARVIS_RESTORE_DB_URL",
        f"postgresql://postgres:pw@db.{target_ref}.supabase.co:5432/postgres",
    )
    monkeypatch.setenv("JARVIS_RESTORE_ALLOWED_PROJECT_REF", target_ref)
    identity = tmp_path / "identity.txt"
    identity.write_text("mock identity")
    identity.chmod(0o600)
    monkeypatch.setenv("AGE_IDENTITY_FILE", str(identity))
    archive = tmp_path / "backup.age"
    archive.write_bytes(b"mock")
    monkeypatch.setattr(backup.shutil, "which", lambda _name: "/usr/bin/mock")
    monkeypatch.setattr(backup, "_safe_extract", lambda _archive, _destination: {
        "source_project_ref": backup.PRODUCTION_PROJECT_REF
    })
    with patch.object(backup, "run_checked", side_effect=["", "not-a-number"]):
        with pytest.raises(backup.BackupError, match="Nem sikerült ellenőrizni"):
            backup.restore_backup(archive, target_ref, confirmed=True)



def test_database_url_secrets_are_not_inherited_by_child_processes(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://postgres:top-secret@db.kiutreccucbegskxowek.supabase.co/postgres")
    monkeypatch.setenv("JARVIS_RESTORE_DB_URL", "postgresql://postgres:other-secret@db.abcdefghijklmnopqrst.supabase.co/postgres")
    monkeypatch.setenv("GEMINI_API_KEY", "must-not-leak")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "must-not-leak-either")
    _safe_url, env = backup._connection_env_and_url(
        "postgresql://postgres:encoded%3Asecret@db.kiutreccucbegskxowek.supabase.co:5432/postgres",
        tmp_path,
    )
    assert "SUPABASE_DB_URL" not in env
    assert "JARVIS_RESTORE_DB_URL" not in env
    assert "GEMINI_API_KEY" not in env
    assert "SUPABASE_SERVICE_ROLE_KEY" not in env
    assert env["PGPASSWORD"] == "encoded:secret"


def test_backup_uses_one_pg_dump_snapshot_for_schema_and_data(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "SUPABASE_DB_URL",
        "postgresql://postgres:mock-password@db.kiutreccucbegskxowek.supabase.co:5432/postgres",
    )
    monkeypatch.setenv("BACKUP_AGE_RECIPIENT", "age1mockrecipient")
    monkeypatch.setenv("JARVIS_BACKUP_SOURCE_PROJECT_REF", backup.PRODUCTION_PROJECT_REF)
    monkeypatch.setattr(backup.shutil, "which", lambda _name: "/usr/bin/mock")
    monkeypatch.setattr(
        backup, "_connection_env_and_url",
        lambda *_args: ("postgresql://postgres@db.example.test/postgres", {"PGPASSWORD": "mock-password"}),
    )
    commands = []

    def fake_run_checked(args, *, env=None):
        commands.append(args)
        if args[0] == "pg_dump":
            Path(args[args.index("--file") + 1]).write_bytes(b"one consistent snapshot")
        elif args[0] == "pg_restore":
            Path(args[args.index("--file") + 1]).write_text("SELECT 1;")
        elif args[0] == "age":
            Path(args[args.index("--output") + 1]).write_bytes(b"encrypted")
        return ""

    monkeypatch.setattr(backup, "run_checked", fake_run_checked)
    backup.create_backup(tmp_path / "private")

    assert sum(command[0] == "pg_dump" for command in commands) == 1
    assert sum(command[0] == "pg_restore" for command in commands) == 2
    assert commands[0][commands[0].index("--file") + 1].endswith("database.dump")
    assert commands[1][-1] == commands[0][commands[0].index("--file") + 1]
    assert commands[2][-1] == commands[0][commands[0].index("--file") + 1]



def test_run_checked_sanitizes_database_urls_even_without_explicit_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://postgres:never-leak@db.kiutreccucbegskxowek.supabase.co/postgres")
    monkeypatch.setenv("JARVIS_RESTORE_DB_URL", "postgresql://postgres:also-never-leak@db.abcdefghijklmnopqrst.supabase.co/postgres")
    captured = {}

    def fake_run(_args, **kwargs):
        captured.update(kwargs)
        return subprocess.CompletedProcess(_args, 0, stdout="", stderr="")

    monkeypatch.setattr(backup.subprocess, "run", fake_run)
    backup.run_checked(["age", "--version"])

    assert "SUPABASE_DB_URL" not in captured["env"]
    assert "JARVIS_RESTORE_DB_URL" not in captured["env"]



def test_run_checked_does_not_pass_unrelated_application_secrets(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "never-leak")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "never-leak-either")
    captured = {}

    def fake_run(_args, **kwargs):
        captured.update(kwargs)
        return subprocess.CompletedProcess(_args, 0, stdout="", stderr="")

    monkeypatch.setattr(backup.subprocess, "run", fake_run)
    backup.run_checked(["age", "--version"])

    assert "GEMINI_API_KEY" not in captured["env"]
    assert "SUPABASE_SERVICE_ROLE_KEY" not in captured["env"]
    assert "PATH" in captured["env"]

def test_local_test_database_allowlist_accepts_only_loopback_urls():
    assert backup._is_loopback_db_url("postgresql://postgres:pw@127.0.0.1:5432/postgres")
    assert backup._is_loopback_db_url("postgresql://postgres:pw@localhost:5432/postgres")
    assert not backup._is_loopback_db_url(
        "postgresql://postgres:pw@db.kiutreccucbegskxowek.supabase.co:5432/postgres"
    )


def test_local_test_project_ref_requires_explicit_flag_and_loopback(monkeypatch):
    local_url = "postgresql://postgres:pw@127.0.0.1:5432/postgres"
    with pytest.raises(backup.BackupError):
        backup._validated_project_ref(local_url, allow_local_test=False)
    assert backup._validated_project_ref(local_url, allow_local_test=True) == "local-test"


def test_verify_backup_requires_private_identity_file(monkeypatch, tmp_path):
    monkeypatch.delenv("AGE_IDENTITY_FILE", raising=False)
    with pytest.raises(backup.BackupError, match="AGE_IDENTITY_FILE"):
        backup.verify_backup(tmp_path / "not-a-backup")

