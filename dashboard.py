import streamlit as st
from supabase import create_client, Client
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Oldal konfiguráció
st.set_page_config(
    page_title="Jarvis AI Business Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Egyedi CSS a profi megjelenésért
st.markdown("""
    <style>
        .main { background-color: #0e1117; }
        .metric-card { background-color: #161b22; padding: 20px; border-radius: 10px; border: 1px solid #30363d; }
    </style>
""", unsafe_allow_html=True)

# Supabase kapcsolat
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# Fejléc
st.title("🛡️ Jarvis AI Business Dashboard")
st.caption("Autonóm B2B Ügyfélszerző, Pontozó & Outreach Vezetői Irányítópult")

# Adatok lekérése a Supabase-ből
@st.cache_data(ttl=60)
def load_data():
    try:
        leads_res = supabase.table("leads").select("*").execute()
        leads_df = pd.DataFrame(leads_res.data) if leads_res.data else pd.DataFrame()
    except Exception:
        leads_df = pd.DataFrame()

    try:
        logs_res = supabase.table("logs").select("*").order("created_at", desc=True).limit(50).execute()
        logs_df = pd.DataFrame(logs_res.data) if logs_res.data else pd.DataFrame()
    except Exception:
        logs_df = pd.DataFrame()
        
    return leads_df, logs_df

leads_df, logs_df = load_data()

# Alapadatok előkészítése
if not leads_df.empty:
    total_leads = len(leads_df)
    new_count = len(leads_df[leads_df["status"] == "new"]) if "status" in leads_df.columns else 0
    sent_count = len(leads_df[leads_df["status"] == "sent"]) if "status" in leads_df.columns else 0
    interested_count = len(leads_df[leads_df["status"] == "interested"]) if "status" in leads_df.columns else 0
    
    # Konverziós arány számítása
    conversion_rate = round((interested_count / sent_count * 100), 1) if sent_count > 0 else 0.0
else:
    total_leads = new_count = sent_count = interested_count = 0
    conversion_rate = 0.0

# --- FELSŐ METRIKÁK (KPI kártyák) ---
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Összes Lead", total_leads, delta=f"{new_count} új")
col2.metric("Várakozó (New)", new_count)
col3.metric("Elküldött Ajánlat", sent_count)
col4.metric("Pozitív Válasz", interested_count)
col5.metric("Konverziós Arány", f"{conversion_rate}%")

st.divider()

# --- FÜLEK A ÁTTEKINTHETŐSÉGÉRT ---
tab_analytics, tab_leads, tab_logs = st.tabs(["📊 Üzleti Elemzések & Grafikonok", "📋 Lead Adatbázis", "📜 Rendszernaplók"])

with tab_analytics:
    if not leads_df.empty:
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            st.subheader("Státusz megoszlás")
            if "status" in leads_df.columns:
                status_counts = leads_df["status"].value_counts().reset_index()
                status_counts.columns = ["status", "count"]
                
                fig_status = px.pie(
                    status_counts, 
                    names="status", 
                    values="count", 
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                fig_status.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white")
                st.plotly_chart(fig_status, use_container_width=True)
            else:
                st.info("Nincs státusz oszlop az adatok között.")
                
        with col_g2:
            st.subheader("Lead Pontszámok Eloszlása (Score)")
            if "score" in leads_df.columns:
                fig_score = px.histogram(
                    leads_df, 
                    x="score", 
                    nbins=10,
                    color_discrete_sequence=["#00CC96"]
                )
                fig_score.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white")
                st.plotly_chart(fig_score, use_container_width=True)
            else:
                st.info("Még nincsenek pontszámok kiszámítva a leidekhez.")
    else:
        st.warning("Még nincsenek adatok a grafikonok megjelenítéséhez.")

with tab_leads:
    st.subheader("Részletes Lead Kezelő")
    if not leads_df.empty:
        selected_status = st.selectbox("Szűrés státusz szerint:", ["Összes"] + list(leads_df["status"].unique()))
        if selected_status != "Összes":
            filtered_df = leads_df[leads_df["status"] == selected_status]
        else:
            filtered_df = leads_df
        st.dataframe(filtered_df, use_container_width=True)
    else:
        st.info("Az adatbázis jelenleg üres.")

with tab_logs:
    st.subheader("Valós idejű Rendszernaplók")
    if not logs_df.empty:
        st.dataframe(logs_df, use_container_width=True)
    else:
        st.info("Nincsenek aktív naplóbejegyzések.")

# Oldalsáv (Sidebar) extra vezérlőkkel
with st.sidebar:
    st.header("⚙️ Rendszer státusz")
    st.success("Minden modul aktív (AI, Scraper, Auditor)")
    if st.button("🔄 Adatok frissítése"):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    st.text("Jarvis Core v2.5\nAutonóm B2B Engine")
