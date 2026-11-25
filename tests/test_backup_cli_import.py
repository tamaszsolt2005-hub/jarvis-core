"""Direct CLI import regression for the production backup workflow entry point."""
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_backup_script_can_import_repository_modules_when_run_by_path(tmp_path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "supabase_backup.py"), "--help"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert "backup" in result.stdout.lower()
