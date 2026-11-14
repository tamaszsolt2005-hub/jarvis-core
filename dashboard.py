import streamlit as st
from supabase import create_client, Client
import pandas as pd
import plotly.express as px
import google.generativeai as genai

# Oldal konfiguráció
st.set_page_config(
    page_title="Jarvis AI Business Dashboard & Chat",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Egyedi stílus
st.markdown("""
    <style>
        .main { background-color: #0e1117; }
    </style>
""", unsafe_allow_html=True)

# Supabase és Gemini kapcsolat
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-3.5-flash')

# Fejléc
st.title("🛡️ Jarvis AI Business Control Center")
st.caption("Autonóm B2B Ügyfélszerző & AI Chat Vezérlőpult")

# Adatok lekérése gyorsítótárral
@st.cache_data(ttl=30)
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

    try:
        settings_res = supabase.table("settings").select("*").execute()
        settings = {item["key"]: item["value"] for item in settings_res.data} if settings_res.data else {}
    except Exception:
        settings = {}
        
    return leads_df, logs_df, settings

leads_df, logs_df, settings = load_data()

# KPI adatok
if not leads_df.empty:
    total_leads = len(leads_df)
    new_count = len(leads_df[leads_df["status"] == "new"]) if "status" in leads_df.columns else 0
    sent_count = len(leads_df[leads_df["status"] == "sent"]) if "status" in leads_df.columns else 0
    interested_count = len(leads_df[leads_df["status"] == "interested"]) if "status" in leads_df.columns else 0
    conversion_rate = round((interested_count / sent_count * 100), 1) if sent_count > 0 else 0.0
else:
    total_leads = new_count = sent_count = interested_count = 0
    conversion_rate = 0.0

# --- FELSŐ KPI SÁV ---
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Összes Lead", total_leads)
col2.metric("Várakozó", new_count)
col3.metric("Elküldött", sent_count)
col4.metric("Pozitív Válasz", interested_count)
col5.metric("Konverzió", f"{conversion_rate}%")

st.divider()

# --- FÜLEK: CHAT ÉS VEZÉRLÉS / GRAFIKONOK / ADATBÁZIS ---
tab_chat, tab_analytics, tab_leads, tab_logs = st.tabs([
    "💬 Jarvis AI Chat & Irányító", 
    "📊 Üzleti Grafikonok", 
    "📋 Lead Adatbázis", 
    "📜 Naplók"
])

with tab_chat:
    st.subheader("Beszélgetés Jarvisszal (Dinamikus Vezérlés)")
    st.info(f"🎯 **Aktuális célcsoport / fókusz:** `{settings.get('target_niche', 'még nincs beállítva')}`")
    
    # Chat üzenetek inicializálása Session State-ben
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Üdvözlöm, Tamás! Én vagyok Jarvis, a B2B asszisztensed. Miben segíthetek? (Mondhatod, hogy kit keressünk, vagy kérhetsz statisztikát!)"}
        ]

    # Előző üzenetek kiírása
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Felhasználói beviteli mező (ChatGPT stílus)
    if prompt := st.chat_input("Írd be az utasítást vagy kérdezz a statisztikákról..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # AI válasz generálása és szándék felismerés
        with st.chat_message("assistant"):
            with st.spinner("Jarvis gondolkodik és cselekszik..."):
                try:
                    system_prompt = (
                        f"Te vagy Jarvis, egy autonóm B2B értékesítési AI asszisztens. "
                        f"A felhasználó (Tamás) most ezt írta: '{prompt}'. "
                        f"Jelenlegi adatok: Összes lead: {total_leads}, Elküldött: {sent_count}, Érdeklődő: {interested_count}. "
                        f"Ha a felhasználó új célcsoportot, nisch-t vagy feladatot adott meg (pl. cukrászok, weboldalak, stb.), "
                        f"akkor a válaszod elejére írd be pontosan ezt: [UPDATE_NICHE: új célcsoport leírása], majd válaszolj barátságosan magyarul. "
                        f"Ha statisztikát kér, foglald össze a fenti számokat."
                    )
                    
                    response = ai_model.generate_content(system_prompt)
                    reply_text = response.text
                    
                    # Ha a válasz tartalmazza a célcsoport frissítést, mentjük a Supabase-be
                    if "[UPDATE_NICHE:" in reply_text:
                        import re
                        match = re.search(r'\[UPDATE_NICHE:\s*(.*?)\]', reply_text)
                        if match:
                            new_niche = match.group(1).strip()
                            supabase.table("settings").upsert({"key": "target_niche", "value": new_niche}).execute()
                            reply_text = re.sub(r'\[UPDATE_NICHE:.*?\]', '', reply_text).strip()
                            reply_text += f"\n\n✅ *Sikeresen frissítettem a célcsoportot a rendszerben:* **{new_niche}**"
                    
                    st.markdown(reply_text)
                    st.session_state.messages.append({"role": "assistant", "content": reply_text})
                except Exception as e:
                    err_msg = f"Hiba történt a válaszadás során: {e}"
                    st.error(err_msg)
                    st.session_state.messages.append({"role": "assistant", "content": err_msg})

with tab_analytics:
    if not leads_df.empty:
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.subheader("Státusz megoszlás")
            if "status" in leads_df.columns:
                status_counts = leads_df["status"].value_counts().reset_index()
                status_counts.columns = ["status", "count"]
                fig_status = px.pie(status_counts, names="status", values="count", hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
                fig_status.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white")
                st.plotly_chart(fig_status, use_container_width=True)
        with col_g2:
            st.subheader("Lead Pontszámok Eloszlása")
            if "score" in leads_df.columns:
                fig_score = px.histogram(leads_df, x="score", nbins=10, color_discrete_sequence=["#00CC96"])
                fig_score.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white")
                st.plotly_chart(fig_score, use_container_width=True)
    else:
        st.warning("Még nincsenek adatok a grafikonokhoz.")

with tab_leads:
    st.subheader("Lead Adatbázis")
    if not leads_df.empty:
        st.dataframe(leads_df, use_container_width=True)
    else:
        st.info("Az adatbázis üres.")

with tab_logs:
    st.subheader("Rendszernaplók")
    if not logs_df.empty:
        st.dataframe(logs_df, use_container_width=True)
    else:
        st.info("Nincsenek naplók.")

# Oldalsáv
with st.sidebar:
    st.header("⚙️ Vezérlőpult")
    st.success("Jarvis Core Online 🟢")
    if st.button("🔄 Adatok frissítése"):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    st.text("Mobilbarát PWA felület\nVerzió: 3.0")
