"""Regression checks for the JARVIS premium Streamlit theme."""
from pathlib import Path
import tomllib


def test_streamlit_theme_is_defined_and_consistent():
    config = tomllib.loads(Path(".streamlit/config.toml").read_text(encoding="utf-8"))
    theme = config["theme"]
    assert theme["base"] == "dark"
    assert theme["primaryColor"] == "#82B4FF"
    assert theme["backgroundColor"] == "#0A1020"
    assert theme["secondaryBackgroundColor"] == "#111C30"
    assert theme["showWidgetBorder"] is True


def test_dashboard_uses_clean_hungarian_chat_workspace_copy():
    source = Path("dashboard.py").read_text(encoding="utf-8")
    analytics = Path("jarvis_analytics.py").read_text(encoding="utf-8")
    assert "Miben segíthetek ma?" in source
    assert "Your Personal AI Assistant" in source
    assert 'key="jarvis_nav_analytics"' in source
    assert "jarvis-analytics-title" in analytics
    assert "READY" not in source
