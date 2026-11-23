from proactive_monitor_job import main


def test_job_runs_monitor_and_prints_report(monkeypatch, capsys):
    import proactive_monitor_job

    fake_db = object()
    calls = []
    monkeypatch.setattr(proactive_monitor_job, "get_supabase", lambda: fake_db)
    monkeypatch.setattr(
        proactive_monitor_job, "run_proactive_monitor",
        lambda db: calls.append(db) or "# Napi monitor\n",
    )

    main()

    assert calls == [fake_db]
    assert capsys.readouterr().out == "# Napi monitor\n"


def test_job_propagates_monitor_failure(monkeypatch):
    import pytest
    import proactive_monitor_job

    monkeypatch.setattr(proactive_monitor_job, "get_supabase", lambda: object())
    monkeypatch.setattr(
        proactive_monitor_job, "run_proactive_monitor",
        lambda _db: (_ for _ in ()).throw(ConnectionError("database unavailable")),
    )

    with pytest.raises(ConnectionError, match="database unavailable"):
        main()
