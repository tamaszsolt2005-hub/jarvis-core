from reply_analyzer import fallback_classification

def test_unsubscribe_is_rejected():
    assert fallback_classification("Kérem, iratkoztassanak le.") == "opt_out"

def test_negative_reply_is_rejected():
    assert fallback_classification("Köszönöm, nem érdekel.") == "rejected"

def test_positive_reply_is_interested():
    assert fallback_classification("Érdekel az árajánlat.") == "interested"

def test_later_reply_is_later():
    assert fallback_classification("Keressenek inkább jövő hónapban.") == "later"

def test_unknown_reply_is_unknown():
    assert fallback_classification("Köszönöm az üzenetet.") == "unknown"


def test_classify_reply_uses_model_only_for_unknown_fallback(monkeypatch):
    import reply_analyzer

    monkeypatch.setattr(reply_analyzer, "generate_text", lambda _prompt: "interested.")
    assert reply_analyzer.classify_reply("Köszönöm az üzenetet.") == "interested"
    monkeypatch.setattr(reply_analyzer, "generate_text", lambda _prompt: "unsupported label")
    assert reply_analyzer.classify_reply("Köszönöm az üzenetet.") == "unknown"
    assert reply_analyzer.classify_reply("Kérem, ne keressenek többet.") == "opt_out"


def test_classify_reply_reports_model_failure_and_returns_unknown(monkeypatch):
    import reply_analyzer

    reports = []
    monkeypatch.setattr(
        reply_analyzer, "generate_text",
        lambda _prompt: (_ for _ in ()).throw(RuntimeError("mock classifier outage")),
    )
    monkeypatch.setattr(reply_analyzer, "report_error", lambda error, **kwargs: reports.append((error, kwargs)))
    assert reply_analyzer.classify_reply("Köszönöm az üzenetet.") == "unknown"
    assert reports[0][1]["operation"] == "classify_reply_with_model"
    assert reports[0][1]["severity"] == "warning"
