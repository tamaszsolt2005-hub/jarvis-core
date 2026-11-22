import pytest

import lead_gen


def test_csv_import_reports_database_startup_failure_and_reraises(monkeypatch):
    captured = []
    monkeypatch.setattr(
        lead_gen, "get_supabase",
        lambda: (_ for _ in ()).throw(RuntimeError("connection failed password=never-log-this")),
    )
    monkeypatch.setattr(
        lead_gen, "report_error",
        lambda error, **kwargs: captured.append((error, kwargs)),
    )

    with pytest.raises(RuntimeError, match="connection failed"):
        lead_gen.run("unused.csv")

    assert captured[0][1]["module"] == "lead_gen"
    assert captured[0][1]["operation"] == "import_reviewed_csv"
    assert captured[0][1]["severity"] == "error"
    assert captured[0][1]["db"] is None
