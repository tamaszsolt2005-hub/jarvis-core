#!/usr/bin/env python3
"""Encrypted, off-site logical backup and guarded restore for the JARVIS Supabase DB.

Backups contain the complete public schema and public data. They deliberately do
not dump Supabase-managed auth/storage/realtime schemas or Storage object binaries.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

PRODUCTION_PROJECT_REF = "kiutreccucbegskxowek"
BACKUP_PREFIX = "jarvis-db"
ALLOWED_ARCHIVE_FILES = {"manifest.json", "schema.sql", "data.sql"}


class BackupError(RuntimeError):
    pass


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


def run_checked(args: list[str], *, env: dict[str, str] | None = None) -> str:
    try:
        result = subprocess.run(
            args, check=True, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env=env,
        )
        return result.stdout.strip()
    except FileNotFoundError as exc:
        raise BackupError(f"Hiányzó külső program: {args[0]}") from exc
    except subprocess.CalledProcessError as exc:
        # Never echo command arguments: they may contain a database URL/password.
        detail = (exc.stderr or "").splitlines()
        safe_detail = detail[-1][:300] if detail else "nincs részletes hibaüzenet"
        raise BackupError(f"A(z) {args[0]} parancs hibával leállt: {safe_detail}") from exc


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
    actual_ref = project_ref_from_db_url(db_url)
    if source_ref != PRODUCTION_PROJECT_REF or actual_ref != PRODUCTION_PROJECT_REF:
        raise BackupError("A mentés csak az előre rögzített JARVIS éles projektből indulhat; a forrásazonosító nem egyezik.")
    if not shutil.which("supabase") or not shutil.which("age"):
        raise BackupError("A mentéshez a supabase CLI és az age program szükséges.")

    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_id = f"{BACKUP_PREFIX}-{stamp}-{uuid.uuid4()}"
    final_path = output_dir / f"{backup_id}.tar.gz.age"

    with tempfile.TemporaryDirectory(prefix="jarvis-db-backup-") as tmp:
        work = Path(tmp)
        schema = work / "schema.sql"
        data = work / "data.sql"
        manifest_path = work / "manifest.json"
        archive = work / "backup.tar.gz"

        # Capture only application-owned public schema objects and data.
        run_checked(["supabase", "db", "dump", f"--remote={db_url}", "--schema", "public", "--file", str(schema)])
        run_checked(["supabase", "db", "dump", f"--remote={db_url}", "--schema", "public", "--data-only", "--use-copy", "--file", str(data)])
        if not schema.is_file() or not data.is_file() or schema.stat().st_size == 0:
            raise BackupError("A Supabase CLI nem készített teljes sémamentést és adatmentést.")

        manifest = {
            "format_version": 1,
            "backup_id": backup_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_project_ref": actual_ref,
            "included_schemas": ["public"],
            "included_objects": "all public schema objects and table data, including legacy public tables",
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

    return final_path


def _safe_extract(archive: Path, destination: Path) -> dict:
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        names = {m.name for m in members}
        if names != ALLOWED_ARCHIVE_FILES or any(not m.isfile() for m in members):
            raise BackupError("A mentés archívuma nem a várt, biztonságos fájlkészletet tartalmazza.")
        for member in members:
            if Path(member.name).name != member.name:
                raise BackupError("Az archívum tiltott elérési utat tartalmaz.")
        tar.extractall(destination, members=members)

    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format_version") != 1 or manifest.get("source_project_ref") != PRODUCTION_PROJECT_REF:
        raise BackupError("Ismeretlen formátum vagy nem JARVIS-forrásból származó mentés.")
    for name in ("schema.sql", "data.sql"):
        expected = manifest.get("files", {}).get(name, {}).get("sha256")
        if not expected or sha256_file(destination / name) != expected:
            raise BackupError(f"A(z) {name} ellenőrzőösszege hibás.")
    return manifest


def restore_backup(archive_path: Path, target_ref: str) -> None:
    db_url = os.environ.get("JARVIS_RESTORE_DB_URL", "")
    allowed_ref = os.environ.get("JARVIS_RESTORE_ALLOWED_PROJECT_REF", "")
    identity = os.environ.get("AGE_IDENTITY_FILE", "")
    if not db_url or not allowed_ref or not identity:
        raise BackupError("Hiányzó konfiguráció: JARVIS_RESTORE_DB_URL, JARVIS_RESTORE_ALLOWED_PROJECT_REF vagy AGE_IDENTITY_FILE.")
    if target_ref == PRODUCTION_PROJECT_REF:
        raise BackupError("TILTVA: visszaállítás az éles JARVIS-adatbázisra nem engedélyezett.")
    if target_ref != allowed_ref:
        raise BackupError("A célprojekt nem egyezik a külön engedélyezett tesztprojekt-azonosítóval.")
    if project_ref_from_db_url(db_url) != target_ref:
        raise BackupError("A cél DB URL és a megadott célprojekt-azonosító nem egyezik.")
    if not Path(identity).is_file():
        raise BackupError("Az AGE_IDENTITY_FILE nem található.")
    if not shutil.which("age") or not shutil.which("psql"):
        raise BackupError("A visszaállításhoz az age és a psql program szükséges.")
    if not archive_path.is_file():
        raise BackupError("A mentési fájl nem található.")

    with tempfile.TemporaryDirectory(prefix="jarvis-db-restore-") as tmp:
        work = Path(tmp)
        decrypted = work / "backup.tar.gz"
        run_checked(["age", "--decrypt", "--identity", identity, "--output", str(decrypted), str(archive_path)])
        manifest = _safe_extract(decrypted, work)
        if manifest["source_project_ref"] == target_ref:
            raise BackupError("A forrás és cél projekt nem lehet azonos.")
        # Refuse any non-empty public schema: restore is only allowed into a fresh,
        # isolated project. This prevents overwriting existing data.
        count = run_checked([
            "psql", "--no-psqlrc", "--tuples-only", "--no-align",
            "--command",
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f','S');",
            "--dbname", db_url,
        ])
        try:
            public_tables = int(count.strip())
        except ValueError as exc:
            raise BackupError("Nem sikerült ellenőrizni a cél public séma ürességét.") from exc
        if public_tables != 0:
            raise BackupError("A cél public séma nem üres; a visszaállítás biztonsági okból megszakadt.")

        run_checked([
            "psql", "--no-psqlrc", "--single-transaction",
            "--set", "ON_ERROR_STOP=1",
            "--file", str(work / "schema.sql"),
            "--file", str(work / "data.sql"),
            "--dbname", db_url,
        ])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    backup_parser = sub.add_parser("backup", help="Encrypted logical backup of JARVIS public schema")
    backup_parser.add_argument("--output-dir", type=Path, default=Path(".private-backups"))
    restore_parser = sub.add_parser("restore", help="Restore only into a fresh, explicitly allowed non-production project")
    restore_parser.add_argument("--archive", type=Path, required=True)
    restore_parser.add_argument("--target-project-ref", required=True)
    args = parser.parse_args()

    try:
        if args.command == "backup":
            result = create_backup(args.output_dir)
            print(f"Titkosított mentés elkészült: {result.name}")
        else:
            restore_backup(args.archive, args.target_project_ref)
            print("A visszaállítás befejeződött az elkülönített célprojektben.")
    except (BackupError, OSError, tarfile.TarError, json.JSONDecodeError) as exc:
        parser.exit(2, f"HIBA: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
