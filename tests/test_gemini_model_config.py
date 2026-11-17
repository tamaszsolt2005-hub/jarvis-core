from jarvis_common import get_model_name


def test_default_model_is_current_stable_flash(monkeypatch):
    monkeypatch.setattr("jarvis_common.get_secret", lambda name, default=None: default)
    assert get_model_name() == "gemini-3.5-flash"


def test_retired_legacy_model_overrides_fall_back_to_current_default(monkeypatch):
    monkeypatch.setattr(
        "jarvis_common.get_secret",
        lambda name, default=None: "gemini-2.5-flash" if name == "GEMINI_MODEL" else default,
    )
    assert get_model_name() == "gemini-3.5-flash"


def test_explicit_non_legacy_model_override_is_preserved(monkeypatch):
    monkeypatch.setattr(
        "jarvis_common.get_secret",
        lambda name, default=None: "gemini-3.7-flash" if name == "GEMINI_MODEL" else default,
    )
    assert get_model_name() == "gemini-3.7-flash"
