"""Unit tests for JARVIS analytics aggregation and event labels."""
import pandas as pd

from jarvis_analytics import (
    _activity_label,
    _change_label,
    _daily_series,
    _module_label,
    _sparkline_svg,
)


def test_daily_series_uses_budapest_calendar_days_and_fills_zeros():
    timestamps = pd.to_datetime(
        ["2026-11-18T22:30:00Z", "2026-11-19T08:00:00Z", "2026-11-19T09:00:00Z"],
        utc=True,
    ).tz_convert("Europe/Budapest")
    frame = pd.DataFrame({"local_ts": timestamps})

    counts = _daily_series(frame, ["2026-11-18", "2026-11-19", "2026-11-20"])

    assert counts.tolist() == [1, 2, 0]


def test_daily_series_can_filter_a_subset_of_events():
    timestamps = pd.to_datetime(
        ["2026-11-19T08:00:00Z", "2026-11-19T09:00:00Z"],
        utc=True,
    ).tz_convert("Europe/Budapest")
    frame = pd.DataFrame({"local_ts": timestamps, "kind": ["chat", "system"]})

    counts = _daily_series(frame, ["2026-11-19"], frame["kind"] == "chat")

    assert counts.tolist() == [1]


def test_daily_series_returns_real_zeroes_for_empty_period():
    frame = pd.DataFrame({"local_ts": pd.Series(dtype="datetime64[ns, UTC]")})

    counts = _daily_series(frame, ["2026-11-18", "2026-11-19"])

    assert counts.tolist() == [0, 0]


def test_module_labels_group_related_backend_modules():
    assert _module_label("lead_gen_debrecen") == "Leadkutatás"
    assert _module_label("dynamic_scraper") == "Weboldal-feldolgozás"
    assert _module_label("email_sender") == "E-mail modul"
    assert _module_label("chat") == "Chat"


def test_activity_labels_do_not_show_raw_log_messages():
    assert _activity_label({"module": "chat", "message": "chat_request", "level": "info"}) == "Beszélgetési kérés"
    assert _activity_label({"module": "chat", "message": "chat_response", "level": "info"}) == "AI-válasz elkészült"
    assert _activity_label({"module": "lead_gen", "message": "private details", "level": "error"}) == "Hibajelzés"


def test_period_delta_handles_zero_baseline_without_division_error():
    assert _change_label(4, 0) == "Új aktivitás"
    assert _change_label(0, 0) == "Nincs aktivitás"
    assert _change_label(15, 10) == "+50% az előző időszakhoz képest"
    assert _change_label(5, 10) == "-50% az előző időszakhoz képest"


def test_sparkline_svg_is_generated_from_supplied_daily_values():
    svg = _sparkline_svg([0, 2, 1, 4], "#00CFFF")

    assert svg.startswith("<svg")
    assert "#00CFFF" in svg
    assert "stroke-width" in svg
