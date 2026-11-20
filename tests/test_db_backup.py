import hashlib, json
from pathlib import Path
import pytest
import scripts.db_backup as backup

def test_restore_requires_confirmation(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_RESTORE_TARGET_PROJECT_REF", "abcdefghij1234567890")
    with pytest.raises(backup.BackupError, match="confirm-restore"):
        backup.restore(tmp_path / "missing.dump.age", False)

def test_production_target_is_always_blocked(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_RESTORE_TARGET_PROJECT_REF", backup.PRODUCTION_REF)
    with pytest.raises(backup.BackupError, match="permanently blocked"):
        backup.restore(tmp_path / "missing.dump.age", True)

def test_wrong_target_host_is_blocked(monkeypatch, tmp_path):
    identity = tmp_path / "age.key"; identity.write_text("dummy")
    archive = tmp_path / "a.dump.age"; archive.write_bytes(b"ciphertext")
    (tmp_path / "a.manifest.json").write_text(json.dumps({"backup_id":"a","source_project_ref":backup.PRODUCTION_REF,"ciphertext_sha256":hashlib.sha256(b"ciphertext").hexdigest()}))
    monkeypatch.setenv("JARVIS_RESTORE_TARGET_PROJECT_REF", "abcdefghij1234567890")
    monkeypatch.setenv("JARVIS_RESTORE_AGE_IDENTITY_FILE", str(identity))
    monkeypatch.setenv("JARVIS_RESTORE_DATABASE_URL", "postgresql://u:p@db.wrongprojectref123456.supabase.co:5432/postgres")
    monkeypatch.setattr(backup, "tools", lambda *a: None)
    with pytest.raises(backup.BackupError, match="host does not match"):
        backup.restore(archive, True)

def test_checksum_mismatch_is_blocked(monkeypatch, tmp_path):
    identity = tmp_path / "age.key"; identity.write_text("dummy")
    archive = tmp_path / "a.dump.age"; archive.write_bytes(b"tampered")
    (tmp_path / "a.manifest.json").write_text(json.dumps({"backup_id":"a","source_project_ref":backup.PRODUCTION_REF,"ciphertext_sha256":"0"*64}))
    monkeypatch.setenv("JARVIS_RESTORE_TARGET_PROJECT_REF", "abcdefghij1234567890")
    monkeypatch.setenv("JARVIS_RESTORE_AGE_IDENTITY_FILE", str(identity))
    monkeypatch.setenv("JARVIS_RESTORE_DATABASE_URL", "postgresql://u:p@db.abcdefghij1234567890.supabase.co:5432/postgres")
    monkeypatch.setattr(backup, "tools", lambda *a: None)
    with pytest.raises(backup.BackupError, match="Checksum mismatch"):
        backup.restore(archive, True)
