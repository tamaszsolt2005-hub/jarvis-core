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
