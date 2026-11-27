"""Truthful, server-side JARVIS activity analytics built from existing log events."""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from html import escape
import re
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from jarvis_errors import report_error


_ANALYTICS_TZ = ZoneInfo("Europe/Budapest")
# Verified Supabase project metadata for the Jarvis project (not the first log event).
_SUPABASE_PROJECT_CREATED_AT = datetime(2026, 11, 13, 16, 2, 24, 276230, tzinfo=timezone.utc)
_RANGE_DAYS = {"7 nap": 7, "30 nap": 30, "90 nap": 90, "1 év": 365}
_COLORS = {
    "blue": "#168BFF",
    "cyan": "#00CFFF",
    "purple": "#8B5CF6",
    "green": "#22D989",
    "orange": "#FFB547",
    "red": "#FF667A",
}


def _module_label(value: Any) -> str:
    module = str(value or "unknown").strip().casefold()
    if module == "chat":
        return "Chat"
    if module.startswith("lead_gen"):
        return "Leadkutatás"
    if module == "dynamic_scraper":
        return "Weboldal-feldolgozás"
    if module == "email_sender":
        return "E-mail modul"
    if module in {"task_actions", "tasks"}:
        return "Feladatkezelés"
    return module.replace("_", " ").strip().title() or "Ismeretlen modul"


def _activity_label(row: Any) -> str:
    module = str(row.get("module") or "").casefold()
    message = str(row.get("message") or "").casefold().split("|", 1)[0]
    level = str(row.get("level") or "info").casefold()
    if level in {"error", "critical", "fatal"}:
        return "Hibajelzés"
    if module == "chat":
        if message == "chat_request":
            return "Beszélgetési kérés"
        if message == "chat_response":
            return "AI-válasz elkészült"
        return "Chat aktivitás"
    if module.startswith("lead_gen"):
        return "Leadkutatási esemény"
    if module == "dynamic_scraper":
        return "Weboldal-feldolgozási esemény"
    if module == "email_sender":
        return "E-mail modul esemény"
    return f"{_module_label(module)} esemény"


def _sparkline_svg(values: list[int], color: str) -> str:
    """Create a tiny SVG trend from real daily counts; no external image or JS."""
    data = [int(value) for value in values[-14:]]
    if len(data) < 2:
        data = ([0] + data) if data else [0, 0]
    low, high = min(data), max(data)
    spread = max(high - low, 1)
    points = []
    for index, value in enumerate(data):
        x = 4 + index * (192 / max(len(data) - 1, 1))
        y = 31 - ((value - low) / spread) * 24
        points.append((x, y))
    path = " ".join(("M" if i == 0 else "L") + f" {x:.1f},{y:.1f}" for i, (x, y) in enumerate(points))
    return (
        '<svg viewBox="0 0 200 36" preserveAspectRatio="none" aria-hidden="true">'
        f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2.2" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg>'
    )

def _daily_series(data: pd.DataFrame, labels: list[str], mask: pd.Series | None = None) -> pd.Series:
    subset = data if mask is None else data.loc[mask]
    if subset.empty:
        return pd.Series(0, index=labels, dtype="int64")
    grouped = subset.groupby(subset["local_ts"].dt.strftime("%Y-%m-%d")).size()
    return grouped.reindex(labels, fill_value=0).astype("int64")


def is_analytics_question(question: str) -> bool:
    """Recognize Hungarian and English requests for usage/system analytics."""
    q = str(question or "").casefold()
    return any(term in q for term in (
        "analitika", "analitik", "elemz", "analíz", "analiz", "teljesít",
        "trend", "statiszt", "arány", "diagram", "grafikon", "használati adat",
        "rendszerhasználat", "aktivitási adat",
    ))


def build_chat_analytics_context(
    records: list[dict],
    now: datetime | None = None,
    project_created_at: datetime | None = None,
) -> str:
    """Summarize log events and distinguish project age from observed log coverage."""
    current_local = (now or datetime.now(_ANALYTICS_TZ)).astimezone(_ANALYTICS_TZ)
    created_at = (project_created_at or _SUPABASE_PROJECT_CREATED_AT).astimezone(_ANALYTICS_TZ)
    frame = pd.DataFrame(records or [])
    if frame.empty or "created_at" not in frame:
        return "A naplótábla jelenleg nem tartalmaz elemezhető eseményt. Adatforrás: public.logs."
    frame["created_at_utc"] = pd.to_datetime(frame["created_at"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["created_at_utc"]).copy()
    if frame.empty:
        return "A naplórekordokban nincs érvényes időbélyeg; elemzés nem készíthető."
    frame["module"] = frame.get("module", pd.Series("unknown", index=frame.index)).fillna("unknown").astype(str)
    frame["level"] = frame.get("level", pd.Series("info", index=frame.index)).fillna("info").astype(str).str.casefold()
    frame["message"] = frame.get("message", pd.Series("", index=frame.index)).fillna("").astype(str).str.casefold()
    lines = [
        "JARVIS ANALITIKA – VALÓS SUPABASE-NAPLÓADATOK",
        f"Supabase-projekt létrehozva: {created_at:%Y-%m-%d %H:%M:%S %Z}.",
        f"Ténylegesen megfigyelt naplózási időszak: {frame['created_at_utc'].min().tz_convert(_ANALYTICS_TZ):%Y-%m-%d %H:%M:%S %Z} – {frame['created_at_utc'].max().tz_convert(_ANALYTICS_TZ):%Y-%m-%d %H:%M:%S %Z}.",
        f"Adatforrás: public.logs; beolvasott és időbélyeggel rendelkező rekordok: {len(frame)}.",
        "A projekt létrehozási dátuma és az első naplóbejegyzés dátuma külön adat. A projekt létrehozása előtti kért időszakra nincs naplóadat; ez önmagában nem bizonyít adatvesztést vagy automatikus törlést.",
        "A naptári napok Europe/Budapest szerint értendők; minden időszak az előző azonos hosszúságú időszakkal összehasonlítható.",
        "A jelentést készítő chatkérés válaszeseménye csak a válasz elkészülte után kerül a naplóba, ezért azt a következő analitikai lekérdezés fogja tartalmazni.",
    ]
    for days in (7, 30, 90, 365):
        start_local = datetime.combine(current_local.date() - timedelta(days=days - 1), time.min, tzinfo=_ANALYTICS_TZ)
        previous_start_local = start_local - timedelta(days=days)
        start_utc = pd.Timestamp(start_local.astimezone(timezone.utc))
        previous_start_utc = pd.Timestamp(previous_start_local.astimezone(timezone.utc))
        now_utc = pd.Timestamp(current_local.astimezone(timezone.utc))
        current = frame[(frame["created_at_utc"] >= start_utc) & (frame["created_at_utc"] <= now_utc)]
        previous = frame[(frame["created_at_utc"] >= previous_start_utc) & (frame["created_at_utc"] < start_utc)]
        chat_messages = current.loc[current["module"].str.casefold() == "chat", "message"].str.split("|", n=1).str[0]
        chat_requests = int((chat_messages == "chat_request").sum())
        chat_responses = int((chat_messages == "chat_response").sum())
        errors = int(current["level"].isin(["error", "critical", "fatal"]).sum())
        warnings = int(current["level"].isin(["warn", "warning"]).sum())
        modules = current["module"].value_counts().to_dict()
        lines.append(
            f"{days} nap: esemény={len(current)}, előző időszak={len(previous)}, "
            f"chatkérés={chat_requests}, AI-válasz esemény={chat_responses}, hiba={errors}, figyelmeztetés={warnings}, "
            f"aktív modul={current['module'].nunique()}, modulmegoszlás={modules or 'nincs adat'}."
        )
    latest = frame.sort_values("created_at_utc", ascending=False).head(5)
    safe_latest = [
        f"{row['created_at_utc'].tz_convert(_ANALYTICS_TZ).strftime('%Y-%m-%d %H:%M')} – "
        f"{_activity_label(row)} ({_module_label(row['module'])})"
        for row in latest.to_dict("records")
    ]
    lines.append("Legutóbbi eseménytípusok (üzenettartalom nélkül): " + ("; ".join(safe_latest) if safe_latest else "nincs adat") + ".")
    lines.append(
        "Korlát: ezek naplózott események, nem elégedettség- vagy válaszminőség-mérések. "
        "A chatkérések és válaszesemények csak akkor jelennek meg, ha ténylegesen rögzültek."
    )
    return "\n".join(lines)



def is_executive_analytics_report_request(question: str) -> bool:
    """Identify explicit executive analytics reports that must use deterministic output."""
    q = str(question or "").casefold()
    report_action = any(term in q for term in (
        "készíts", "keszits", "állíts össze", "allits ossze", "kérek", "kerem",
        "generálj", "generalj", "készítsd el", "keszitsd el",
    ))
    report_topic = any(
        term in q for term in ("analitika", "analitik", "statiszt", "rendszerhasználat")
    )
    return report_action and report_topic


def build_executive_analytics_report(
    records: list[dict],
    now: datetime | None = None,
    project_created_at: datetime | None = None,
    truncated: bool = False,
) -> str:
    """Build a deterministic 30-day executive report from real log rows."""
    current_local = (now or datetime.now(_ANALYTICS_TZ)).astimezone(_ANALYTICS_TZ)
    created_at = (project_created_at or _SUPABASE_PROJECT_CREATED_AT).astimezone(_ANALYTICS_TZ)
    frame = pd.DataFrame(records or [])
    if not frame.empty and "created_at" in frame:
        frame["created_at_utc"] = pd.to_datetime(frame["created_at"], utc=True, errors="coerce")
        frame = frame.dropna(subset=["created_at_utc"]).copy()
    else:
        frame = pd.DataFrame(columns=["module", "level", "message", "created_at_utc"])

    if not frame.empty:
        for column, default in (("module", "unknown"), ("level", "info"), ("message", "")):
            if column not in frame:
                frame[column] = default
            frame[column] = frame[column].fillna(default).astype(str)
        frame["level"] = frame["level"].str.casefold()
        frame["message"] = frame["message"].str.casefold()

    end_local = current_local
    start_local = datetime.combine(current_local.date() - timedelta(days=29), time.min, tzinfo=_ANALYTICS_TZ)
    last7_start = datetime.combine(current_local.date() - timedelta(days=6), time.min, tzinfo=_ANALYTICS_TZ)
    previous7_start = last7_start - timedelta(days=7)
    start_utc = pd.Timestamp(start_local.astimezone(timezone.utc))
    end_utc = pd.Timestamp(end_local.astimezone(timezone.utc))
    last7_utc = pd.Timestamp(last7_start.astimezone(timezone.utc))
    previous7_utc = pd.Timestamp(previous7_start.astimezone(timezone.utc))

    recent30 = frame[(frame["created_at_utc"] >= start_utc) & (frame["created_at_utc"] <= end_utc)].copy()
    last7 = frame[(frame["created_at_utc"] >= last7_utc) & (frame["created_at_utc"] <= end_utc)].copy()
    previous7 = frame[(frame["created_at_utc"] >= previous7_utc) & (frame["created_at_utc"] < last7_utc)].copy()

    def count_level(data: pd.DataFrame, levels: set[str]) -> int:
        return int(data["level"].isin(levels).sum()) if not data.empty else 0

    def count_chat(data: pd.DataFrame, event: str) -> int:
        if data.empty:
            return 0
        messages = data.loc[data["module"].str.casefold() == "chat", "message"].str.split("|", n=1).str[0]
        return int((messages == event).sum())

    total = len(recent30)
    errors = count_level(recent30, {"error", "critical", "fatal"})
    warnings = count_level(recent30, {"warn", "warning"})
    module_counts = recent30["module"].value_counts().to_dict() if total else {}
    active_modules = len(module_counts)
    requests = count_chat(recent30, "chat_request")
    responses = count_chat(recent30, "chat_response")

    # Only UUID-linked events are eligible for outcome classification.
    # Legacy events without an ID remain visible as unlinked, never guessed.
    linked_requests: set[str] = set()
    linked_responses: set[str] = set()
    linked_errors: set[str] = set()
    legacy_requests = legacy_responses = 0
    if not recent30.empty:
        for row in recent30.loc[recent30["module"].str.casefold() == "chat", ["message"]].itertuples(index=False):
            match = re.fullmatch(r"(chat_request|chat_response|chat_error)(?:\|request_id=([0-9a-f]{32}))?", row.message)
            if not match:
                continue
            event, event_id = match.groups()
            if event_id is None:
                if event == "chat_request":
                    legacy_requests += 1
                elif event == "chat_response":
                    legacy_responses += 1
            elif event == "chat_request":
                linked_requests.add(event_id)
            elif event == "chat_response":
                linked_responses.add(event_id)
            elif event == "chat_error":
                linked_errors.add(event_id)
    successful_requests = len((linked_requests & linked_responses) - linked_errors)
    failed_requests = len(linked_requests & linked_errors)
    unfinished_requests = len(linked_requests - linked_responses - linked_errors)
    unlinked_requests = legacy_requests
    unlinked_responses = legacy_responses
    previous_total, last_total = len(previous7), len(last7)
    if previous_total:
        delta_text = f"{(last_total - previous_total) / previous_total * 100:+.1f}%"
    elif last_total:
        delta_text = "új aktivitás (az előző 7 napban 0 esemény)"
    else:
        delta_text = "mindkét időszakban 0 esemény"

    if frame.empty:
        observed_text = "Nem áll rendelkezésre érvényes időbélyegű naplórekord."
    else:
        first_seen = frame["created_at_utc"].min().tz_convert(_ANALYTICS_TZ)
        last_seen = frame["created_at_utc"].max().tz_convert(_ANALYTICS_TZ)
        observed_text = f"{first_seen:%Y-%m-%d %H:%M:%S %Z} – {last_seen:%Y-%m-%d %H:%M:%S %Z}"

    lines = [
        "# 30 napos vezetői analitikai jelentés",
        "",
        f"**Jelentés készítésének időpontja:** {current_local:%Y-%m-%d %H:%M:%S %Z} (Europe/Budapest)",
        f"**Vizsgált 30 napos időablak:** {start_local:%Y-%m-%d %H:%M %Z} – {end_local:%Y-%m-%d %H:%M %Z}",
        "",
        "## Vezetői összefoglaló",
        f"A vizsgált időablakban **{total}** naplózott esemény szerepel **{active_modules}** aktív modultól. "
        f"A naplóban {errors} hibaszintű és {warnings} figyelmeztetési szintű esemény található. "
        "Ez kizárólag a naplózott eseményekre vonatkozik, nem bizonyítja önmagában a teljes rendszer hibamentességét.",
        "",
        "## Projekt- és naplózási időszak – külön kezelve",
        f"- **Supabase-projekt létrehozása:** {created_at:%Y-%m-%d %H:%M:%S %Z} (Europe/Budapest; ellenőrzött projektmetaadat).",
        f"- **A beolvasott naplók tényleges megfigyelt időszaka:** {observed_text}.",
        "- A projekt létrehozási időpontja nem azonos az első naplóbejegyzés időpontjával.",
        "- A megfigyelt időszak a lekérdezésben elérhető, érvényes időbélyegű rekordok minimuma és maximuma; nem bizonyít folyamatos aktivitást a teljes időszakban.",
        "",
        "## 1. Tények – adatbázis",
        f"- Összes naplózott esemény a 30 napos ablakban: **{total}**.",
        f"- Hibaszintű esemény (error/critical/fatal): **{errors}** ({errors / total * 100:.1f}% a naplózott eseményekből)." if total else "- Hibaszintű esemény: 0 (nincs esemény, ezért hibaarány nem számítható).",
        f"- Figyelmeztetés (warn/warning): **{warnings}** ({warnings / total * 100:.1f}% a naplózott eseményekből)." if total else "- Figyelmeztetés: 0 (nincs esemény, ezért arány nem számítható).",
        f"- Chatkérések: **{requests}**; AI-válasz események: **{responses}**.",
        f"- Azonosítóval összerendelt kérések: sikeres **{successful_requests}**, sikertelen **{failed_requests}**, befejezetlen **{unfinished_requests}**.",
        f"- Régi, request_id nélküli események: kérés **{unlinked_requests}**, válasz **{unlinked_responses}** (ezek nem rendelhetők össze megbízhatóan).",
        f"- Aktív modulok száma: **{active_modules}**.",
        "",
        "**Modulonkénti eseményszám (30 nap):**",
    ]
    if module_counts:
        lines.extend(
            f"- {module}: {count} ({count / total * 100:.1f}%)"
            for module, count in sorted(module_counts.items(), key=lambda item: (-item[1], item[0]))
        )
    else:
        lines.append("- Nincs naplózott modulaktivitás ebben az időablakban.")

    lines.extend([
        "",
        "## 2. Rövid távú trend – utolsó 7 nap vs. előző 7 nap",
        f"- Utolsó 7 nap: **{last_total}** esemény.",
        f"- Előző 7 nap: **{previous_total}** esemény.",
        f"- Változás: **{delta_text}**.",
    ])
    if last7.empty:
        lines.append("- Az utolsó 7 napban egyetlen modulhoz sem érkezett naplózott esemény.")
    else:
        last7_modules = last7["module"].value_counts().to_dict()
        lines.append("- Utolsó 7 nap modulmegoszlása: " + ", ".join(
            f"{name}: {count}" for name, count in sorted(last7_modules.items(), key=lambda item: (-item[1], item[0]))
        ))

    lines.extend([
        "",
        "## 3. Következtetések és bizonytalanságok",
        "- A 0 naplózott hibaszintű esemény nem azonos a 0 tényleges hibával: csak a rögzített level mezőket tükrözi.",
        "- Ha egy modulhoz az utolsó 7 napban nem tartozik esemény, az csak naplózási inaktivitást jelez; önmagában nem bizonyítja a modul leállását vagy ütemezési problémáját.",
        "- Az eseményszám nem méri a válaszok minőségét, a felhasználói elégedettséget, az üzleti konverziót vagy a sikeres kézbesítést.",
        "- A sikeres/sikertelen/befejezetlen bontás kizárólag azonosítóval összekapcsolt, a vizsgált időablakban naplózott kérésekre vonatkozik; a régi azonosító nélküli események külön szerepelnek.",
        "- A 7 napos összehasonlítás Europe/Budapest naptári napjai szerint készült; a százalékos változás nevezője az előző 7 nap eseményszáma.",
    ])
    if truncated:
        lines.append("- **Adatlefedettségi korlát:** a lekérdezés elérte az 5000 rekordos korlátot, ezért az összesítés és a megfigyelt időszak nem feltétlenül teljes.")
    lines.extend([
        "",
        "## 4. Rangsorolt javaslatok",
        "1. **Automatizált modulok ütemezésének ellenőrzése:** csak akkor vizsgáld az email_sender, lead_gen vagy dynamic_scraper futását, ha ezeknek az adott héten működniük kellett volna. A naplóhiány önmagában nem bizonyít leállást.",
        "2. **A naplózás teljességének ellenőrzése:** vesd össze a várt futások számát a rögzített eseményekkel, és külön naplózd a megkezdett, sikeres és sikertelen futásokat.",
        "3. **A teljesítménymérés bővítése:** üzleti döntéshez külön mérd a feladat sikerességét, feldolgozási időt és üzleti eredményt; a puszta eseményszám ezek helyettesítésére nem alkalmas.",
        "",
        "## Adatforrás és módszertan",
        "Forrás: Supabase public.logs; module, level, message és created_at mezők. A kérés- és válaszesemények request_id alapján kapcsolódnak; nyers naplóüzenet nem kerül a jelentésbe. A projekt létrehozási időpontja külön, ellenőrzött projektmetaadat.",
    ])
    return "\n".join(lines)


def _change_label(current: int, previous: int) -> str:
    if previous == 0:
        return "Új aktivitás" if current > 0 else "Nincs aktivitás"
    change = ((current - previous) / previous) * 100
    sign = "+" if change > 0 else ""
    return f"{sign}{change:.0f}% az előző időszakhoz képest"


def _metric_card(title: str, value: str, detail: str, icon: str, color: str, spark: list[int]) -> str:
    return (
        f'<div class="jarvis-kpi" style="--kpi-accent:{color}">'
        f'<div class="jarvis-kpi-top"><span class="jarvis-kpi-icon">{icon}</span>'
        f'<span class="jarvis-kpi-value">{escape(value)}</span></div>'
        f'<div class="jarvis-kpi-label">{escape(title)}</div>'
        f'<div class="jarvis-kpi-detail">{escape(detail)}</div>'
        f'<div class="jarvis-kpi-spark">{_sparkline_svg(spark, color)}</div>'
        '</div>'
    )


def _empty_chart(message: str) -> None:
    st.markdown(f'<div class="jarvis-empty">{escape(message)}</div>', unsafe_allow_html=True)


def _chart_layout(fig: go.Figure, height: int = 300) -> go.Figure:
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, Arial, sans-serif", "color": "#DCE8FA", "size": 12},
        margin={"l": 8, "r": 8, "t": 12, "b": 8},
        height=height,
        showlegend=False,
        hoverlabel={"bgcolor": "#101E35", "bordercolor": "#2474BB", "font": {"color": "#F4F7FF"}},
    )
    return fig


def render_analytics(db: Any) -> None:
    """Render a truthful analytics page from the private public.logs table."""
    st.markdown(
        """
        <style>
        .jarvis-analytics-head {display:flex;align-items:center;justify-content:space-between;gap:20px;padding:4px 0 18px;border-bottom:1px solid #1B3553;margin-bottom:22px;}
        .jarvis-analytics-title {display:flex;align-items:center;gap:15px;}
        .jarvis-analytics-title .glyph {font-size:2.35rem;color:#20BFFF;text-shadow:0 0 16px rgba(22,139,255,.55);}
        .jarvis-analytics-title h1 {font-size:1.9rem;line-height:1.1;margin:0;color:#F4F7FF;font-weight:760;}
        .jarvis-analytics-title p {font-size:.9rem;color:#9AAAC5;margin:6px 0 0;}
        .jarvis-analytics-status {display:flex;align-items:center;gap:14px;color:#DCE8FA;font-size:.9rem;white-space:nowrap;}
        .jarvis-analytics-status .live-dot {width:10px;height:10px;border-radius:50%;background:#22D989;box-shadow:0 0 10px rgba(34,217,137,.7);display:inline-block;margin-right:7px;}
        .jarvis-analytics-status .separator {height:22px;width:1px;background:#263A56;}
        .jarvis-analytics-status .profile {width:40px;height:40px;border-radius:50%;display:grid;place-items:center;background:linear-gradient(145deg,#176EC4,#0B2E5A);border:1px solid #2879D0;color:white;font-weight:700;}
        .jarvis-kpi {height:142px;position:relative;overflow:hidden;padding:17px 18px 12px;border-radius:18px;border:1px solid color-mix(in srgb,var(--kpi-accent) 45%,#203957);background:linear-gradient(145deg,rgba(17,30,53,.98),rgba(5,15,31,.98));box-shadow:0 8px 22px rgba(0,0,0,.16);}
        .jarvis-kpi:after {content:"";position:absolute;right:-25px;top:-35px;width:105px;height:105px;border-radius:50%;background:var(--kpi-accent);opacity:.06;filter:blur(20px);}
        .jarvis-kpi-top {display:flex;align-items:center;gap:13px;position:relative;z-index:1;}
        .jarvis-kpi-icon {font-size:1.8rem;color:var(--kpi-accent);text-shadow:0 0 14px color-mix(in srgb,var(--kpi-accent) 55%,transparent);}
        .jarvis-kpi-value {font-size:2rem;line-height:1;font-weight:780;color:#F4F7FF;letter-spacing:-.04em;}
        .jarvis-kpi-label {margin-top:9px;color:#DCE8FA;font-size:.9rem;font-weight:650;}
        .jarvis-kpi-detail {margin-top:4px;color:#9AAAC5;font-size:.72rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
        .jarvis-kpi-spark {position:absolute;left:14px;right:14px;bottom:6px;height:30px;opacity:.9;}
        .jarvis-kpi-spark svg {width:100%;height:100%;}
        .jarvis-panel-title {font-size:1.05rem;font-weight:720;color:#F4F7FF;margin:0 0 3px;}
        .jarvis-panel-subtitle {font-size:.76rem;color:#8FA4C2;margin:0 0 10px;}
        .jarvis-empty {min-height:135px;display:flex;align-items:center;justify-content:center;text-align:center;padding:16px;color:#9AAAC5;font-size:.9rem;border:1px dashed #284362;border-radius:12px;background:rgba(8,22,43,.45);}
        .jarvis-recent {display:flex;align-items:center;gap:11px;padding:10px 0;border-bottom:1px solid rgba(43,66,96,.5);}
        .jarvis-recent:last-child {border-bottom:0;}
        .jarvis-recent-dot {width:9px;height:9px;min-width:9px;border-radius:50%;background:#168BFF;box-shadow:0 0 9px rgba(22,139,255,.6);}
        .jarvis-recent-dot.error {background:#FF667A;box-shadow:0 0 9px rgba(255,102,122,.5);}
        .jarvis-recent-time {width:76px;min-width:76px;color:#9AAAC5;font-size:.76rem;font-variant-numeric:tabular-nums;}
        .jarvis-recent-label {color:#E7EFFC;font-size:.82rem;line-height:1.35;}
        .jarvis-data-note {padding:12px 15px;border:1px solid #244365;border-radius:12px;background:rgba(9,26,48,.7);color:#AFC1DC;font-size:.8rem;line-height:1.6;margin-top:14px;}
        div[data-testid="stVerticalBlockBorderWrapper"] {border-color:#203957 !important;border-radius:17px !important;background:linear-gradient(145deg,rgba(11,23,43,.78),rgba(6,15,30,.9)) !important;}
        div[data-testid="stRadio"] > label {display:none;}
        div[data-testid="stRadio"] div[role="radiogroup"] {gap:6px;flex-wrap:wrap;}
        div[data-testid="stRadio"] div[role="radiogroup"] label {background:#0C1B31;border:1px solid #243D5B;border-radius:9px;padding:5px 12px;color:#B9C9E2;}
        div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) {background:#1266C2;border-color:#168BFF;color:#fff;box-shadow:0 0 12px rgba(22,139,255,.22);}
        @media(max-width:900px) {
            .jarvis-kpi {height:132px;padding:14px;}
            .jarvis-kpi-value {font-size:1.7rem;}
        }
        @media(max-width:650px) {
            .jarvis-analytics-head {align-items:flex-start;flex-direction:column;}
            .jarvis-analytics-status {align-self:flex-end;}
            .jarvis-analytics-title h1 {font-size:1.55rem;}
            .jarvis-kpi {height:128px;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    now_local = datetime.now(_ANALYTICS_TZ)
    header_time = now_local.strftime("%H:%M")
    st.markdown(
        '<div class="jarvis-analytics-head">'
        '<div class="jarvis-analytics-title"><span class="glyph">▥</span><div>'
        '<h1>Analitika</h1><p>Részletes betekintés a JARVIS használatába</p></div></div>'
        '<div class="jarvis-analytics-status"><span><i class="live-dot"></i>Aktív</span>'
        f'<span class="separator"></span><span>◷ &nbsp; {header_time}</span>'
        '<span class="profile">T</span></div></div>',
        unsafe_allow_html=True,
    )

    selected_range = st.session_state.get("jarvis_analytics_range", "30 nap")
    if selected_range not in _RANGE_DAYS:
        selected_range = "30 nap"
    period_days = _RANGE_DAYS[selected_range]
    start_date = now_local.date() - timedelta(days=period_days - 1)
    current_start_local = datetime.combine(start_date, time.min, tzinfo=_ANALYTICS_TZ)
    previous_start_local = current_start_local - timedelta(days=period_days)
    current_start_utc = current_start_local.astimezone(timezone.utc)
    previous_start_utc = previous_start_local.astimezone(timezone.utc)
    now_utc = now_local.astimezone(timezone.utc)

    try:
        result = (
            db.table("logs")
            .select("module,level,message,created_at")
            .gte("created_at", previous_start_utc.isoformat())
            .lte("created_at", now_utc.isoformat())
            .order("created_at", desc=True)
            .limit(5000)
            .execute()
        )
        records = result.data or []
    except Exception as exc:
        report_error(
            exc,
            module="jarvis_analytics",
            operation="load_analytics_logs",
            severity="error",
            db=db,
        )
        st.error("Az analitikai naplók most nem tölthetők be.")
        st.caption(f"Hibatípus: {type(exc).__name__}. A meglévő adatokhoz nem történt módosítás.")
        return

    frame = pd.DataFrame(records, columns=["module", "level", "message", "created_at"])
    if not frame.empty:
        frame["created_at_utc"] = pd.to_datetime(frame["created_at"], utc=True, errors="coerce")
        frame = frame.dropna(subset=["created_at_utc"]).copy()
        frame["local_ts"] = frame["created_at_utc"].dt.tz_convert(_ANALYTICS_TZ)
        frame["module"] = frame["module"].fillna("unknown").astype(str)
        frame["level"] = frame["level"].fillna("info").astype(str).str.casefold()
        frame["message"] = frame["message"].fillna("").astype(str)
        frame["module_label"] = frame["module"].map(_module_label)

    if frame.empty:
        current = frame.copy()
        previous = frame.copy()
    else:
        current = frame[frame["created_at_utc"] >= pd.Timestamp(current_start_utc)].copy()
        previous = frame[
            (frame["created_at_utc"] >= pd.Timestamp(previous_start_utc))
            & (frame["created_at_utc"] < pd.Timestamp(current_start_utc))
        ].copy()

    def count_errors(data: pd.DataFrame) -> int:
        return int(data["level"].isin(["error", "critical", "fatal"]).sum()) if not data.empty else 0

    def count_chat_requests(data: pd.DataFrame) -> int:
        return int(((data["module"].str.casefold() == "chat") & (data["message"].str.split("|", n=1).str[0] == "chat_request")).sum()) if not data.empty else 0

    current_events = int(len(current))
    previous_events = int(len(previous))
    current_chat = count_chat_requests(current)
    previous_chat = count_chat_requests(previous)
    current_errors = count_errors(current)
    previous_errors = count_errors(previous)
    def count_warnings(data: pd.DataFrame) -> int:
        return int(data["level"].isin(["warn", "warning"]).sum()) if not data.empty else 0
    current_warnings = count_warnings(current)
    previous_warnings = count_warnings(previous)
    current_modules = int(current["module"].nunique()) if not current.empty else 0
    previous_modules = int(previous["module"].nunique()) if not previous.empty else 0

    daily_index = pd.date_range(start=start_date, end=now_local.date(), freq="D")
    daily_labels = [day.strftime("%Y-%m-%d") for day in daily_index]
    daily_counts = _daily_series(current, daily_labels)

    if current.empty:
        daily_active_modules = [0] * len(daily_labels)
    else:
        daily_active_modules = (
            current.assign(local_day=current["local_ts"].dt.strftime("%Y-%m-%d"))
            .groupby("local_day")["module"].nunique()
            .reindex(daily_labels, fill_value=0)
            .tolist()
        )

    metrics = [
        ("Naplózott események", f"{current_events:,}".replace(",", " "), _change_label(current_events, previous_events), "◉", _COLORS["blue"], daily_counts.tolist()),
        ("Chatkérések", f"{current_chat:,}".replace(",", " "), _change_label(current_chat, previous_chat), "◌", _COLORS["purple"], (
            _daily_series(current, daily_labels, current["message"].str.split("|", n=1).str[0] == "chat_request").tolist()
            if not current.empty else [0] * len(daily_labels)
        )),
        ("Hibajelzések", f"{current_errors:,}".replace(",", " "), _change_label(current_errors, previous_errors), "⚡", _COLORS["cyan"], (
            _daily_series(current, daily_labels, current["level"].isin(["error", "critical", "fatal"])).tolist()
            if not current.empty else [0] * len(daily_labels)
        )),
        ("Figyelmeztetések", f"{current_warnings:,}".replace(",", " "), _change_label(current_warnings, previous_warnings), "!", _COLORS["orange"], (
            _daily_series(current, daily_labels, current["level"].isin(["warn", "warning"])).tolist()
            if not current.empty else [0] * len(daily_labels)
        )),
        ("Aktív modulok", f"{current_modules:,}".replace(",", " "), _change_label(current_modules, previous_modules), "✦", _COLORS["orange"], daily_active_modules),
    ]

    metric_columns = st.columns(5)
    for column, metric in zip(metric_columns, metrics):
        title, value, detail, icon, color, spark = metric
        with column:
            st.markdown(_metric_card(title, value, detail, icon, color, spark), unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    left, right = st.columns([1.9, 1.05], gap="medium")

    with left:
        with st.container(border=True):
            trend_title, trend_period = st.columns([1.25, 1.7], gap="small")
            with trend_title:
                st.markdown('<div class="jarvis-panel-title">↗ &nbsp; Naplózott aktivitási trend</div>'
                            '<div class="jarvis-panel-subtitle">Napi eseményszám</div>',
                            unsafe_allow_html=True)
            with trend_period:
                st.radio(
                    "Időszak",
                    options=list(_RANGE_DAYS.keys()),
                    index=list(_RANGE_DAYS.keys()).index(selected_range),
                    horizontal=True,
                    key="jarvis_analytics_range",
                    label_visibility="collapsed",
                )
            if current.empty:
                _empty_chart("Ebben az időszakban még nincs naplózott aktivitás.")
            else:
                trend = go.Figure()
                trend.add_trace(go.Scatter(
                    x=[item.strftime("%Y-%m-%d") for item in daily_index],
                    y=daily_counts.tolist(),
                    mode="lines+markers",
                    line={"color": _COLORS["cyan"], "width": 3, "shape": "spline"},
                    marker={"size": 7, "color": _COLORS["cyan"], "line": {"color": "#D9F8FF", "width": 1}},
                    fill="tozeroy",
                    fillcolor="rgba(0,207,255,.12)",
                    hovertemplate="%{x}<br>%{y} esemény<extra></extra>",
                ))
                trend.update_xaxes(showgrid=False, zeroline=False, tickfont={"color": "#AFC1DC"})
                trend.update_yaxes(showgrid=True, gridcolor="rgba(76,111,151,.18)", zeroline=False,
                                   rangemode="tozero", title=None, tickfont={"color": "#AFC1DC"})
                st.plotly_chart(_chart_layout(trend, 320), width="stretch", config={"displayModeBar": False, "responsive": True})

    with right:
        with st.container(border=True):
            st.markdown('<div class="jarvis-panel-title">◉ &nbsp; Modulaktivitás</div>'
                        '<div class="jarvis-panel-subtitle">A háttérmodulok naplózott eseményeinek megoszlása</div>',
                        unsafe_allow_html=True)
            if current.empty:
                _empty_chart("Nincs megjeleníthető modulaktivitás.")
            else:
                module_counts = current["module_label"].value_counts()
                donut = go.Figure(go.Pie(
                    labels=module_counts.index.tolist(),
                    values=module_counts.values.tolist(),
                    hole=.68,
                    sort=False,
                    marker={"colors": [_COLORS["blue"], _COLORS["purple"], _COLORS["green"], _COLORS["orange"], _COLORS["cyan"]]},
                    textinfo="none",
                    hovertemplate="%{label}<br>%{value} esemény (%{percent})<extra></extra>",
                ))
                donut.update_layout(annotations=[{
                    "text": f"<b>{current_events}</b><br><span style='font-size:10px'>esemény</span>",
                    "showarrow": False, "font": {"color": "#F4F7FF", "size": 20},
                }])
                st.plotly_chart(_chart_layout(donut, 320), width="stretch", config={"displayModeBar": False, "responsive": True})

    bottom_left, bottom_middle, bottom_right = st.columns([1, 1.12, 1.08], gap="medium")

    with bottom_left:
        with st.container(border=True):
            st.markdown('<div class="jarvis-panel-title">◷ &nbsp; Aktivitási időszakok</div>'
                        '<div class="jarvis-panel-subtitle">Az események eloszlása helyi idő szerint</div>',
                        unsafe_allow_html=True)
            if current.empty:
                _empty_chart("Nincs elegendő időbélyeg az aktivitás elemzéséhez.")
            else:
                hours = current["local_ts"].dt.hour
                bins = [0, 6, 12, 18, 24]
                labels = ["00–06", "06–12", "12–18", "18–24"]
                buckets = pd.cut(hours, bins=bins, labels=labels, right=False, include_lowest=True)
                hour_counts = buckets.value_counts(sort=False).reindex(labels, fill_value=0)
                total = int(hour_counts.sum())
                percentages = [(int(value) / total * 100) if total else 0 for value in hour_counts.values]
                activity = go.Figure(go.Bar(
                    x=labels, y=hour_counts.values,
                    marker={"color": [_COLORS["blue"], "#2187E8", "#3B9AD8", "#1761B8"],
                            "line": {"color": "#4BB9FF", "width": 1}},
                    text=[f"{value:.0f}%" for value in percentages],
                    textposition="outside",
                    hovertemplate="%{x}<br>%{y} esemény<extra></extra>",
                ))
                activity.update_xaxes(showgrid=False, tickfont={"color": "#AFC1DC"})
                activity.update_yaxes(showgrid=False, visible=False, rangemode="tozero")
                st.plotly_chart(_chart_layout(activity, 235), width="stretch", config={"displayModeBar": False, "responsive": True})

    with bottom_middle:
        with st.container(border=True):
            st.markdown('<div class="jarvis-panel-title">✦ &nbsp; Főbb modulok</div>'
                        '<div class="jarvis-panel-subtitle">Modulonkénti eseményszám a kiválasztott időszakban</div>',
                        unsafe_allow_html=True)
            if current.empty:
                _empty_chart("Még nincs elegendő adat a modulok összehasonlításához.")
            else:
                module_counts = current["module_label"].value_counts().sort_values(ascending=True)
                module_total = max(int(module_counts.sum()), 1)
                bar = go.Figure(go.Bar(
                    x=module_counts.values,
                    y=module_counts.index.tolist(),
                    orientation="h",
                    marker={"color": [_COLORS["blue"], _COLORS["purple"], _COLORS["green"], _COLORS["orange"], _COLORS["cyan"]]},
                    text=[f"{(value / module_total) * 100:.0f}%" for value in module_counts.values],
                    textposition="outside",
                    hovertemplate="%{y}<br>%{x} esemény<extra></extra>",
                ))
                bar.update_xaxes(visible=False, range=[0, max(int(module_counts.max()) * 1.25, 1)])
                bar.update_yaxes(showgrid=False, tickfont={"color": "#DCE8FA"})
                st.plotly_chart(_chart_layout(bar, 235), width="stretch", config={"displayModeBar": False, "responsive": True})

    with bottom_right:
        with st.container(border=True):
            st.markdown('<div class="jarvis-panel-title">◷ &nbsp; Legutóbbi aktivitás</div>'
                        '<div class="jarvis-panel-subtitle">Legfrissebb naplózott események</div>',
                        unsafe_allow_html=True)
            if current.empty:
                _empty_chart("Még nincs megjeleníthető esemény.")
            else:
                recent_rows = current.sort_values("created_at_utc", ascending=False).head(8).to_dict("records")
                recent_html = []
                for row in recent_rows:
                    event_time = row["local_ts"]
                    local_time = (
                        event_time.strftime("%H:%M")
                        if event_time.date() == now_local.date()
                        else event_time.strftime("%d.%m %H:%M")
                    )
                    is_error = str(row.get("level") or "").casefold() in {"error", "critical", "fatal", "warn", "warning"}
                    dot_class = "jarvis-recent-dot error" if is_error else "jarvis-recent-dot"
                    description = escape(_activity_label(row))
                    recent_html.append(
                        f'<div class="jarvis-recent"><span class="{dot_class}"></span>'
                        f'<span class="jarvis-recent-time">{local_time}</span>'
                        f'<span class="jarvis-recent-label">{description}</span></div>'
                    )
                st.markdown("".join(recent_html), unsafe_allow_html=True)

    if len(records) >= 5000:
        st.warning("Az elérhető naplóbejegyzések elérték az 5000-es lekérdezési korlátot; az összesítés nem biztos, hogy teljes.")
    st.markdown(
        '<div class="jarvis-data-note"><strong>Adatminőség és adatvédelem:</strong> '
        'A grafikonok a Supabase <code>public.logs</code> táblájának tényleges eseményeiből készülnek. '
        'A chatkérések és a sikeres AI-válaszok csak eseménytípusként kerülnek naplózásra; '
        'a felhasználói üzenetek és az AI-válaszok tartalma nem. A válaszpontosságot, az elégedettséget '
        'és a munkamenet időtartamát a rendszer jelenleg nem méri, ezért ezekhez nem jelenítünk meg kitalált értékeket.</div>',
        unsafe_allow_html=True,
    )
