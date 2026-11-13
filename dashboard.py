import streamlit as st
from supabase import create_client

st.set_page_config(page_title="Jarvis Business Dashboard", page_icon="🤖", layout="wide")

st.title("🤖 Jarvis AI Business Dashboard")
st.markdown("Autonóm B2B Ügyfélszerző & Outreach Vezetői Irányítópult")

# Supabase kapcsolat betöltése
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase = create_client(url, key)
except Exception:
    st.warning("Add meg a Supabase kulcsokat a Streamlit Secrets-ben a valós adatokhoz!")
    supabase = None

if supabase:
    leads_res = supabase.table("leads").select("*").execute()
    leads = leads_res.data if leads_res.data else []

    logs_res = supabase.table("logs").select("*").order("id", desc=True).limit(20).execute()
    logs = logs_res.data if logs_res.data else []

    total_leads = len(leads)
    sent_leads = sum(1 for l in leads if l["status"] in ["sent", "followed_up"])
    replied_leads = sum(1 for l in leads if l["status"] == "replied")

    col1, col2, col3 = st.columns(3)
    col1.metric("Összes Lead", total_leads)
    col2.metric("Elküldött Ajánlat", sent_leads)
    col3.metric("Beérkezett Válasz", replied_leads)

    st.divider()

    st.subheader("📋 Aktív Leidek és Státuszok")
    if leads:
        st.dataframe(leads)
    else:
        st.info("Még nincsenek leidek az adatbázisban.")

    st.subheader("📜 Rendszernaplók (Logs)")
    if logs:
        for log in logs:
            st.text(f"[{log.get('module', 'system')}] {log.get('message', '')}")
    else:
        st.info("Még nincsenek naplóbejegyzések.")
