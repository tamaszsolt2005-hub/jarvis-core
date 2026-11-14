"""JARVIS mobile-friendly operations dashboard."""
from __future__ import annotations

import hmac
import streamlit as st
import pandas as pd
import plotly.express as px

from jarvis_common import get_secret, get_supabase, generate_text

st.set_page_config(page_title="JARVIS | Intelligence Center",page_icon="🛡️",layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
:root{--bg:#090d14;--panel:#111925;--line:#263347;--gold:#d6b477;--muted:#93a1b5}
.stApp{background:radial-gradient(ellipse at 75% 0%,#18263a 0%,#090d14 48%);color:#f2f5fa;font-family:'DM Sans',sans-serif}
h1,h2,h3{font-family:'Space Grotesk',sans-serif}
[data-testid="stSidebar"]{background:#0d1420;border-right:1px solid var(--line)}
.block-container{max-width:1440px;padding-top:1.6rem}
.jarvis-card{background:linear-gradient(145deg,#141f2d,#0e1520);border:1px solid #26364a;border-radius:18px;padding:18px;margin:6px 0}
.jarvis-label{color:#9baabe;font-size:12px;text-transform:uppercase;letter-spacing:1.5px}
.jarvis-value{font-family:'Space Grotesk';font-size:30px;font-weight:700;color:#f6f7fa}
.orb-wrap{display:flex;align-items:center;justify-content:center;height:210px}
.orb{width:150px;height:150px;border-radius:50%;background:radial-gradient(circle at 35% 30%,#e5d3a5 0%,#6e8daf 16%,#233b59 42%,#0c1421 68%);box-shadow:0 0 24px #8ab9e777,0 0 70px #d6b47733,inset -15px -15px 35px #02060c;animation:float 4s ease-in-out infinite,glow 3s ease-in-out infinite alternate}
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-12px)}}
@keyframes glow{from{box-shadow:0 0 20px #8ab9e755,0 0 55px #d6b47722,inset -15px -15px 35px #02060c}to{box-shadow:0 0 35px #8ab9e799,0 0 85px #d6b47755,inset -15px -15px 35px #02060c}}
[data-testid="stMetric"]{background:#111925;border:1px solid #26364a;padding:14px;border-radius:15px}
@media(max-width:700px){.block-container{padding:1rem .8rem}.jarvis-value{font-size:24px}.orb-wrap{height:160px}.orb{width:115px;height:115px}}
</style>
""",unsafe_allow_html=True)

def authenticated() -> bool:
    expected=get_secret("JARVIS_DASHBOARD_PASSWORD")
    if not expected:
        st.error("Hiányzó JARVIS_DASHBOARD_PASSWORD. Állítsd be a Codespace Streamlit secrets fájlban.")
        return False
    if st.session_state.get("authenticated"):
        return True
    st.title("JARVIS access")
    password=st.text_input("Dashboard jelszó",type="password")
    if st.button("Belépés",type="primary"):
        if hmac.compare_digest(password,expected):
            st.session_state["authenticated"]=True
            st.rerun()
        st.error("Hibás jelszó.")
    return False

if not authenticated():
    st.stop()

st.sidebar.title("🛡️ JARVIS")
page=st.sidebar.radio("Navigáció",["Command Center","Lead Intelligence","Analytics","AI Assistant","System"])
st.sidebar.caption("Business intelligence · secure operations")

try:
    db=get_supabase()
    leads=db.table("leads").select("*").order("created_at",desc=True).limit(2000).execute().data or []
    logs=db.table("logs").select("*").order("created_at",desc=True).limit(100).execute().data or []
    settings=db.table("settings").select("*").limit(100).execute().data or []
except Exception as exc:
    st.error(f"Supabase kapcsolat nem elérhető: {type(exc).__name__}: {exc}")
    st.stop()

df=pd.DataFrame(leads)
if "status" not in df: df["status"]=pd.Series(dtype="str")
counts=df["status"].fillna("unknown").value_counts().to_dict() if not df.empty else {}
st.title("JARVIS Intelligence Center")
st.caption("B2B sales operations · real-time Supabase snapshot")
if page=="Command Center":
    c1,c2=st.columns([1,2])
    with c1:
        st.markdown('<div class="orb-wrap"><div class="orb"></div></div>',unsafe_allow_html=True)
    with c2:
        st.subheader("Command Center")
        st.write("A rendszer készen áll az adatok, válaszok és jóváhagyott munkafolyamatok áttekintésére.")
        st.info("Az automatikus e-mailküldés alapértelmezés szerint kikapcsolt. Élesítés előtt ellenőrizd a jogalapot és a leiratkozási folyamatot.")
    cols=st.columns(4)
    metrics=[("Összes lead",len(df)),("Új lead",counts.get("new",0)),("Elküldve",counts.get("sent",0)+counts.get("followed_up",0)),("Válasz / tiltás",counts.get("replied",0)+counts.get("opted_out",0))]
    for col,(label,value) in zip(cols,metrics): col.metric(label,value)
    st.subheader("Legutóbbi aktivitás")
    if logs: st.dataframe(pd.DataFrame(logs).drop(columns=["id"],errors="ignore"),use_container_width=True,hide_index=True)
    else: st.caption("Még nincs naplóbejegyzés.")
elif page=="Lead Intelligence":
    st.subheader("Lead Intelligence")
    if not df.empty:
        cols=[x for x in ["company_name","email","website","status","reply_category","created_at","next_follow_up_at"] if x in df]
        st.dataframe(df[cols],use_container_width=True,hide_index=True)
        st.download_button("Lead lista export (CSV)",df[cols].to_csv(index=False).encode("utf-8-sig"),"jarvis_leads.csv","text/csv")
    else: st.info("Még nincs lead. Importálj felülvizsgált CSV-t a lead_gen.py modullal.")
elif page=="Analytics":
    st.subheader("Business Analytics")
    if counts:
        chart=pd.DataFrame([{"Státusz":k,"Darab":v} for k,v in counts.items()])
        st.plotly_chart(px.pie(chart,names="Státusz",values="Darab",hole=.55),use_container_width=True)
        if "created_at" in df:
            dates=pd.to_datetime(df["created_at"],errors="coerce").dt.date.value_counts().sort_index()
            if not dates.empty: st.plotly_chart(px.bar(x=dates.index.astype(str),y=dates.values,labels={"x":"Dátum","y":"Lead"}),use_container_width=True)
    else: st.info("Nincs még elemezhető adat.")
elif page=="AI Assistant":
    st.subheader("JARVIS AI Assistant")
    st.caption("Az AI a rendszer összesített státuszát kapja meg, személyes e-mail címeket nem.")
    if "chat" not in st.session_state: st.session_state.chat=[]
    for role,msg in st.session_state.chat: st.chat_message(role).write(msg)
    prompt=st.chat_input("Miben segíthetek?")
    if prompt:
        st.session_state.chat.append(("user",prompt))
        context=f"Lead státuszok: {counts}. Utolsó naplók száma: {len(logs)}."
        try: answer=generate_text("Te vagy JARVIS, magyar B2B üzleti asszisztens. Válaszolj tömören.\n"+context+"\nKérdés: "+prompt)
        except Exception as exc: answer=f"AI szolgáltatás nem elérhető: {type(exc).__name__}"
        st.session_state.chat.append(("assistant",answer)); st.rerun()
else:
    st.subheader("System")
    st.write({"lead_count":len(df),"log_count":len(logs),"status_counts":counts})
    st.write("Beállítások")
    if settings: st.dataframe(pd.DataFrame(settings),use_container_width=True,hide_index=True)
    if st.button("Kijelentkezés"):
        st.session_state.clear(); st.rerun()
