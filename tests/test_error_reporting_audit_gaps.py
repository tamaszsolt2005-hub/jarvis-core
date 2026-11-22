"""Regression tests for the remaining centralized error-reporting gaps."""
import sys
from types import SimpleNamespace

import pytest


def test_jarvis_status_reports_database_read_failure(monkeypatch, capsys):
    import jarvis_status

    reports = []
    monkeypatch.setattr(jarvis_status, "get_supabase", lambda: SimpleNamespace(
        table=lambda _name: SimpleNamespace(
            select=lambda *_args: SimpleNamespace(
                limit=lambda *_args: SimpleNamespace(
                    execute=lambda: (_ for _ in ()).throw(RuntimeError("password=private"))
                )
            )
        )
    ))
    monkeypatch.setattr(jarvis_status, "report_error", lambda error, **kwargs: reports.append((error, kwargs)))

    jarvis_status.run()

    assert len(reports) == 1
    assert reports[0][1]["module"] == "jarvis_status"
    assert reports[0][1]["operation"] == "load_lead_status_counts"
    output = capsys.readouterr().out
    assert "RuntimeError" in output
    assert "private" not in output


def test_global_research_job_reports_and_reraises_startup_failure(monkeypatch):
    import global_lead_research_job

    original = RuntimeError("database unavailable")
    reports = []
    monkeypatch.setattr(global_lead_research_job, "get_supabase", lambda: (_ for _ in ()).throw(original))
    monkeypatch.setattr(
        global_lead_research_job,
        "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )

    with pytest.raises(RuntimeError) as caught:
        global_lead_research_job.main()

    assert caught.value is original
    assert reports[0][0] is original
    assert reports[0][1]["module"] == "global_lead_research_job"
    assert reports[0][1]["severity"] == "critical"


def test_get_secret_registers_streamlit_secret_for_redaction(monkeypatch):
    import jarvis_common
    from jarvis_errors import sanitize_log_text

    fake_streamlit = SimpleNamespace(secrets=SimpleNamespace(get=lambda _name: "streamlit-private-value"))
    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)
    monkeypatch.delenv("JARVIS_STREAMLIT_TEST_SECRET", raising=False)

    assert jarvis_common.get_secret("JARVIS_STREAMLIT_TEST_SECRET") == "streamlit-private-value"
    assert "streamlit-private-value" not in sanitize_log_text(
        "request failed: streamlit-private-value"
    )


def test_get_secret_reports_unexpected_streamlit_secret_access_error(monkeypatch):
    import jarvis_common

    class BrokenSecrets:
        def get(self, _name):
            raise RuntimeError("secret backend unavailable")

    reports = []
    monkeypatch.setitem(sys.modules, "streamlit", SimpleNamespace(secrets=BrokenSecrets()))
    monkeypatch.setattr(jarvis_common, "report_error", lambda error, **kwargs: reports.append((error, kwargs)))
    monkeypatch.setenv("JARVIS_STREAMLIT_FALLBACK", "fallback-value")

    assert jarvis_common.get_secret("JARVIS_STREAMLIT_FALLBACK") == "fallback-value"
    assert len(reports) == 1
    assert reports[0][1]["module"] == "jarvis_common"
    assert reports[0][1]["operation"] == "read_streamlit_secret:JARVIS_STREAMLIT_FALLBACK"


def test_missing_streamlit_secrets_file_is_not_reported_as_operational_error(monkeypatch):
    import jarvis_common

    class StreamlitSecretNotFoundError(Exception):
        pass

    class MissingSecrets:
        def get(self, _name):
            raise StreamlitSecretNotFoundError("No secrets file")

    reports = []
    monkeypatch.setitem(sys.modules, "streamlit", SimpleNamespace(secrets=MissingSecrets()))
    monkeypatch.setattr(jarvis_common, "report_error", lambda error, **kwargs: reports.append((error, kwargs)))
    monkeypatch.delenv("JARVIS_OPTIONAL_NOT_SET", raising=False)

    assert jarvis_common.get_secret("JARVIS_OPTIONAL_NOT_SET") is None
    assert reports == []


def test_get_secret_does_not_register_non_credential_configuration(monkeypatch):
    import jarvis_common
    from jarvis_errors import sanitize_log_text

    fake_streamlit = SimpleNamespace(secrets=SimpleNamespace(get=lambda _name: "gemini-3.8-flash"))
    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)
    assert jarvis_common.get_secret("GEMINI_MODEL") == "gemini-3.8-flash"
    assert "gemini-3.8-flash" in sanitize_log_text("Configured model: gemini-3.8-flash")
