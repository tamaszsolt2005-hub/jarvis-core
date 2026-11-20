"""Unit tests for JARVIS analytics aggregation and event labels."""
import pandas as pd

from jarvis_analytics import (
    _activity_label,
    _change_label,
    _daily_series,
    _module_label,
    _sparkline_svg,
    build_chat_analytics_context,
    is_analytics_question,
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



def test_analytics_intent_recognizes_hungarian_analytics_requests():
    assert is_analytics_question("Mutasd az analitikát")
    assert is_analytics_question("Kérek egy statisztikai trendet")
    assert is_analytics_question("Milyen diagramok vannak?")
    assert not is_analytics_question("Hozz létre egy új leadet")


def test_chat_analytics_uses_log_events_and_never_includes_raw_messages():
    records = [
        {"module": "chat", "level": "info", "message": "chat_request", "created_at": "2026-11-19T08:00:00Z"},
        {"module": "chat", "level": "info", "message": "chat_response", "created_at": "2026-11-19T08:01:00Z"},
        {"module": "lead_gen", "level": "error", "message": "private@example.com", "created_at": "2026-11-19T09:00:00Z"},
        {"module": "scraper", "level": "warning", "message": "sensitive warning detail", "created_at": "2026-11-19T10:00:00Z"},
    ]
    summary = build_chat_analytics_context(
        records,
        now=pd.Timestamp("2026-11-19T12:00:00+01:00").to_pydatetime(),
    )
    assert "Adatforrás: public.logs" in summary
    assert "chatkérés=1" in summary
    assert "AI-válasz esemény=1" in summary
    assert "hiba=1" in summary
    assert "figyelmeztetés=1" in summary
    assert "private@example.com" not in summary
    assert all(f"{days} nap:" in summary for days in (7, 30, 90, 365))
