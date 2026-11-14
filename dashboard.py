"""JARVIS Intelligence Center — clean, responsive Streamlit dashboard."""
from __future__ import annotations

import hmac

import pandas as pd
import plotly.express as px
import streamlit as st

from jarvis_common import generate_text, get_secret, get_supabase

st.set_page_config(
    page_title="JARVIS | Intelligence Center",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# A restrained, high-contrast interface. No external font or image dependencies.
st.markdown(
    """
    <style>
    :root {
        --ink: #17243a;
        --muted: #68778d;
        --line: #e4eaf2;
        --surface: #ffffff;
        --canvas: #f4f7fb;
        --accent: #4263eb;
        --accent-soft: #edf1ff;
    }
    .stApp { background: var(--canvas); color: var(--ink); }
    [data-testid="stHeader"] { background: rgba(244,247,251,.92); }
    [data-testid="stSidebar"] {
        background: #111c2e;
        border-right: 1px solid #26354b;
    }
    [data-testid="stSidebar"] * { color: #e9eef7; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label { color: #d7e0ed; }
    .block-container { max-width: 1380px; padding-top: 2rem; padding-bottom: 3rem; }
    h1, h2, h3 { color: var(--ink); letter-spacing: -.035em; }
    h1 { font-size: clamp(1.8rem, 3vw, 2.5rem); font-weight: 750; }
    h2, h3 { font-weight: 700; }
    p, label, .stCaption { color: var(--muted); }
    .eyebrow {
        color: var(--accent); font-size: .72rem; font-weight: 750;
        letter-spacing: .13em; text-transform: uppercase; margin-bottom: .35rem;
    }
    .page-subtitle { color: var(--muted); margin-top: -.55rem; margin-bottom: 1.5rem; }
    .surface {
        background: var(--surface); border: 1px solid var(--line);
        border-radius: 16px; padding: 1.1rem 1.25rem;
        box-shadow: 0 3px 14px rgba(25,42,70,.035);
    }
    .metric-label { color: var(--muted); font-size: .82rem; font-weight: 600; }
    .metric-value { color: var(--ink); font-size: 2rem; font-weight: 750; line-height: 1.25; }
    .metric-note { color: #8a97a9; font-size: .75rem; margin-top: .2rem; }
    div[data-testid="stMetric"] {
        background: var(--surface); border: 1px solid var(--line);
        border-radius: 16px; padding: 1rem 1.1rem;
        box-shadow: 0 3px 14px rgba(25,42,70,.035);
    }
    div[data-testid="stMetric"] label { color: var(--muted); }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: var(--ink); font-weight: 750;
    }
    .stButton > button, .stDownloadButton > button {
        border-radius: 10px; font-weight: 650; min-height: 2.6rem;
    }
    .stButton > button[kind="primary"] {
        background: var(--accent); border-color: var(--accent);
    }
    div[data-testid="stChatMessage"] {
        border: 1px solid var(--line); border-radius: 14px;
        background: var(--surface); padding: .8rem 1rem; margin-bottom: .65rem;
    }
    div[data-testid="stAlert"] { border-radius: 12px; }
    [data-testid="stDataFrame"], [data-testid="stTable"] {
        border: 1px solid var(--line); border-radius: 12px; overflow: hidden;
    }
    hr { border-color: var(--line); }
    @media (max-width: 700px) {
        .block-container { padding: 1rem .8rem 2rem; }
        .surface { padding: .9rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def authenticated() -> bool:
    expected = get_secret("JARVIS_DASHBOARD_PASSWORD")
    if not expected:
        st.error("Hiányzó JARVIS_DASHBOARD_PASSWORD. Állítsd be a Codespace secrets fájljában.")
        return False
    if st.session_state.get("authenticated"):
        return True

    st.markdown('<div class="eyebrow">SECURE WORKSPACE</div>', unsafe_allow_html=True)
    st.title("Üdvözöl a JARVIS")
    st.caption("Jelentkezz be a biztonságos értékesítési irányítópulthoz.")
    with st.container(border=True):
        password = st.text_input("Dashboard jelszó", type="password")
        if st.button("Belépés", type="primary", use_container_width=True):
            if hmac.compare_digest(password, expected):
                st.session_state["authenticated"] = True
                st.rerun()
            st.error("Hibás jelszó.")
    return False


if not authenticated():
    st.stop()

st.sidebar.markdown("## ✦ JARVIS")
st.sidebar.caption("INTELLIGENCE CENTER")
page = st.sidebar.radio(
    "MUNKATERÜLET",
    ["Áttekintés", "Leadek", "Elemzések", "AI asszisztens", "Rendszer"],
    label_visibility="visible",
)
st.sidebar.divider()
st.sidebar.caption("B2B SALES OPERATIONS")
if st.sidebar.button("Kijelentkezés", use_container_width=True):
    st.session_state.clear()
    st.rerun()

try:
    db = get_supabase()
    leads = (
        db.table("leads")
        .select("*")
        .order("created_at", desc=True)
        .limit(2000)
        .execute()
        .data
        or []
    )
    logs = (
        db.table("logs")
        .select("*")
        .order("created_at", desc=True)
        .limit(100)
        .execute()
        .data
        or []
    )
    settings = db.table("settings").select("*").limit(100).execute().data or []
except Exception as exc:
    st.error("A Supabase-adatbázis jelenleg nem érhető el.")
    st.caption(f"Technikai részlet: {type(exc).__name__}. Ellenőrizd a Supabase URL és kulcs beállítását.")
    st.stop()

df = pd.DataFrame(leads)
if "status" not in df:
    df["status"] = pd.Series(dtype="str")
counts = df["status"].fillna("unknown").value_counts().to_dict() if not df.empty else {}
sent_count = counts.get("sent", 0) + counts.get("followed_up", 0)
reply_count = counts.get("replied", 0) + counts.get("opted_out", 0)

st.markdown('<div class="eyebrow">JARVIS / INTELLIGENCE CENTER</div>', unsafe_allow_html=True)
st.title(
    {
        "Áttekintés": "Üzleti áttekintés",
        "Leadek": "Leadkezelés",
        "Elemzések": "Teljesítmény és elemzések",
        "AI asszisztens": "JARVIS AI asszisztens",
        "Rendszer": "Rendszerállapot",
    }[page]
)
st.markdown('<div class="page-subtitle">B2B értékesítési műveletek · élő Supabase-adatok</div>', unsafe_allow_html=True)

if page == "Áttekintés":
    st.info("Az automatikus e-mail-küldés ki van kapcsolva. Élesítés előtt ellenőrizd a kapcsolatfelvétel jogalapját és a leiratkozási folyamatot.")
    metric_cols = st.columns(4)
    for col, label, value in zip(
        metric_cols,
        ["Összes lead", "Új lead", "Elküldött", "Válasz / tiltás"],
        [len(df), counts.get("new", 0), sent_count, reply_count],
    ):
        with col:
            st.metric(label, value)

    left, right = st.columns([1.25, 1])
    with left:
        st.subheader("Legutóbbi leadek")
        if not df.empty:
            visible = [c for c in ["company_name", "status", "website", "created_at"] if c in df]
            st.dataframe(df[visible].head(8), use_container_width=True, hide_index=True)
        else:
            st.caption("Még nincs megjeleníthető lead.")
    with right:
        st.subheader("Leadek státusz szerint")
        if counts:
            chart = pd.DataFrame([{"Státusz": k, "Darab": v} for k, v in counts.items()])
            fig = px.pie(chart, names="Státusz", values="Darab", hole=0.62)
            fig.update_layout(
                margin=dict(t=12, b=12, l=8, r=8),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend_title_text="",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("A diagramhoz még nincs adat.")

    st.subheader("Legutóbbi aktivitás")
    if logs:
        log_df = pd.DataFrame(logs).drop(columns=["id"], errors="ignore")
        st.dataframe(log_df.head(10), use_container_width=True, hide_index=True)
    else:
        st.caption("Még nincs naplóbejegyzés.")

elif page == "Leadek":
    st.subheader("Lead-adatbázis")
    st.caption(f"{len(df)} lead található az adatbázisban.")
    if not df.empty:
        visible = [
            c for c in [
                "company_name", "email", "website", "status", "reply_category",
                "created_at", "next_follow_up_at",
            ] if c in df
        ]
        search = st.text_input("Keresés cégnév vagy e-mail alapján", placeholder="Kezdj el gépelni…")
        view = df[visible].copy()
        if search:
            searchable = [c for c in ["company_name", "email", "website"] if c in view]
            mask = view[searchable].fillna("").astype(str).apply(
                lambda col: col.str.contains(search, case=False, regex=False)
            ).any(axis=1)
            view = view[mask]
        st.dataframe(view, use_container_width=True, hide_index=True)
        st.download_button(
            "Leadlista letöltése CSV-ben",
            view.to_csv(index=False).encode("utf-8-sig"),
            "jarvis_leads.csv",
            "text/csv",
        )
    else:
        st.info("Még nincs lead. Importálj előzetesen ellenőrzött CSV-fájlt.")

elif page == "Elemzések":
    st.subheader("Értékesítési teljesítmény")
    if counts:
        chart = pd.DataFrame([{"Státusz": k, "Darab": v} for k, v in counts.items()])
        fig = px.bar(chart, x="Státusz", y="Darab", color="Státusz")
        fig.update_layout(
            showlegend=False,
            margin=dict(t=20, b=20, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)
        if "created_at" in df:
            dates = pd.to_datetime(df["created_at"], errors="coerce").dt.date.value_counts().sort_index()
            if not dates.empty:
                st.subheader("Leadek időbeli alakulása")
                trend = px.line(
                    x=dates.index.astype(str),
                    y=dates.values,
                    markers=True,
                    labels={"x": "Dátum", "y": "Leadek"},
                )
                trend.update_layout(
                    margin=dict(t=20, b=20, l=10, r=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(trend, use_container_width=True)
    else:
        st.info("Még nincs elegendő adat az elemzéshez.")

elif page == "AI asszisztens":
    st.caption("A JARVIS összesített leadstátuszokat kap; személyes e-mail-címeket nem továbbítunk a modellnek.")
    if "chat" not in st.session_state:
        st.session_state.chat = []

    for role, message in st.session_state.chat:
        with st.chat_message(role):
            st.markdown(message)

    prompt = st.chat_input("Írd be az üzenetedet a JARVIS-nak…")
    if prompt:
        # Save the user turn once, then render the completed exchange on rerun.
        st.session_state.chat.append(("user", prompt))
        context = f"Lead státuszok: {counts}. Utolsó naplók száma: {len(logs)}."
        with st.spinner("A JARVIS gondolkodik…"):
            try:
                answer = generate_text(
                    "Te vagy JARVIS, magyar B2B üzleti asszisztens. "
                    "Válaszolj magyarul, világosan és tömören. "
                    "Fontos képességhatárok: ebben az alkalmazásban jelenleg csak a kapott összesített "
                    "leadstátuszokat és naplószámot látod. Csak elemzést, javaslatot és szövegtervezetet "
                    "adhatsz. Nem tudsz leadet létrehozni vagy módosítani, státuszt átírni, e-mailt küldeni, "
                    "emlékeztetőt vagy feladatot létrehozni, illetve aktivitást rögzíteni. Soha ne állítsd, "
                    "hogy ilyen műveletet elvégeztél. Ha ilyet kérnek, mondd el, hogy ez a funkció még nincs "
                    "bekötve, és ajánlj biztonságos következő lépést. Ne találj ki adatot vagy rendszerfunkciót.\n"
                    + context
                    + "\nBeszélgetési előzmény: "
                    + "\n".join(f"{r}: {m}" for r, m in st.session_state.chat[-8:])
                    + "\nKérdés: "
                    + prompt
                )
                if not answer:
                    answer = "A Gemini üres választ adott. Próbáld újra egy rövidebb kérdéssel."
            except Exception as exc:
                answer = (
                    "Most nem sikerült elérni a Gemini AI-szolgáltatást. "
                    "Ellenőrizd a GEMINI_API_KEY beállítást és a modell elérhetőségét, "
                    "majd próbáld újra."
                )
                st.session_state.chat.append(("assistant", answer))
                st.error(answer)
                st.caption(f"Technikai hibakód: {type(exc).__name__}. Titkos kulcsot ne másolj ide.")
                st.stop()
        st.session_state.chat.append(("assistant", answer))
        st.rerun()

    if st.session_state.chat and st.button("Beszélgetés törlése"):
        st.session_state.chat = []
        st.rerun()

else:
    st.subheader("Kapcsolatok és konfiguráció")
    status_cols = st.columns(3)
    status_cols[0].metric("Adatbázis", "Kapcsolódva")
    status_cols[1].metric("Leadek", len(df))
    status_cols[2].metric("Naplóbejegyzések", len(logs))
    st.subheader("Rendszerbeállítások")
    if settings:
        st.dataframe(pd.DataFrame(settings), use_container_width=True, hide_index=True)
    else:
        st.caption("Nincsenek mentett rendszerbeállítások.")
    st.caption("Az automatikus e-mail-küldés biztonsági okból kikapcsolva marad.")
