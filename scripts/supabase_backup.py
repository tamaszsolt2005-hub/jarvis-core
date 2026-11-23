#!/usr/bin/env python3
"""Encrypted, off-site logical backup and guarded restore for the JARVIS Supabase DB.

Backups contain the complete public schema and public data. They deliberately do
not dump Supabase-managed auth/storage/realtime schemas or Storage object binaries.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import tarfile
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlparse, urlsplit, urlunsplit

from jarvis_errors import report_error, sanitize_log_text

PRODUCTION_PROJECT_REF = "kiutreccucbegskxowek"
BACKUP_PREFIX = "jarvis-db"
ALLOWED_ARCHIVE_FILES = {"manifest.json", "schema.sql", "data.sql"}


class BackupError(RuntimeError):
    pass


_CHILD_ENV_KEYS = {
    "PATH", "HOME", "TMPDIR", "TEMP", "TMP", "LANG", "LC_ALL", "LC_CTYPE",
    "SYSTEMROOT", "WINDIR", "SSL_CERT_FILE", "SSL_CERT_DIR",
    "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH", "PGPASSWORD", "PGSSLROOTCERT", "PGSSLMODE",
}


def _safe_child_env(source: dict[str, str] | None = None) -> dict[str, str]:
    """Pass only runtime essentials to external tools, never application secrets."""
    values = os.environ if source is None else source
    return {key: value for key, value in values.items() if key in _CHILD_ENV_KEYS}


def project_ref_from_db_url(db_url: str) -> str:
    """Extract the Supabase project ref from direct or pooler connection URLs."""
    parsed = urlparse(db_url)
    host = (parsed.hostname or "").lower()
    direct = re.fullmatch(r"db\.([a-z0-9]{20})\.supabase\.co", host)
    if direct:
        return direct.group(1)
    # Supavisor usernames conventionally use postgres.<project-ref>.
    username = parsed.username or ""
    pooler = re.fullmatch(r"postgres\.([a-z0-9]{20})", username)
    if pooler and "pooler.supabase.com" in host:
        return pooler.group(1)
    raise BackupError("A DB URL-ből nem állapítható meg biztonságosan a Supabase projektazonosító.")

def _is_loopback_db_url(db_url: str) -> bool:
    """Return true only for an explicitly local database host."""
    host = (urlsplit(db_url).hostname or "").strip("[]").lower()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _validated_project_ref(db_url: str, *, allow_local_test: bool) -> str:
    """Permit a synthetic project ref only for explicitly enabled loopback tests."""
    if allow_local_test and _is_loopback_db_url(db_url):
        return "local-test"
    return project_ref_from_db_url(db_url)




def _connection_env_and_url(db_url: str, work: Path) -> tuple[str, dict[str, str]]:
    """Build a password-free libpq URL and pass credentials via environment."""
    parsed = urlsplit(db_url)
    if not parsed.hostname or not parsed.username or not parsed.password:
        raise BackupError("A DB URL-nek hostot, felhasználót és jelszót kell tartalmaznia.")
    username = quote(unquote(parsed.username), safe="")
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = parsed.port or 5432
    netloc = f"{username}@{host}:{port}"
    # GitHub-hosted runners may resolve Supabase's AAAA record first despite
    # having no IPv6 route. Pin libpq to a resolved IPv4 address while keeping
    # the original hostname for TLS certificate verification.
    try:
        ipv4 = socket.getaddrinfo(parsed.hostname, port, socket.AF_INET, socket.SOCK_STREAM)[0][4][0]
    except (OSError, IndexError) as exc:
        raise BackupError("Az adatbázis hosztnevéhez nem található elérhető IPv4-cím a futtatókörnyezetben.") from exc
    query = parse_qsl(parsed.query, keep_blank_values=True)
    query = [(key, value) for key, value in query if key.lower() != "hostaddr"]
    query.append(("hostaddr", ipv4))
    safe_url = urlunsplit((parsed.scheme, netloc, parsed.path or "/postgres", urlencode(query), ""))
    db_env = _safe_child_env()
    db_env["PGPASSWORD"] = unquote(parsed.password)
    return safe_url, db_env


def run_checked(args: list[str], *, env: dict[str, str] | None = None) -> str:
    # Every external process gets a sanitized environment, including age and
    # pg_restore calls that do not need a database connection.
    child_env = _safe_child_env(env)
    try:
        result = subprocess.run(
            args, check=True, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env=child_env,
        )
        return result.stdout.strip()
    except FileNotFoundError as exc:
        raise BackupError(f"Hiányzó külső program: {args[0]}") from exc
    except subprocess.CalledProcessError as exc:
        # Never echo argv or raw stderr: either may contain credentials.
        detail = (exc.stderr or "").lower()
        if "password authentication failed" in detail or "authentication failed" in detail:
            reason = "adatbázis-hitelesítés sikertelen (ellenőrizd a jelszót és annak URL-kódolását)"
        elif "could not translate host" in detail or "name or service not known" in detail or "no such host" in detail:
            reason = "a megadott adatbázis-hosztnév nem oldható fel"
        elif "timeout expired" in detail or "connection timed out" in detail or "could not connect to server" in detail:
            reason = "az adatbázis nem érhető el a megadott hoston/porton (hálózat vagy pooler-beállítás)"
        elif "ssl" in detail or "certificate" in detail:
            reason = "SSL/TLS-kapcsolati hiba"
        elif "docker" in detail or "daemon" in detail or "container" in detail:
            reason = "a külső adatbázis-eszköz futtatókörnyezete hibázott"
        else:
            # Keep useful PostgreSQL diagnostics while removing any URI credentials.
            raw_detail = (exc.stderr or "").strip().splitlines()
            safe_detail = sanitize_log_text(raw_detail[0] if raw_detail else "nincs részletes hibaüzenet", max_length=400)
            reason = f"PostgreSQL hiba: {safe_detail}"
        raise BackupError(f"A(z) {args[0]} parancs hibával leállt: {reason}.") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_backup(output_dir: Path) -> Path:
    db_url = os.environ.get("SUPABASE_DB_URL", "")
    recipient = os.environ.get("BACKUP_AGE_RECIPIENT", "")
    source_ref = os.environ.get("JARVIS_BACKUP_SOURCE_PROJECT_REF", "")
    if not db_url or not recipient or not source_ref:
        raise BackupError("Hiányzó konfiguráció: SUPABASE_DB_URL, BACKUP_AGE_RECIPIENT vagy JARVIS_BACKUP_SOURCE_PROJECT_REF.")
    local_test = (
        os.environ.get("JARVIS_BACKUP_ALLOW_LOCAL_TEST_DB", "").strip().lower() == "true"
        and _is_loopback_db_url(db_url)
    )
    actual_ref = _validated_project_ref(db_url, allow_local_test=local_test)
    expected_ref = "local-test" if local_test else PRODUCTION_PROJECT_REF
    if source_ref != expected_ref or actual_ref != expected_ref:
        raise BackupError("A mentés forrásprojekt-azonosítója nem egyezik az engedélyezett JARVIS-forrással.")
    if not all(shutil.which(program) for program in ("pg_dump", "pg_restore", "age")):
        raise BackupError("A mentéshez a pg_dump, pg_restore és age program szükséges.")

    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        output_dir.chmod(0o700)
    except OSError:
        pass
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_id = f"{BACKUP_PREFIX}-{stamp}-{uuid.uuid4()}"
    final_path = output_dir / f"{backup_id}.tar.gz.age"

    with tempfile.TemporaryDirectory(prefix="jarvis-db-backup-") as tmp:
        work = Path(tmp)
        schema = work / "schema.sql"
        data = work / "data.sql"
        dump = work / "database.dump"
        manifest_path = work / "manifest.json"
        archive = work / "backup.tar.gz"

        # One custom-format pg_dump gives schema and data the same MVCC snapshot.
        # Splitting that immutable dump with pg_restore avoids cross-command drift.
        # PGPASSWORD is inherited by libpq and is never placed in command arguments.
        safe_url, db_env = _connection_env_and_url(db_url, work)
        run_checked([
            "pg_dump", "--no-password", "--dbname", safe_url,
            "--schema=public", "--no-owner", "--no-privileges",
            "--format=custom", "--file", str(dump),
        ], env=db_env)
        run_checked([
            "pg_restore", "--schema-only", "--no-owner", "--no-privileges",
            "--file", str(schema), str(dump),
        ])
        run_checked([
            "pg_restore", "--data-only", "--no-owner", "--no-privileges",
            "--file", str(data), str(dump),
        ])
        if not dump.is_file() or not schema.is_file() or not data.is_file() or schema.stat().st_size == 0:
            raise BackupError("A pg_dump/pg_restore nem készített teljes sémamentést és adatmentést.")

        manifest = {
            "format_version": 1,
            "backup_id": backup_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_project_ref": actual_ref,
            "included_schemas": ["public"],
            "included_objects": "all public schema objects and table data, including legacy public tables",
            "snapshot_consistency": "schema and data extracted from one pg_dump custom archive",
            "excluded": [
                "Supabase-managed auth/storage/realtime schemas and platform internals",
                "Supabase Storage object binaries (metadata only is not a file backup)",
                "database role passwords and project secrets",
            ],
            "files": {
                "schema.sql": {"sha256": sha256_file(schema), "bytes": schema.stat().st_size},
                "data.sql": {"sha256": sha256_file(data), "bytes": data.stat().st_size},
            },
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with tarfile.open(archive, "w:gz") as tar:
            for name in ("manifest.json", "schema.sql", "data.sql"):
                tar.add(work / name, arcname=name)

        encrypted_tmp = work / final_path.name
        run_checked(["age", "--recipient", recipient, "--output", str(encrypted_tmp), str(archive)])
        if not encrypted_tmp.is_file() or encrypted_tmp.stat().st_size == 0:
            raise BackupError("Az age titkosított mentés nem jött létre.")
        os.replace(encrypted_tmp, final_path)
        try:
            final_path.chmod(0o600)
        except OSError:
            pass

    return final_path


def _safe_extract(archive: Path, destination: Path) -> dict:
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        names = {m.name for m in members}
        if len(members) != len(ALLOWED_ARCHIVE_FILES) or names != ALLOWED_ARCHIVE_FILES or any(not m.isfile() for m in members):
            raise BackupError("A mentés archívuma nem a várt, biztonságos fájlkészletet tartalmazza.")
        for member in members:
            if Path(member.name).name != member.name:
                raise BackupError("Az archívum tiltott elérési utat tartalmaz.")
        tar.extractall(destination, members=members)

    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    source_ref = manifest.get("source_project_ref")
    local_test_archive = (
        source_ref == "local-test"
        and (
            os.environ.get("JARVIS_BACKUP_ALLOW_LOCAL_TEST_DB", "").strip().lower() == "true"
            or os.environ.get("JARVIS_RESTORE_ALLOW_LOCAL_TEST_DB", "").strip().lower() == "true"
        )
    )
    if manifest.get("format_version") != 1 or (
        source_ref != PRODUCTION_PROJECT_REF and not local_test_archive
    ):
        raise BackupError("Ismeretlen formátum vagy nem engedélyezett JARVIS-forrásból származó mentés.")
    for name in ("schema.sql", "data.sql"):
        expected = manifest.get("files", {}).get(name, {}).get("sha256")
        if not expected or sha256_file(destination / name) != expected:
            raise BackupError(f"A(z) {name} ellenőrzőösszege hibás.")
    return manifest


def _restore_sql_text(schema_sql: str, data_sql: str) -> str:
    """Restore into Supabase's existing public schema, not by recreating it."""
    schema_sql = re.sub(
        r"(?im)^\s*CREATE\s+SCHEMA\s+(?:IF\s+NOT\s+EXISTS\s+)?public(?:\s+AUTHORIZATION\s+[^;]+)?\s*;\s*$",
        "",
        schema_sql,
    )
    schema_sql = re.sub(
        r"(?im)^\s*ALTER\s+SCHEMA\s+public\s+OWNER\s+TO\s+[^;]+;\s*$",
        "",
        schema_sql,
    )
    return schema_sql + chr(10) + data_sql

def verify_backup(archive_path: Path) -> dict:
    """Decrypt a backup and verify its exact archive contents and SHA-256 manifest."""
    identity = os.environ.get("AGE_IDENTITY_FILE", "")
    if not identity:
        raise BackupError("A mentés ellenőrzéséhez AGE_IDENTITY_FILE szükséges.")
    identity_path = Path(identity)
    if not identity_path.is_file():
        raise BackupError("Az AGE_IDENTITY_FILE nem található.")
    if os.name == "posix" and identity_path.stat().st_mode & 0o077:
        raise BackupError("Az age privát kulcs fájl jogosultsága túl nyitott; állítsd 0600-ra.")
    if not archive_path.is_file() or not shutil.which("age"):
        raise BackupError("A mentési fájl vagy az age program nem található.")
    with tempfile.TemporaryDirectory(prefix="jarvis-db-verify-") as tmp:
        work = Path(tmp)
        decrypted = work / "backup.tar.gz"
        extracted = work / "extracted"
        extracted.mkdir()
        run_checked([
            "age", "--decrypt", "--identity", str(identity_path),
            "--output", str(decrypted), str(archive_path),
        ])
        return _safe_extract(decrypted, extracted)


def restore_backup(archive_path: Path, target_ref: str, confirmed: bool = False) -> None:
    if not confirmed:
        raise BackupError("A visszaállításhoz explicit --confirm-restore megerősítés szükséges.")
    db_url = os.environ.get("JARVIS_RESTORE_DB_URL", "")
    allowed_ref = os.environ.get("JARVIS_RESTORE_ALLOWED_PROJECT_REF", "")
    identity = os.environ.get("AGE_IDENTITY_FILE", "")
    if not db_url or not allowed_ref or not identity:
        raise BackupError("Hiányzó konfiguráció: JARVIS_RESTORE_DB_URL, JARVIS_RESTORE_ALLOWED_PROJECT_REF vagy AGE_IDENTITY_FILE.")
    if target_ref == PRODUCTION_PROJECT_REF:
        raise BackupError("TILTVA: visszaállítás az éles JARVIS-adatbázisra nem engedélyezett.")
    local_test = (
        os.environ.get("JARVIS_RESTORE_ALLOW_LOCAL_TEST_DB", "").strip().lower() == "true"
        and _is_loopback_db_url(db_url)
    )
    actual_ref = _validated_project_ref(db_url, allow_local_test=local_test)
    if local_test:
        if target_ref != "local-test" or allowed_ref != "local-test":
            raise BackupError("A lokális restore csak a local-test azonosítóval engedélyezett.")
    elif target_ref != allowed_ref:
        raise BackupError("A célprojekt nem egyezik a külön engedélyezett tesztprojekt-azonosítóval.")
    if actual_ref != target_ref:
        raise BackupError("A cél DB URL és a megadott célprojekt-azonosító nem egyezik.")
    identity_path = Path(identity)
    if not identity_path.is_file():
        raise BackupError("Az AGE_IDENTITY_FILE nem található.")
    if os.name == "posix" and identity_path.stat().st_mode & 0o077:
        raise BackupError("Az age privát kulcs fájl jogosultsága túl nyitott; állítsd 0600-ra.")
    if not archive_path.is_file():
        raise BackupError("A mentési fájl nem található.")
    if not shutil.which("age") or not shutil.which("psql"):
        raise BackupError("A visszaállításhoz az age és a psql program szükséges.")

    with tempfile.TemporaryDirectory(prefix="jarvis-db-restore-") as tmp:
        work = Path(tmp)
        decrypted = work / "backup.tar.gz"
        run_checked(["age", "--decrypt", "--identity", identity, "--output", str(decrypted), str(archive_path)])
        manifest = _safe_extract(decrypted, work)
        if manifest["source_project_ref"] == target_ref and not local_test:
            raise BackupError("A forrás és cél projekt nem lehet azonos.")
        # Refuse any non-empty public schema: restore is only allowed into a fresh,
        # isolated project. This prevents overwriting existing data.
        safe_url, db_env = _connection_env_and_url(db_url, work)
        count = run_checked([
            "psql", "--no-psqlrc", "--tuples-only", "--no-align",
            "--command",
            "SELECT (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f','S')) + (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public') + (SELECT count(*) FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace WHERE n.nspname='public' AND t.typtype IN ('c','d','e','r','m'));",
            "--dbname", safe_url,
        ], env=db_env)
        try:
            public_tables = int(count.strip())
        except ValueError as exc:
            raise BackupError("Nem sikerült ellenőrizni a cél public séma ürességét.") from exc
        if public_tables != 0:
            raise BackupError("A cél public séma nem üres; a visszaállítás biztonsági okból megszakadt.")

        combined = work / "restore.sql"
        schema_text = (work / "schema.sql").read_text(encoding="utf-8")
        data_text = (work / "data.sql").read_text(encoding="utf-8")
        combined.write_text(
            "-- Restrict default table privileges before restoring the public schema." + chr(10)
            + "ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated;" + chr(10)
            + "ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM anon, authenticated;" + chr(10)
            + _restore_sql_text(schema_text, data_text),
            encoding="utf-8",
        )
        run_checked([
            "psql", "--no-psqlrc", "--single-transaction",
            "--set", "ON_ERROR_STOP=1",
            "--file", str(combined),
            "--dbname", safe_url,
        ], env=db_env)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    backup_parser = sub.add_parser("backup", help="Encrypted logical backup of JARVIS public schema")
    backup_parser.add_argument("--output-dir", type=Path, default=Path(".private-backups"))
    verify_parser = sub.add_parser("verify", help="Decrypt and verify a backup archive and its SHA-256 manifest")
    verify_parser.add_argument("--archive", type=Path, required=True)
    restore_parser = sub.add_parser("restore", help="Restore only into a fresh, explicitly allowed non-production project")
    restore_parser.add_argument("--archive", type=Path, required=True)
    restore_parser.add_argument("--target-project-ref", required=True)
    restore_parser.add_argument("--confirm-restore", action="store_true")
    args = parser.parse_args()

    try:
        if args.command == "backup":
            result = create_backup(args.output_dir)
            print(f"Titkosított mentés elkészült: {result.name}")
        elif args.command == "verify":
            manifest = verify_backup(args.archive)
            print(f"Mentés ellenőrizve: {manifest['backup_id']}")
        else:
            restore_backup(args.archive, args.target_project_ref, args.confirm_restore)
            print("A visszaállítás befejeződött az elkülönített célprojektben.")
    except (BackupError, OSError, tarfile.TarError, json.JSONDecodeError) as exc:
        report_error(
            exc, module="supabase_backup",
            operation={"backup": "create_backup", "verify": "verify_backup", "restore": "restore_backup"}[args.command],
            severity="error",
        )
        parser.exit(2, f"HIBA: {sanitize_log_text(exc, max_length=1000)}\n")
    except Exception as exc:
        report_error(
            exc, module="supabase_backup",
            operation="create_backup" if args.command == "backup" else "restore_backup",
            severity="critical",
        )
        parser.exit(2, "HIBA: váratlan hiba történt; a részleteket a helyi hibajelentés rögzítette.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
