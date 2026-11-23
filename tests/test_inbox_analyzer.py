from inbox_analyzer import analyze_incoming_reply


def test_compatibility_analyzer_uses_shared_model_configuration(monkeypatch):
    import inbox_analyzer

    captured = {}

    class Response:
        text = "[INTERESTED]"

    class Models:
        def generate_content(self, **kwargs):
            captured.update(kwargs)
            return Response()

    class Client:
        models = Models()

    monkeypatch.setattr(inbox_analyzer.genai, "Client", lambda api_key: Client())
    monkeypatch.setattr(inbox_analyzer, "get_model_name", lambda: "gemini-3.8-flash")

    assert analyze_incoming_reply("Kérek ajánlatot", "dummy-key") == "interested"
    assert captured["model"] == "gemini-3.8-flash"


def test_compatibility_analyzer_handles_empty_and_all_model_labels(monkeypatch):
    import inbox_analyzer

    assert analyze_incoming_reply("", "dummy-key") == "later"

    class Response:
        def __init__(self, text):
            self.text = text
    class Models:
        def __init__(self, text):
            self.text = text
        def generate_content(self, **_kwargs):
            return Response(self.text)
    class Client:
        def __init__(self, text):
            self.models = Models(text)

    monkeypatch.setattr(inbox_analyzer.genai, "Client", lambda api_key: Client("[LATER]"))
    assert analyze_incoming_reply("Talán később", "dummy-key") == "later"
    monkeypatch.setattr(inbox_analyzer.genai, "Client", lambda api_key: Client("[REJECTED]"))
    assert analyze_incoming_reply("Nem kérem", "dummy-key") == "rejected"
    monkeypatch.setattr(inbox_analyzer.genai, "Client", lambda api_key: Client(None))
    assert analyze_incoming_reply("Válasz", "dummy-key") == "rejected"


def test_compatibility_analyzer_reports_provider_failure_and_falls_back(monkeypatch):
    import inbox_analyzer

    reports = []
    monkeypatch.setattr(
        inbox_analyzer.genai, "Client",
        lambda **_kwargs: (_ for _ in ()).throw(ConnectionError("mock Gemini outage")),
    )
    monkeypatch.setattr(inbox_analyzer, "report_error", lambda error, **kwargs: reports.append((error, kwargs)))
    assert analyze_incoming_reply("Ajánlatot kérek", "dummy-key") == "later"
    assert reports[0][1]["operation"] == "classify_incoming_reply"
    assert reports[0][1]["severity"] == "warning"
