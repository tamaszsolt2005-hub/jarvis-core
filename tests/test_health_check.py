from health_check import REQUIRED_TABLES, run_self_diagnostics


class FakeResponse:
    text = "OK"


class FakeModels:
    def generate_content(self, **_kwargs):
        return FakeResponse()


class FakeGemini:
    models = FakeModels()


class FakeResult:
    data = []


class FakeQuery:
    def select(self, _columns):
        return self

    def limit(self, _limit):
        return self

    def execute(self):
        return FakeResult()


class FakeDB:
    def table(self, _name):
        return FakeQuery()


def test_diagnostics_reports_missing_configuration_without_connecting(monkeypatch):
    import health_check

    monkeypatch.setattr(health_check, "get_secret", lambda _name: None)
    monkeypatch.setattr(health_check, "get_supabase", lambda: (_ for _ in ()).throw(AssertionError("must not connect")))
    monkeypatch.setattr(health_check, "get_gemini_client", lambda: (_ for _ in ()).throw(AssertionError("must not connect")))
    report = run_self_diagnostics()
    assert "1/15" in report  # Only the hard-coded email safety lock can pass without secrets.
    assert "SUPABASE_URL" in report
    assert "GEMINI_API_KEY" in report
    assert "E-mail-küldési biztonsági zár" in report
    assert "nem módosít" in report


def test_diagnostics_checks_all_required_tables_and_gemini(monkeypatch):
    import health_check

    values = {
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "test-secret",
        "SUPABASE_KEY": None,
        "GEMINI_API_KEY": "test-gemini",
        "JARVIS_DASHBOARD_PASSWORD": "test-password",
    }
    monkeypatch.setattr(health_check, "get_secret", lambda name: values.get(name))
    monkeypatch.setattr(health_check, "get_supabase", lambda: FakeDB())
    monkeypatch.setattr(health_check, "get_gemini_client", lambda: FakeGemini())
    report = run_self_diagnostics()
    assert "15/15" in report
    for table in REQUIRED_TABLES:
        assert f"Supabase tábla: {table}" in report
    assert "Gemini API próbakérés | OK" in report
    assert "Supabase oszlop: leads.website | OK" in report
    assert "Supabase oszlop: logs.level | OK" in report
    assert "test-secret" not in report
    assert "test-gemini" not in report


def test_diagnostics_marks_missing_table_as_attention(monkeypatch):
    import health_check

    class BrokenDB:
        def table(self, name):
            if name == "jarvis_memory":
                raise RuntimeError("missing table")
            return FakeQuery()

    values = {
        "SUPABASE_URL": "url", "SUPABASE_SERVICE_ROLE_KEY": "key",
        "GEMINI_API_KEY": None, "JARVIS_DASHBOARD_PASSWORD": "pw",
    }
    monkeypatch.setattr(health_check, "get_secret", lambda name: values.get(name))
    monkeypatch.setattr(health_check, "get_supabase", lambda: BrokenDB())
    report = run_self_diagnostics()
    assert "Supabase tábla: jarvis_memory | FIGYELMET IGÉNYEL" in report
    assert "Supabase oszlop: leads.website | OK" in report
    assert "Supabase oszlop: logs.level | OK" in report
    assert "Gemini API próbakérés | FIGYELMET IGÉNYEL" in report


def test_diagnostics_reports_supabase_initialization_failure_without_business_writes(monkeypatch):
    import health_check

    values = {
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_KEY": "mock-key",
        "GEMINI_API_KEY": None,
        "JARVIS_DASHBOARD_PASSWORD": "mock-password",
    }
    reports = []
    monkeypatch.setattr(health_check, "get_secret", lambda name: values.get(name))
    monkeypatch.setattr(
        health_check, "get_supabase",
        lambda: (_ for _ in ()).throw(RuntimeError("mock connection failure")),
    )
    monkeypatch.setattr(
        health_check, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )

    report = run_self_diagnostics()

    assert "Supabase kapcsolat | FIGYELMET IGÉNYEL" in report
    assert "Supabase tábla: leads | FIGYELMET IGÉNYEL" in report
    assert "Supabase oszlop: leads.website | FIGYELMET IGÉNYEL" in report
    assert reports[0][1]["operation"] == "initialize_supabase"
    assert reports[0][1]["severity"] == "warning"


def test_diagnostics_reports_missing_optional_columns(monkeypatch):
    import health_check

    values = {
        "SUPABASE_URL": "url",
        "SUPABASE_SERVICE_ROLE_KEY": "key",
        "GEMINI_API_KEY": None,
        "JARVIS_DASHBOARD_PASSWORD": "pw",
    }
    reports = []

    class Query(FakeQuery):
        def __init__(self, table):
            self.table = table

        def select(self, columns):
            if self.table == "leads" and columns == "website":
                raise RuntimeError("column leads.website does not exist")
            if self.table == "logs" and columns == "level":
                raise RuntimeError("column logs.level does not exist")
            return self

    class DB:
        def table(self, name):
            return Query(name)

    monkeypatch.setattr(health_check, "get_secret", lambda name: values.get(name))
    monkeypatch.setattr(health_check, "get_supabase", lambda: DB())
    monkeypatch.setattr(
        health_check, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )

    report = run_self_diagnostics()

    assert "Supabase oszlop: leads.website | FIGYELMET IGÉNYEL" in report
    assert "Supabase oszlop: logs.level | FIGYELMET IGÉNYEL" in report
    assert {item[1]["operation"] for item in reports} == {
        "probe_leads_website", "probe_logs_level"
    }


def test_diagnostics_handles_empty_gemini_response_and_enabled_email_lock(monkeypatch):
    import email_utils
    import health_check

    values = {
        "SUPABASE_URL": "url",
        "SUPABASE_SERVICE_ROLE_KEY": "key",
        "GEMINI_API_KEY": "gemini",
        "JARVIS_DASHBOARD_PASSWORD": "pw",
    }

    class EmptyModels:
        def generate_content(self, **_kwargs):
            return type("Response", (), {"text": " "})()

    class EmptyGemini:
        models = EmptyModels()

    monkeypatch.setattr(health_check, "get_secret", lambda name: values.get(name))
    monkeypatch.setattr(health_check, "get_supabase", lambda: FakeDB())
    monkeypatch.setattr(health_check, "get_gemini_client", lambda: EmptyGemini())
    monkeypatch.setattr(email_utils, "EMAIL_DELIVERY_ENABLED", True)

    report = run_self_diagnostics()

    assert "Gemini API próbakérés | FIGYELMET IGÉNYEL" in report
    assert "E-mail-küldési biztonsági zár | FIGYELMET IGÉNYEL" in report


def test_diagnostics_reports_gemini_transport_failure(monkeypatch):
    import health_check

    values = {
        "SUPABASE_URL": None,
        "SUPABASE_SERVICE_ROLE_KEY": None,
        "SUPABASE_KEY": None,
        "GEMINI_API_KEY": "gemini",
        "JARVIS_DASHBOARD_PASSWORD": None,
    }
    reports = []

    class BrokenModels:
        def generate_content(self, **_kwargs):
            raise TimeoutError("mock Gemini timeout")

    class BrokenGemini:
        models = BrokenModels()

    monkeypatch.setattr(health_check, "get_secret", lambda name: values.get(name))
    monkeypatch.setattr(health_check, "get_gemini_client", lambda: BrokenGemini())
    monkeypatch.setattr(
        health_check, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )

    report = run_self_diagnostics()

    assert "Gemini API próbakérés | FIGYELMET IGÉNYEL" in report
    assert reports[0][1]["operation"] == "probe_gemini"
    assert reports[0][1]["severity"] == "warning"
