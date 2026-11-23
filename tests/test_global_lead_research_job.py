import json

import pytest

import global_lead_research_job as job


def test_global_research_job_passes_safe_scope_and_prints_structured_result(monkeypatch, capsys):
    db = object()
    captured = {}
    audits = []

    monkeypatch.setattr(job, "get_service_supabase", lambda: db)
    monkeypatch.setattr(job, "get_research_market", lambda actual_db: "Hungary" if actual_db is db else None)
    monkeypatch.setattr(job, "audit_event", lambda actual_db, **kwargs: audits.append(kwargs) or True)

    def research(actual_db, prompt, **kwargs):
        captured.update({"db": actual_db, "prompt": prompt, **kwargs})
        return {
            "scope": "global",
            "saved_count": 3,
            "skipped_count": 2,
            "email_sending": "disabled",
            "contact_permission": "explicit_consent_required",
            "companies": [{"company_name": "Example Ltd"}],
        }

    monkeypatch.setattr(job, "research_global_companies", research)

    job.main()

    output = json.loads(capsys.readouterr().out)
    assert output["saved_count"] == 3
    assert output["contact_permission"] == "explicit_consent_required"
    assert captured["db"] is db
    assert captured["max_results"] == 15
    assert captured["market_country"] == "Hungary"
    assert "személyes elérhetőséget és hozzájárulást ne következtess ki" in captured["prompt"]
    assert [event["status"] for event in audits] == ["pending", "success"]
    assert audits[0]["operation_id"] == audits[1]["operation_id"]
    assert audits[1]["result"]["email_sending"] is False


def test_global_research_job_reports_startup_failure_and_reraises(monkeypatch):
    failure = RuntimeError("mock Supabase startup failure")
    reports = []
    monkeypatch.setattr(
        job, "get_service_supabase",
        lambda: (_ for _ in ()).throw(failure),
    )
    monkeypatch.setattr(
        job, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )

    with pytest.raises(RuntimeError) as caught:
        job.main()

    assert caught.value is failure
    assert reports[0][0] is failure
    assert reports[0][1]["module"] == "global_lead_research_job"
    assert reports[0][1]["operation"] == "run_daily_global_research"
    assert reports[0][1]["severity"] == "critical"
    assert reports[0][1]["db"] is None


def test_global_research_job_reports_research_failure_with_database_context(monkeypatch):
    failure = RuntimeError("mock research failure")
    db = object()
    reports = []
    audits = []
    monkeypatch.setattr(job, "get_service_supabase", lambda: db)
    monkeypatch.setattr(job, "get_research_market", lambda _db: "Hungary")
    monkeypatch.setattr(job, "audit_event", lambda actual_db, **kwargs: audits.append(kwargs) or True)
    monkeypatch.setattr(
        job, "research_global_companies",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(failure),
    )
    monkeypatch.setattr(
        job, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )

    with pytest.raises(RuntimeError) as caught:
        job.main()

    assert caught.value is failure
    assert reports[0][0] is failure
    assert reports[0][1]["db"] is db
    assert reports[0][1]["severity"] == "critical"
    assert [event["status"] for event in audits] == ["pending", "unknown"]
    assert audits[0]["operation_id"] == audits[1]["operation_id"]


def test_global_research_job_does_not_start_research_when_pending_audit_fails(monkeypatch):
    db = object()
    audits = []
    monkeypatch.setattr(job, "get_service_supabase", lambda: db)
    monkeypatch.setattr(job, "audit_event", lambda actual_db, **kwargs: audits.append(kwargs) or False)
    monkeypatch.setattr(
        job, "research_global_companies",
        lambda *_args, **_kwargs: pytest.fail("research must not start"),
    )
    monkeypatch.setattr(job, "report_error", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="pending audit"):
        job.main()

    assert [event["status"] for event in audits] == ["pending", "failed"]
    assert audits[0]["operation_id"] == audits[1]["operation_id"]
