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


def test_dashboard_uses_polished_hungarian_workspace_copy():
    source = Path("dashboard.py").read_text(encoding="utf-8")
    assert "Üzleti döntések." in source
    assert "PRIVATE WORKSPACE" in source
    assert "READY" not in source
