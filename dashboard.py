
import streamlit as st
from supabase import create_client, Client
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import google.generativeai as genai
import re
from datetime import datetime

# =========================================================
# 1. CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="JARVIS | Intelligence Center",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================
# 2. PREMIUM DESIGN SYSTEM
# =========================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@400;500;600;700&display=swap');

:root {
    --bg: #0B0E14;
    --surface: #111620;
    --surface2: #161D29;
    --border: rgba(255,255,255,0.075);
    --gold: #D6B477;
    --blue: #77B9FF;
    --text: #F1F3F7;
    --muted: #8993A5;
    --green: #51D6A0;
    --red: #F17C83;
}

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

.stApp {
    background: var(--bg);
    color: var(--text);
}

header[data-testid="stHeader"] {
    background: transparent;
}

.block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
    max-width: 1500px;
}

[data-testid="stSidebar"] {
    background: #0E131C;
    border-right: 1px solid var(--border);
}

[data-testid="stSidebar"] > div:first-child {
    padding-top: 2rem;
}

[data-testid="stSidebar"] * {
    color: var(--text);
}

h1, h2, h3 {
    font-family: 'Space Grotesk', sans-serif !important;
    letter-spacing: -0.7px;
}

h1 {
    font-size: 2.1rem !important;
    font-weight: 700 !important;
}

h2 {
    font-size: 1.35rem !important;
}

p, label {
    color: var(--muted);
}

hr {
    border-color: var(--border) !important;
}

.hero {
    background: linear-gradient(115deg, #171F2D 0%, #111722 60%, #1B1C25 100%);
    border: 1px solid rgba(214,180,119,0.22);
    border-radius: 18px;
    padding: 28px 30px;
    margin-bottom: 25px;
    position: relative;
    overflow: hidden;
}

.hero:after {
    content: "";
    position: absolute;
    width: 220px;
    height: 220px;
    border-radius: 50%;
    right: -65px;
    top: -110px;
    background: rgba(214,180,119,0.08);
    filter: blur(5px);
}

.hero-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 28px;
    font-weight: 700;
    color: #F7F3EB;
}

.hero-sub {
    color: #9BA8BB;
    font-size: 13px;
    margin-top: 8px;
}

.eyebrow {
    color: var(--gold);
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 2.5px;
    text-transform: uppercase;
    margin-bottom: 10px;
}

.metric-card {
    background: linear-gradient(145deg, #171E2A, #111721);
    border: 1px solid var(--border);
    border-radius: 15px;
    padding: 20px;
    min-height: 125px;
    transition: all .2s ease;
}

.metric-card:hover {
    border-color: rgba(214,180,119,0.4);
    transform: translateY(-2px);
}

.metric-label {
    font-size: 11px;
    color: #8D99AC;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
}

.metric-value {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 32px;
    font-weight: 700;
    color: #F3F5F9;
    margin-top: 12px;
}

.metric-caption {
    font-size: 11px;
    color: var(--gold);
    margin-top: 5px;
}

.section-label {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 17px;
    font-weight: 600;
    color: #E8ECF3;
    margin: 12px 0 16px 0;
}

.panel {
    background: #111721;
    border: 1px solid var(--border);
    border-radius: 15px;
    padding: 20px;
}

.status-online {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    background: rgba(81,214,160,.09);
    color: #51D6A0;
    border: 1px solid rgba(81,214,160,.2);
    border-radius: 30px;
    padding: 6px 12px;
    font-size: 11px;
    font-weight: 700;
}

.gold-text {
    color: var(--gold);
}

.stButton > button {
    background: linear-gradient(110deg, #D6B477, #B9945E);
    color: #141414 !important;
    border: none;
    border-radius: 9px;
    font-weight: 700;
    min-height: 42px;
    transition: all .2s ease;
}

.stButton > button:hover {
    background: #E6C995;
    border: none;
    box-shadow: 0 5px 20px rgba(214,180,119,.15);
}

.stTextInput input, .stTextArea textarea {
    background: #171E29 !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    color: white !important;
}

[data-testid="stChatMessage"] {
    background: #141B26;
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 15px;
    margin-bottom: 12px;
}

[data-testid="stChatInput"] {
    background: #111721;
    border: 1px solid rgba(214,180,119,.25);
    border-radius: 14px;
}

[data-testid="stDataFrame"] {
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 18px;
    border-bottom: 1px solid var(--border);
}

.stTabs [data-baseweb="tab"] {
    color: #8993A5;
    font-weight: 600;
}

.stTabs [aria-selected="true"] {
    color: var(--gold) !important;
}

.stSelectbox div[data-baseweb="select"] > div {
    background: #171E29;
    border-color: var(--border);
}

div[data-testid="stMetric"] {
    background: #111721;
    border: 1px solid var(--border);
    padding: 15px;
    border-radius: 12px;
}

div[data-testid="stMetricLabel"] {
    color: #8993A5;
}

div[data-testid="stMetricValue"] {
    color: #F1F3F7;
}

footer {
    visibility: hidden;
}

@media(max-width: 768px) {
    .block-container {
        padding: 1rem 1rem 2rem 1rem;
    }

    .hero {
        padding: 20px;
    }

    .hero-title {
        font-size: 23px;
    }

    .metric-card {
        padding: 14px;
    }

    .metric-value {
        font-size: 25px;
    }
}
</style>
""", unsafe_allow_html=True)


# =========================================================
# 3. CONNECTIONS
# =========================================================

@st.cache_resource
def get_connections():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]

    supabase = create_client(url, key)

    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

    model = genai.GenerativeModel("gemini-2.5-flash")

    return supabase, model


try:
    supabase, ai_model = get_connections()
    connection_ok = True
except Exception as e:
    st.error(f"Kapcsolódási hiba: {e}")
    st.stop()


# =========================================================
# 4. DATABASE
# =========================================================

@st.cache_data(ttl=30)
def load_data():
    try:
        leads_res = supabase.table("leads").select("*").execute()
        leads_df = pd.DataFrame(leads_res.data or [])
    except Exception:
        leads_df = pd.DataFrame()

    try:
        logs_res = (
            supabase.table("logs")
            .select("*")
            .order("created_at", desc=True)
            .limit(100)
            .execute()
        )
        logs_df = pd.DataFrame(logs_res.data or [])
    except Exception:
        logs_df = pd.DataFrame()

    try:
        settings_res = supabase.table("settings").select("*").execute()

        settings = {
            item["key"]: item["value"]
            for item in (settings_res.data or [])
        }
    except Exception:
        settings = {}

    return leads_df, logs_df, settings


leads_df, logs_df, settings = load_data()


# =========================================================
# 5. BUSINESS INTELLIGENCE
# =========================================================

total_leads = len(leads_df)

if not leads_df.empty and "status" in leads_df.columns:
    status_series = leads_df["status"].fillna("unknown")

    new_count = int((status_series == "new").sum())
    sent_count = int((status_series == "sent").sum())
    interested_count = int((status_series == "interested").sum())
    other_count = total_leads - new_count - sent_count - interested_count
else:
    new_count = sent_count = interested_count = other_count = 0

conversion_rate = (
    round(interested_count / sent_count * 100, 1)
    if sent_count > 0 else 0.0
)


# =========================================================
# 6. REUSABLE COMPONENTS
# =========================================================

def metric_card(label, value, caption, icon):
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{icon} &nbsp; {label}</div>
        <div class="metric-value">{value}</div>
        <div class="metric-caption">{caption}</div>
    </div>
    """, unsafe_allow_html=True)


def section_header(title, subtitle=None):
    st.markdown(f'<div class="section-label">{title}</div>',
                unsafe_allow_html=True)
    if subtitle:
        st.caption(subtitle)


def chart_layout(fig, height=320):
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(
            family="DM Sans",
            color="#AAB5C5",
            size=11
        ),
        margin=dict(l=10, r=10, t=35, b=10),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(color="#AAB5C5")
        ),
        hoverlabel=dict(
            bgcolor="#202A38",
            font_color="white"
        )
    )

    fig.update_xaxes(
        gridcolor="rgba(255,255,255,0.045)",
        zerolinecolor="rgba(255,255,255,0.05)"
    )

    fig.update_yaxes(
        gridcolor="rgba(255,255,255,0.045)",
        zerolinecolor="rgba(255,255,255,0.05)"
    )

    return fig


# =========================================================
# 7. SIDEBAR NAVIGATION
# =========================================================

with st.sidebar:

    st.markdown("""
    <div style="padding: 5px 0 25px 0;">
        <div style="font-size:11px;letter-spacing:3px;color:#D6B477;font-weight:800;">
            J.A.R.V.I.S
        </div>
        <div style="font-family:'Space Grotesk';font-size:24px;font-weight:700;color:#F1F3F7;">
            Intelligence
        </div>
        <div style="font-size:11px;color:#8993A5;">
            BUSINESS OPERATING SYSTEM
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("##### WORKSPACE")

    app_mode = st.radio(
        "Navigáció",
        [
            "💬  AI Command Center",
            "📊  Business Analytics",
            "🎯  Lead Intelligence",
            "📜  System Activity"
        ],
        label_visibility="collapsed"
    )

    st.divider()

    st.markdown("##### SYSTEM STATUS")

    st.markdown(
        '<div class="status-online">● SYSTEM ONLINE</div>',
        unsafe_allow_html=True
    )

    st.caption("Supabase & Gemini connected")

    st.divider()

    st.markdown("##### ACTIVE CAMPAIGN")

    niche = settings.get("target_niche", "Nincs beállítva")

    st.markdown(f"""
    <div class="panel">
        <div style="font-size:10px;color:#8993A5;letter-spacing:1px;">
            TARGET NICHE
        </div>
        <div style="font-size:15px;font-weight:700;color:#D6B477;margin-top:8px;">
            {niche}
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.write("")

    if st.button("↻  REFRESH DATABASE", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()

    st.caption("JARVIS PREMIUM • VERSION 5.0")
    st.caption(f"Updated: {datetime.now().strftime('%Y.%m.%d %H:%M')}")


# =========================================================
# 8. AI COMMAND CENTER
# =========================================================

if app_mode == "💬  AI Command Center":

    st.markdown("""
    <div class="hero">
        <div class="eyebrow">PERSONAL AI ASSISTANT</div>
        <div class="hero-title">Welcome to JARVIS.</div>
        <div class="hero-sub">
            Your intelligent business command center.
            Analyze, discover and execute your next growth opportunity.
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([3, 1])

    with col1:
        st.markdown("### AI Command Center")
        st.caption("Kommunikálj közvetlenül a Jarvis intelligenciarendszerével.")

    with col2:
        st.markdown(
            '<div class="status-online">● AI ENGINE ACTIVE</div>',
            unsafe_allow_html=True
        )

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "Üdvözöllek! Én vagyok Jarvis, a személyes "
                    "értékesítési intelligenciarendszered.\n\n"
                    "Ismerem a jelenlegi üzleti mutatókat, "
                    "és segítek a következő növekedési lehetőség megtalálásában."
                )
            }
        ]

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Adj utasítást Jarvisnak..."):

        st.session_state.messages.append({
            "role": "user",
            "content": prompt
        })

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):

            with st.spinner("Jarvis elemzi a kérést..."):

                try:
                    conversation = "\n".join([
                        f"{m['role']}: {m['content']}"
                        for m in st.session_state.messages[-12:]
                    ])

                    system_prompt = f"""
Te Jarvis vagy, egy professzionális autonóm B2B
értékesítési és üzleti intelligencia asszisztens.

Mindig magyarul válaszolj, professzionális, természetes stílusban.

ÜZLETI ADATOK:
Összes lead: {total_leads}
Új lead: {new_count}
Elküldött: {sent_count}
Érdeklődő: {interested_count}
Konverzió: {conversion_rate}%

Jelenlegi célcsoport:
{niche}

FELADATAID:
- Üzleti elemzések.
- Értékesítési stratégiák.
- Leadgenerálási ötletek.
- Kampányoptimalizálás.
- Statisztikák értelmezése.
- Célcsoportok meghatározása.

Ha a felhasználó új célcsoportot határoz meg,
a válaszod elejére helyezd ezt a pontos formátumot:

[UPDATE_NICHE: új célcsoport]

A célcsoportot csak akkor módosítsd, ha a felhasználó
egyértelműen új célcsoportot kér vagy határoz meg.

Ne állítsd, hogy adatbázis-módosítást, e-mail-küldést
vagy más külső műveletet végeztél el, ha az nem történt meg.

BESZÉLGETÉS:
{conversation}

Válaszolj a legutóbbi felhasználói üzenetre.
"""

                    response = ai_model.generate_content(system_prompt)
                    reply_text = response.text or "Nem sikerült választ generálni."

                    # Célcsoport frissítése
                    match = re.search(
                        r'\[UPDATE_NICHE:\s*(.*?)\]',
                        reply_text
                    )

                    if match:
                        new_niche = match.group(1).strip()

                        supabase.table("settings").upsert({
                            "key": "target_niche",
                            "value": new_niche
                        }).execute()

                        st.cache_data.clear()

                        reply_text = re.sub(
                            r'\[UPDATE_NICHE:.*?\]',
                            '',
                            reply_text
                        ).strip()

                        reply_text += (
                            f"\n\n✅ **Célcsoport sikeresen frissítve:** "
                            f"{new_niche}"
                        )

                    st.markdown(reply_text)

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": reply_text
                    })

                except Exception as e:
                    error = f"AI hiba: {str(e)}"
                    st.error(error)

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error
                    })


# =========================================================
# 9. BUSINESS ANALYTICS
# =========================================================

elif app_mode == "📊  Business Analytics":

    st.markdown("""
    <div class="hero">
        <div class="eyebrow">BUSINESS INTELLIGENCE</div>
        <div class="hero-title">Business Overview.</div>
        <div class="hero-sub">
            Valós idejű üzleti teljesítmény, értékesítési mutatók
            és adatvezérelt döntéstámogatás.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # KPI CARDS

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        metric_card("Total Leads", f"{total_leads:,}", "Teljes adatbázis", "◎")

    with c2:
        metric_card("New Leads", f"{new_count:,}", "Új lehetőségek", "◈")

    with c3:
        metric_card("Sent", f"{sent_count:,}", "Elért potenciális ügyfelek", "↗")

    with c4:
        metric_card("Interested", f"{interested_count:,}", "Pozitív válaszok", "✦")

    with c5:
        metric_card("Conversion", f"{conversion_rate}%", "Érdeklődők / elküldött", "◉")

    st.write("")
    st.divider()

    tab1, tab2, tab3 = st.tabs([
        "OVERVIEW",
        "PERFORMANCE",
        "DATA INSIGHTS"
    ])

    # -----------------------------------------------------
    # OVERVIEW
    # -----------------------------------------------------

    with tab1:

        left, right = st.columns([1.3, 1])

        with left:

            section_header("Lead Status Distribution")

            if not leads_df.empty and "status" in leads_df.columns:

                status_counts = (
                    leads_df["status"]
                    .fillna("unknown")
                    .value_counts()
                    .reset_index()
                )

                status_counts.columns = ["Status", "Count"]

                fig = px.pie(
                    status_counts,
                    names="Status",
                    values="Count",
                    hole=0.72,
                    color_discrete_sequence=[
                        "#D6B477",
                        "#77B9FF",
                        "#51D6A0",
                        "#8E91BA",
                        "#F17C83"
                    ]
                )

                fig.update_traces(
                    textposition="outside",
                    textinfo="percent",
                    marker=dict(
                        line=dict(color="#111721", width=3)
                    )
                )

                fig.add_annotation(
                    text=f"<b>{total_leads}</b><br><sup>LEADS</sup>",
                    showarrow=False,
                    font=dict(size=20, color="#F1F3F7")
                )

                fig = chart_layout(fig, 360)

                st.plotly_chart(fig, use_container_width=True)

            else:
                st.info("Nincs elérhető státuszadat.")

        with right:

            section_header("Lead Score Distribution")

            if not leads_df.empty and "score" in leads_df.columns:

                fig = px.histogram(
                    leads_df,
                    x="score",
                    nbins=12,
                    color_discrete_sequence=["#D6B477"]
                )

                fig.update_traces(
                    marker_line_width=0,
                    opacity=0.9
                )

                fig = chart_layout(fig, 360)

                st.plotly_chart(fig, use_container_width=True)

            else:
                st.info("Nincs elérhető pontszámadat.")

    # -----------------------------------------------------
    # PERFORMANCE
    # -----------------------------------------------------

    with tab2:

        section_header("Sales Performance", "Értékesítési teljesítmény és eredmények.")

        col1, col2 = st.columns(2)

        with col1:

            st.markdown('<div class="panel">', unsafe_allow_html=True)

            st.markdown("**Conversion Funnel**")

            funnel = pd.DataFrame({
                "Stage": ["Total Leads", "Sent", "Interested"],
                "Value": [total_leads, sent_count, interested_count]
            })

            fig = go.Figure(go.Funnel(
                y=funnel["Stage"],
                x=funnel["Value"],
                textinfo="value+percent initial",
                marker=dict(
                    color=["#D6B477", "#77B9FF", "#51D6A0"]
                )
            ))

            fig = chart_layout(fig, 340)

            st.plotly_chart(fig, use_container_width=True)

            st.markdown('</div>', unsafe_allow_html=True)

        with col2:

            st.markdown('<div class="panel">', unsafe_allow_html=True)

            st.markdown("**Performance Summary**")

            performance = pd.DataFrame({
                "Metric": [
                    "Total Leads",
                    "New Leads",
                    "Sent",
                    "Interested",
                    "Other"
                ],
                "Value": [
                    total_leads,
                    new_count,
                    sent_count,
                    interested_count,
                    other_count
                ]
            })

            fig = px.bar(
                performance,
                x="Value",
                y="Metric",
                orientation="h",
                color="Metric",
                color_discrete_sequence=[
                    "#D6B477",
                    "#77B9FF",
                    "#51D6A0",
                    "#8E91BA",
                    "#F17C83"
                ]
            )

            fig.update_layout(showlegend=False)

            fig = chart_layout(fig, 340)

            st.plotly_chart(fig, use_container_width=True)

            st.markdown('</div>', unsafe_allow_html=True)

    # -----------------------------------------------------
    # DATA INSIGHTS
    # -----------------------------------------------------

    with tab3:

        section_header("Database Intelligence")

        if not leads_df.empty:

            col1, col2 = st.columns(2)

            with col1:

                st.markdown("**Database Health**")

                missing = int(leads_df.isna().sum().sum())

                st.metric("Records", total_leads)
                st.metric("Missing Values", missing)

            with col2:

                st.markdown("**Lead Quality**")

                if "score" in leads_df.columns:

                    average_score = pd.to_numeric(
                        leads_df["score"],
                        errors="coerce"
                    ).mean()

                    st.metric(
                        "Average Score",
                        round(average_score, 2)
                        if pd.notna(average_score) else "N/A"
                    )

                    st.metric(
                        "Highest Score",
                        pd.to_numeric(
                            leads_df["score"],
                            errors="coerce"
                        ).max()
                    )

                else:
                    st.info("Nincs score mező az adatbázisban.")

        else:
            st.info("Az adatbázis jelenleg üres.")


# =========================================================
# 10. LEAD INTELLIGENCE
# =========================================================

elif app_mode == "🎯  Lead Intelligence":

    st.markdown("""
    <div class="hero">
        <div class="eyebrow">CUSTOMER INTELLIGENCE</div>
        <div class="hero-title">Lead Intelligence.</div>
        <div class="hero-sub">
            Potenciális ügyfelek, adatbázis és üzleti lehetőségek.
        </div>
    </div>
    """, unsafe_allow_html=True)

    if not leads_df.empty:

        col1, col2 = st.columns([2, 1])

        with col1:
            search = st.text_input(
                "⌕  Keresés az adatbázisban",
                placeholder="Név, e-mail, cégnév..."
            )

        with col2:

            if "status" in leads_df.columns:

                statuses = ["All"] + sorted(
                    leads_df["status"].dropna().unique().tolist()
                )

                selected_status = st.selectbox(
                    "Szűrés státusz alapján",
                    statuses
                )
            else:
                selected_status = "All"

        filtered_df = leads_df.copy()

        if search:
            mask = filtered_df.astype(str).apply(
                lambda column: column.str.contains(
                    search,
                    case=False,
                    na=False
                )
            ).any(axis=1)

            filtered_df = filtered_df[mask]

        if selected_status != "All" and "status" in filtered_df.columns:
            filtered_df = filtered_df[
                filtered_df["status"] == selected_status
            ]

        st.write("")

        c1, c2 = st.columns(2)

        c1.metric("Találatok", len(filtered_df))
        c2.metric("Összes rekord", total_leads)

        st.dataframe(
            filtered_df,
            use_container_width=True,
            hide_index=True
        )

        csv = filtered_df.to_csv(index=False).encode("utf-8-sig")

        st.download_button(
            "↓  Export CSV",
            data=csv,
            file_name="jarvis_leads.csv",
            mime="text/csv"
        )

    else:
        st.info("Még nincs adat a Lead adatbázisban.")


# =========================================================
# 11. SYSTEM ACTIVITY
# =========================================================

elif app_mode == "📜  System Activity":

    st.markdown("""
    <div class="hero">
        <div class="eyebrow">SYSTEM MONITORING</div>
        <div class="hero-title">Activity Center.</div>
        <div class="hero-sub">
            Rendszertevékenységek és legutóbbi események.
        </div>
    </div>
    """, unsafe_allow_html=True)

    if not logs_df.empty:

        st.metric("Legutóbbi események", len(logs_df))

        if "created_at" in logs_df.columns:

            logs_df["created_at"] = pd.to_datetime(
                logs_df["created_at"],
                errors="coerce"
            )

            st.markdown("##### Activity Timeline")

            st.dataframe(
                logs_df,
                use_container_width=True,
                hide_index=True
            )

        else:

            st.dataframe(
                logs_df,
                use_container_width=True,
                hide_index=True
            )

    else:
        st.info("Még nincsenek rendszernaplók.")


# =========================================================
# 12. FOOTER
# =========================================================

st.markdown("""
<div style="
    margin-top:50px;
    padding:20px 0;
    border-top:1px solid rgba(255,255,255,0.07);
    text-align:center;
">
    <div style="
        font-family:'Space Grotesk';
        color:#D6B477;
        font-size:12px;
        font-weight:700;
        letter-spacing:3px;
    ">
        J.A.R.V.I.S INTELLIGENCE
    </div>
    <div style="
        color:#667286;
        font-size:10px;
        margin-top:8px;
        letter-spacing:1px;
    ">
        BUSINESS AUTOMATION • DATA INTELLIGENCE • AI
    </div>
</div>
""", unsafe_allow_html=True)
