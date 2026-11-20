#!/usr/bin/env python3
"""Encrypted public-schema backup; restore is hard-blocked for production."""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, tempfile, uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

PRODUCTION_REF = "kiutreccucbegskxowek"
BACKUP_DIR = Path(os.getenv("JARVIS_BACKUP_DIR", "private_backups"))

class BackupError(RuntimeError): pass

def required(key):
    value = os.getenv(key, "").strip()
    if not value: raise BackupError("Missing required environment variable: " + key)
    return value

def service_file(url, path, name):
    p = urlparse(url)
    if p.scheme not in ("postgres", "postgresql") or not p.hostname or not p.path or not p.username:
        raise BackupError("Invalid PostgreSQL connection URI.")
    def q(v): return "'" + v.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "") + "'"
    path.write_text(f"[{name}]\nhost={q(p.hostname)}\nport={p.port or 5432}\ndbname={q(unquote(p.path[1:]))}\nuser={q(unquote(p.username))}\npassword={q(unquote(p.password or ''))}\nsslmode=require\n")
    path.chmod(0o600)
    return path, p.hostname

def run(args, env):
    try:
        subprocess.run(args, env=env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError as e: raise BackupError("Missing executable: " + args[0]) from e
    except subprocess.CalledProcessError as e:
        lines = (e.stderr or "").strip().splitlines()
        raise BackupError(f"{args[0]} failed (exit {e.returncode}): {lines[-1][:250] if lines else 'no details'}") from e

def tools(*names):
    missing = [n for n in names if shutil.which(n) is None]
    if missing: raise BackupError("Missing executable(s): " + ", ".join(missing))

def backup():
    tools("pg_dump", "age")
    ref, url, recipient = required("JARVIS_BACKUP_SOURCE_PROJECT_REF"), required("JARVIS_BACKUP_DATABASE_URL"), required("JARVIS_BACKUP_AGE_RECIPIENT")
    if ref != PRODUCTION_REF: raise BackupError("Source project ref mismatch.")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True); BACKUP_DIR.chmod(0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bid = f"jarvis-public-{stamp}-{uuid.uuid4().hex[:12]}"
    enc, manifest = BACKUP_DIR / f"{bid}.dump.age", BACKUP_DIR / f"{bid}.manifest.json"
    with tempfile.TemporaryDirectory(prefix="jarvis-db-") as td:
        td = Path(td); svc, host = service_file(url, td / "pg_service.conf", "jarvis_backup")
        if ref not in host: raise BackupError("Database host does not match source project ref.")
        env = os.environ.copy(); env["PGSERVICEFILE"] = str(svc)
        dump = td / "db.dump"
        run(["pg_dump", "--format=custom", "--no-owner", "--no-acl", "--schema=public", "--dbname=service=jarvis_backup", "--file", str(dump)], env)
        if not dump.is_file() or dump.stat().st_size == 0: raise BackupError("Empty pg_dump archive.")
        run(["age", "--recipient", recipient, "--output", str(enc), str(dump)], env)
    digest = hashlib.sha256(enc.read_bytes()).hexdigest()
    data = {"backup_id": bid, "created_at": datetime.now(timezone.utc).isoformat(), "source_project_ref": ref, "scope": "public schema DDL and data", "format": "pg_dump custom + age", "ciphertext_sha256": digest, "encrypted_file": enc.name, "includes_auth_users": False, "includes_storage_objects": False}
    manifest.write_text(json.dumps(data, indent=2) + "\n"); enc.chmod(0o600); manifest.chmod(0o600)
    print(json.dumps({"backup_id": bid, "encrypted_file": str(enc), "manifest_file": str(manifest), "bytes": enc.stat().st_size}, indent=2))

def restore(archive, confirmed):
    tools("pg_restore", "age")
    if not confirmed: raise BackupError("Restore blocked: --confirm-restore is required.")
    ref = required("JARVIS_RESTORE_TARGET_PROJECT_REF")
    if not re.fullmatch(r"[a-z0-9]{20}", ref): raise BackupError("Malformed restore target project ref.")
    if ref == PRODUCTION_REF: raise BackupError("FATAL: restore to JARVIS production is permanently blocked.")
    identity = Path(required("JARVIS_RESTORE_AGE_IDENTITY_FILE")).expanduser()
    if not identity.is_file(): raise BackupError("Age identity file not found.")
    url = required("JARVIS_RESTORE_DATABASE_URL")
    mf = archive.with_name(archive.name.replace(".dump.age", ".manifest.json"))
    if not archive.is_file() or not mf.is_file(): raise BackupError("Archive or manifest missing.")
    meta = json.loads(mf.read_text())
    if meta.get("source_project_ref") != PRODUCTION_REF: raise BackupError("Manifest source ref mismatch.")
    if hashlib.sha256(archive.read_bytes()).hexdigest() != meta.get("ciphertext_sha256"): raise BackupError("Checksum mismatch; restore refused.")
    with tempfile.TemporaryDirectory(prefix="jarvis-restore-") as td:
        td = Path(td); svc, host = service_file(url, td / "pg_service.conf", "jarvis_restore")
        if ref not in host or PRODUCTION_REF in host: raise BackupError("Restore database host does not match the explicit non-production target.")
        env = os.environ.copy(); env["PGSERVICEFILE"] = str(svc); dump = td / "db.dump"
        run(["age", "--decrypt", "--identity", str(identity), "--output", str(dump), str(archive)], env)
        run(["pg_restore", "--clean", "--if-exists", "--no-owner", "--no-acl", "--exit-on-error", "--schema=public", "--dbname=service=jarvis_restore", str(dump)], env)
    print(json.dumps({"restored_backup_id": meta["backup_id"], "target_project_ref": ref, "schema": "public"}, indent=2))

def main():
    p = argparse.ArgumentParser(); sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("backup")
    r = sub.add_parser("restore"); r.add_argument("--archive", required=True, type=Path); r.add_argument("--confirm-restore", action="store_true")
    a = p.parse_args()
    try:
        backup() if a.cmd == "backup" else restore(a.archive, a.confirm_restore)
    except (BackupError, OSError, ValueError, json.JSONDecodeError) as e:
        print("JARVIS backup error: " + str(e), file=sys.stderr); return 2
    return 0

if __name__ == "__main__": raise SystemExit(main())
