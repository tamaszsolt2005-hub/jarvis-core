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
    is_executive_analytics_report_request,
    build_executive_analytics_report,
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
    assert "Supabase-projekt létrehozva: 2026-11-13" in summary
    assert "Ténylegesen megfigyelt naplózási időszak:" in summary
    assert "A projekt létrehozása előtti kért időszakra nincs naplóadat" in summary
    assert "Adatforrás: public.logs" in summary
    assert "chatkérés=1" in summary
    assert "AI-válasz esemény=1" in summary
    assert "hiba=1" in summary
    assert "figyelmeztetés=1" in summary
    assert "private@example.com" not in summary
    assert all(f"{days} nap:" in summary for days in (7, 30, 90, 365))



def test_executive_analytics_report_request_is_detected():
    assert is_executive_analytics_report_request("Készíts 30 napos vezetői analitikai jelentést")
    assert not is_executive_analytics_report_request("Mutasd az analitikát")
    assert not is_executive_analytics_report_request("Miért hiányos az analitikai jelentés?")


def test_executive_report_uses_verified_project_date_and_distinguishes_log_window():
    records = [
        {"module": "chat", "level": "info", "message": "chat_request", "created_at": "2026-11-19T08:00:00Z"},
        {"module": "chat", "level": "info", "message": "chat_response", "created_at": "2026-11-19T08:01:00Z"},
        {"module": "email_sender", "level": "warning", "message": "private warning text", "created_at": "2026-11-13T18:33:00Z"},
        {"module": "lead_gen", "level": "error", "message": "private error text", "created_at": "2026-11-19T09:00:00Z"},
        {"module": "dynamic_scraper", "level": "info", "message": "scrape", "created_at": "2026-11-14T07:00:00Z"},
    ]
    report = build_executive_analytics_report(
        records, now=pd.Timestamp("2026-11-20T12:00:00+01:00").to_pydatetime()
    )
    assert "Supabase-projekt létrehozása:** 2026-11-13 17:02:24 CET" in report
    assert "2026-11-13 19:33:00 CET" in report
    assert "Összes naplózott esemény a 30 napos ablakban: **5**" in report
    assert "Hibaszintű esemény (error/critical/fatal): **1**" in report
    assert "Figyelmeztetés (warn/warning): **1**" in report
    assert "nem bizonyítja a modul leállását" in report
    assert "private warning text" not in report
    assert "private error text" not in report


def test_executive_report_handles_empty_logs_without_losing_project_metadata():
    report = build_executive_analytics_report(
        [], now=pd.Timestamp("2026-11-20T12:00:00+01:00").to_pydatetime()
    )
    assert "Supabase-projekt létrehozása:** 2026-11-13 17:02:24 CET" in report
    assert "Nem áll rendelkezésre érvényes időbélyegű naplórekord." in report
    assert "nincs esemény, ezért hibaarány nem számítható" in report



def test_executive_report_correlates_chat_outcomes_by_request_id():
    ts = "2026-11-19T08:00:00Z"
    records = [
        {"module": "chat", "level": "info", "message": "chat_request|request_id=" + "a" * 32, "created_at": ts},
        {"module": "chat", "level": "info", "message": "chat_response|request_id=" + "a" * 32, "created_at": "2026-11-19T08:00:01Z"},
        {"module": "chat", "level": "info", "message": "chat_request|request_id=" + "b" * 32, "created_at": ts},
        {"module": "chat", "level": "error", "message": "chat_error|request_id=" + "b" * 32, "created_at": "2026-11-19T08:00:02Z"},
        {"module": "chat", "level": "info", "message": "chat_request|request_id=" + "c" * 32, "created_at": ts},
        {"module": "chat", "level": "info", "message": "chat_request", "created_at": ts},
        {"module": "chat", "level": "info", "message": "chat_response", "created_at": "2026-11-19T08:00:03Z"},
    ]
    report = build_executive_analytics_report(
        records, now=pd.Timestamp("2026-11-20T12:00:00+01:00").to_pydatetime()
    )
    assert "sikeres **1**, sikertelen **1**, befejezetlen **1**" in report
    assert "Régi, request_id nélküli események: kérés **1**, válasz **1**" in report


def test_chat_activity_labels_support_correlated_event_messages():
    from jarvis_analytics import _activity_label

    assert _activity_label({"module": "chat", "message": "chat_request|request_id=" + "a" * 32, "level": "info"}) == "Beszélgetési kérés"
    assert _activity_label({"module": "chat", "message": "chat_response|request_id=" + "a" * 32, "level": "info"}) == "AI-válasz elkészült"


def _fake_streamlit():
    import jarvis_analytics

    class Context:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class FakeStreamlit:
        session_state = {}

        def markdown(self, *_args, **_kwargs):
            pass

        def columns(self, spec, **_kwargs):
            count = spec if isinstance(spec, int) else len(spec)
            return [Context() for _ in range(count)]

        def container(self, **_kwargs):
            return Context()

        def radio(self, *_args, **_kwargs):
            return "30 nap"

        def plotly_chart(self, *_args, **_kwargs):
            pass

        def error(self, *_args, **_kwargs):
            pass

        def caption(self, *_args, **_kwargs):
            pass

        def warning(self, *_args, **_kwargs):
            pass

    return FakeStreamlit()


def test_render_analytics_renders_empty_state_without_database_mutations(monkeypatch):
    import jarvis_analytics as analytics

    class Result:
        data = []

    class Query:
        def select(self, *_args):
            return self

        def gte(self, *_args):
            return self

        def lte(self, *_args):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def limit(self, *_args):
            return self

        def execute(self):
            return Result()

    class DB:
        def table(self, name):
            assert name == "logs"
            return Query()

    monkeypatch.setattr(analytics, "st", _fake_streamlit())
    analytics.render_analytics(DB())


def test_render_analytics_builds_charts_from_real_event_shapes(monkeypatch):
    from datetime import datetime, timedelta, timezone
    import jarvis_analytics as analytics

    now = datetime.now(timezone.utc)
    records = [
        {
            "module": "chat", "level": "info",
            "message": "chat_request|request_id=abc",
            "created_at": (now - timedelta(minutes=3)).isoformat(),
        },
        {
            "module": "chat", "level": "info",
            "message": "chat_response|request_id=abc",
            "created_at": (now - timedelta(minutes=2)).isoformat(),
        },
        {
            "module": "email_sender", "level": "error",
            "message": "private failure detail",
            "created_at": (now - timedelta(minutes=1)).isoformat(),
        },
        {
            "module": "follow_up", "level": "warning",
            "message": "private warning detail",
            "created_at": now.isoformat(),
        },
    ]

    class Result:
        data = records

    class Query:
        def select(self, *_args):
            return self

        def gte(self, *_args):
            return self

        def lte(self, *_args):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def limit(self, *_args):
            return self

        def execute(self):
            return Result()

    class DB:
        def table(self, name):
            assert name == "logs"
            return Query()

    fake_st = _fake_streamlit()
    charts = []
    fake_st.plotly_chart = lambda figure, **kwargs: charts.append(figure)
    monkeypatch.setattr(analytics, "st", fake_st)

    analytics.render_analytics(DB())

    assert len(charts) == 4
    assert all(getattr(chart, "data", None) for chart in charts)


def test_render_analytics_reports_database_read_failure(monkeypatch):
    import jarvis_analytics as analytics

    class Query:
        def select(self, *_args):
            return self

        def gte(self, *_args):
            return self

        def lte(self, *_args):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def limit(self, *_args):
            return self

        def execute(self):
            raise RuntimeError("mock analytics read failure")

    class DB:
        def table(self, _name):
            return Query()

    reports = []
    fake_st = _fake_streamlit()
    errors = []
    fake_st.error = lambda message: errors.append(message)
    monkeypatch.setattr(analytics, "st", fake_st)
    monkeypatch.setattr(
        analytics, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )

    analytics.render_analytics(DB())

    assert errors == ["Az analitikai naplók most nem tölthetők be."]
    assert reports[0][1]["module"] == "jarvis_analytics"
    assert reports[0][1]["operation"] == "load_analytics_logs"
