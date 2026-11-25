from pathlib import Path


def test_production_backup_workflow_restores_into_disposable_postgres17():
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github" / "workflows" / "database-backup.yml"
    ).read_text(encoding="utf-8")
    assert "postgres:17" in workflow
    assert "JARVIS_RESTORE_ALLOWED_PROJECT_REF: local-test" in workflow
    assert "--target-project-ref local-test" in workflow
    assert "Separate PostgreSQL 17 restore verified" in workflow
    assert "kiutreccucbegskxowek" in workflow
