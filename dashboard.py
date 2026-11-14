import streamlit as st
from supabase import create_client, Client
import pandas as pd

# Oldal konfiguráció
st.set_page_config(page_title="Jarvis AI Business Dashboard", layout="wide")

url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

st.title("🛡️ Jarvis AI Business Dashboard")
st.caption("Autonóm B2B Ügyfélszerző & Outreach Vezetői Irányítópult")

# Adatok lekérése a Supabase-ből
try:
    leads_res = supabase.table("leads").select("*").execute()
    leads_df = pd.DataFrame(leads_res.data) if leads_res.data else pd.DataFrame()
except Exception as e:
    st.error(f"Hiba az adatbázis elérésekor: {e}")
    leads_df = pd.DataFrame()

try:
    logs_res = supabase.table("logs").select("*").order("created_at", desc=True).limit(20).execute()
    logs_df = pd.DataFrame(logs_res.data) if logs_res.data else pd.DataFrame()
except Exception:
    logs_df = pd.DataFrame()

# Metrikák / KPI-k kiszámítása
if not leads_df.empty and "status" in leads_df.columns:
    total_leads = len(leads_df)
    sent_count = len(leads_df[leads_df["status"] == "sent"])
    interested_count = len(leads_df[leads_df["status"] == "interested"]) if "interested" in leads_df["status"].values else 0
    new_count = len(leads_df[leads_df["status"] == "new"])
else:
    total_leads = sent_count = interested_count = new_count = 0

# Felső KPI sáv
col1, col2, col3, col4 = st.columns(4)
col1.metric("Összes Lead", total_leads)
col2.metric("Új (Várakozó)", new_count)
col3.metric("Elküldött Ajánlat", sent_count)
col4.metric("Pozitív Válasz", interested_count)

st.divider()

# Aktív Leidek táblázat szűrővel
st.subheader("📋 Aktív Leidek és Státuszok")
if not leads_df.empty:
    status_filter = st.selectbox("Szűrés státusz szerint:", ["Összes"] + list(leads_df["status"].unique()))
    if status_filter != "Összes":
        filtered_df = leads_df[leads_df["status"] == status_filter]
    else:
        filtered_df = leads_df
    st.dataframe(filtered_df, use_container_width=True)
else:
    st.info("Még nincsenek leidek az adatbázisban.")

st.divider()

# Rendszernaplók
st.subheader("📜 Valós idejű Rendszernaplók (Logs)")
if not logs_df.empty:
    st.dataframe(logs_df, use_container_width=True)
else:
    st.info("Még nincsenek naplóbejegyzések.")
