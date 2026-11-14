"""JARVIS — chat-first B2B intelligence workspace.

The UI is intentionally limited to conversation. Business data is retrieved
on demand from Supabase in response to the user's question; the assistant
can analyze and explain that data but this interface performs no mutations
and never sends email.
"""
from __future__ import annotations

import hmac
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import streamlit as st

from jarvis_common import generate_text, get_secret, get_supabase


st.set_page_config(
    page_title="JARVIS | AI Workspace",
    page_icon="✦",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    :root { color-scheme:dark; --ink:#e8eefb; --muted:#91a0ba; --line:rgba(145,166,205,.17); --panel:rgba(15,25,45,.82); --accent:#69a7ff; }
    .stApp { background:radial-gradient(ellipse at 50% -18%, #1b3762 0%, #0b1425 47%, #070d18 100%); color:var(--ink); }
    [data-testid="stHeader"] { background:transparent; }
    [data-testid="stToolbar"] { right:1rem; }
    .block-container { max-width:980px; padding-top:2.1rem; padding-bottom:7rem; }
    h1,h2,h3,p,label,span { color:var(--ink); }
    h1 { font-weight:760; letter-spacing:-.045em; }
    .jarvis-topbar { display:flex; align-items:center; gap:13px; padding:13px 16px; margin-bottom:2.1rem; border:1px solid var(--line); border-radius:18px; background:rgba(10,20,38,.66); box-shadow:0 12px 44px rgba(0,0,0,.18); backdrop-filter:blur(16px); }
    .jarvis-mark { width:39px; height:39px; display:grid; place-items:center; border-radius:13px; color:#dceaff; font-size:21px; background:linear-gradient(145deg,#2f72d5,#61b5ff); box-shadow:0 0 25px rgba(67,145,255,.34); }
    .jarvis-brand { font-weight:800; letter-spacing:.17em; font-size:.86rem; color:#f2f6ff; }
    .jarvis-brand-sub { font-size:.68rem; letter-spacing:.11em; color:#8296b6; margin-top:2px; }
    .jarvis-live { margin-left:auto; color:#9fd8c0; font-size:.69rem; letter-spacing:.1em; border:1px solid rgba(91,205,155,.25); background:rgba(44,155,111,.1); padding:6px 10px; border-radius:30px; }
    .jarvis-hero { text-align:center; padding:1.25rem 0 1.65rem; }
    .jarvis-orb { width:72px; height:72px; margin:0 auto 1.15rem; display:grid; place-items:center; border-radius:24px; font-size:34px; color:#eaf4ff; background:radial-gradient(circle at 32% 25%,#79c6ff,#3677dc 58%,#173c79); box-shadow:0 0 0 8px rgba(76,143,239,.07),0 0 55px rgba(53,132,240,.28); }
    .jarvis-kicker { color:#77b5ff; font-size:.68rem; font-weight:800; letter-spacing:.23em; margin-bottom:.7rem; }
    .jarvis-hero h1 { font-size:clamp(2rem,5vw,3.1rem); margin:0 0 .55rem; color:#f2f6ff; }
    .jarvis-hero p { max-width:610px; margin:0 auto; color:#9aabc5; font-size:.96rem; line-height:1.65; }
    .jarvis-prompts { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin:1rem 0 2rem; }
    .jarvis-prompt { padding:13px 14px; border:1px solid var(--line); border-radius:14px; background:rgba(16,29,51,.68); color:#b8c8e0; font-size:.81rem; line-height:1.5; }
    [data-testid="stChatMessage"] { border:1px solid var(--line); border-radius:18px; background:rgba(14,25,44,.83); padding:1rem 1.1rem; backdrop-filter:blur(12px); }
    [data-testid="stChatMessage"][data-testid="chat-message-assistant"] { border-color:rgba(87,157,255,.23); }
    [data-testid="stChatInput"] { border:1px solid rgba(112,164,231,.32); border-radius:18px; background:rgba(12,23,41,.96); box-shadow:0 10px 42px rgba(0,0,0,.25); }
    [data-testid="stChatInput"] textarea { color:#edf4ff !important; }
    [data-testid="stChatInput"] button { color:#82bdff !important; }
    [data-testid="stMarkdownContainer"] p { line-height:1.68; }
    [data-testid="stCaptionContainer"] p { color:#8295b2; font-size:.7rem; }
    div.stButton > button { border:1px solid var(--line); border-radius:12px; background:rgba(18,33,56,.78); color:#c6d5ec; }
    div.stButton > button:hover { border-color:rgba(105,167,255,.6); color:white; }
    .jarvis-footer { text-align:center; color:#647895; font-size:.69rem; letter-spacing:.07em; margin-top:2rem; }
    @media(max-width:700px) { .block-container{padding:1rem 1rem 6rem;} .jarvis-prompts{grid-template-columns:1fr;} .jarvis-topbar{margin-bottom:1.2rem;} }
    </style>
    """,
    unsafe_allow_html=True,
)


def authenticated() -> bool:
    expected = get_secret("JARVIS_DASHBOARD_PASSWORD")
    if not expected:
        st.error("Hiányzó JARVIS_DASHBOARD_PASSWORD. Állítsd be a Codespace secrets konfigurációjában.")
        return False
    if st.session_state.get("authenticated"):
        return True
    st.markdown('<div class="jarvis-eyebrow">PRIVATE BUSINESS INTELLIGENCE</div>', unsafe_allow_html=True)
    st.title("JARVIS")
    st.caption("A beszélgetéshez jelentkezz be.")
    password = st.text_input("Dashboard jelszó", type="password")
    if st.button("Belépés", type="primary", use_container_width=True):
        if hmac.compare_digest(password, expected):
            st.session_state["authenticated"] = True
            st.rerun()
        st.error("Hibás jelszó.")
    return False


def _safe_rows(db: Any, table: str, columns: str, limit: int = 500) -> list[dict]:
    """Read-only, bounded Supabase query. Never writes or exposes credentials."""
    return db.table(table).select(columns).limit(limit).execute().data or []


def retrieve_context(db: Any, question: str) -> tuple[str, list[str]]:
    """Choose only the datasets relevant to the user's natural-language question."""
    q = question.casefold()
    sections: list[str] = []
    loaded: list[str] = []

    wants_all = any(x in q for x in ("minden", "teljes", "átfogó", "áttekint", "összes"))
    wants_leads = wants_all or any(x in q for x in ("lead", "ügyfél", "cég", "pipeline", "értékesít", "konverz"))
    wants_tasks = wants_all or any(x in q for x in ("feladat", "határid", "teendő", "utánkövet"))
    wants_drafts = wants_all or any(x in q for x in ("piszkozat", "tervezet", "e-mail", "email", "levél"))
    wants_logs = wants_all or any(x in q for x in ("napló", "aktivit", "hiba", "rendszer"))
    wants_analytics = any(x in q for x in ("elemz", "analíz", "analiz", "teljesít", "trend", "statiszt", "arány"))

    # A generic business question receives a compact overview, not an empty context.
    if not any((wants_leads, wants_tasks, wants_drafts, wants_logs)):
        wants_leads = wants_tasks = True

    if wants_leads:
        rows = _safe_rows(
            db, "leads",
            "id,company_name,website,source,status,approved_to_contact,opted_out,reply_category,created_at,next_follow_up_at,follow_up_count",
            1500,
        )
        frame = pd.DataFrame(rows)
        counts = frame["status"].fillna("unknown").value_counts().to_dict() if not frame.empty and "status" in frame else {}
        # Deliberately exclude personal email addresses and free-text notes from model context.
        sections.append("LEAD ADATOK (személyes e-mail-címek nélkül):\n"
                        + f"Összes lead: {len(rows)}; státusz szerinti megoszlás: {counts}.\n"
                        + frame.head(250).to_json(orient="records", force_ascii=False, date_format="iso"))
        loaded.append("leadek")

    if wants_tasks:
        rows = _safe_rows(db, "tasks", "id,title,notes,priority,status,due_at,completed_at,created_at,lead_id", 500)
        sections.append("FELADATOK:\n" + pd.DataFrame(rows).head(250).to_json(orient="records", force_ascii=False, date_format="iso"))
        loaded.append("feladatok")

    if wants_drafts:
        rows = _safe_rows(db, "email_drafts", "id,recipient,subject,status,created_at,lead_id", 200)
        # Draft bodies are not sent to the model unless the user later explicitly asks for review.
        sections.append("E-MAIL PISZKOZAT METAADATOK (levéltörzs nélkül):\n"
                        + pd.DataFrame(rows).to_json(orient="records", force_ascii=False, date_format="iso"))
        loaded.append("e-mail-piszkozatok")

    if wants_logs:
        rows = _safe_rows(db, "logs", "module,level,message,created_at", 100)
        sections.append("RENDSZERNAPLÓ:\n" + pd.DataFrame(rows).head(80).to_json(orient="records", force_ascii=False, date_format="iso"))
        loaded.append("naplók")

    if wants_analytics and wants_leads:
        rows = _safe_rows(db, "leads", "status,created_at,reply_category,follow_up_count,opted_out", 1500)
        frame = pd.DataFrame(rows)
        if not frame.empty:
            sections.append("ELEMZÉSI ALAPADATOK:\n"
                            + f"Státuszok: {frame['status'].fillna('unknown').value_counts().to_dict()}\n"
                            + f"Leiratkozottak: {int(frame['opted_out'].fillna(False).astype(bool).sum())}\n"
                            + f"Utánkövetések összesen: {int(pd.to_numeric(frame['follow_up_count'], errors='coerce').fillna(0).sum())}\n"
                            + "Létrehozási dátumok: " + frame["created_at"].fillna("").astype(str).head(500).to_json(orient="values"))
        if "elemzési összesítés" not in loaded:
            loaded.append("elemzési összesítés")

    return "\n\n".join(sections) or "A kérdéshez nem találtam releváns adatforrást.", loaded


if not authenticated():
    st.stop()

st.markdown(
    '<div class="jarvis-topbar"><div class="jarvis-mark">✦</div><div><div class="jarvis-brand">J.A.R.V.I.S</div>'
    '<div class="jarvis-brand-sub">BUSINESS INTELLIGENCE SYSTEM</div></div>'
    '<div class="jarvis-live">● READY</div></div>',
    unsafe_allow_html=True,
)
head_left, head_right = st.columns([7, 1])
with head_left:
    st.markdown(
        '<div class="jarvis-hero"><div class="jarvis-orb">✦</div>'
        '<div class="jarvis-kicker">YOUR AI BUSINESS PARTNER</div>'
        '<h1>Jó napot. Miben segíthetek?</h1>'
        '<p>Kérdezz az üzleti működésedről. Lekérdezem a releváns adatokat, összefüggéseket keresek, '
        'és érthető, döntéstámogató elemzést készítek.</p></div>',
        unsafe_allow_html=True,
    )
with head_right:
    if st.button("Kilépés", help="Kijelentkezés"):
        st.session_state.clear()
        st.rerun()

if "chat" not in st.session_state or not st.session_state.chat:
    st.markdown(
        '<div class="jarvis-prompts">'
        '<div class="jarvis-prompt">⌁ &nbsp; Elemezd az értékesítési teljesítményünket és a fő trendeket.</div>'
        '<div class="jarvis-prompt">◈ &nbsp; Mely területeken van a legnagyobb növekedési lehetőség?</div>'
        '<div class="jarvis-prompt">⌖ &nbsp; Készíts áttekintést a leadek állapotáról és a következő teendőkről.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

if "chat" not in st.session_state:
    st.session_state.chat = []

for role, message in st.session_state.chat:
    with st.chat_message(role):
        st.markdown(message)

prompt = st.chat_input("Kérdezz a leadekről, kérj elemzést vagy üzleti javaslatot…")
if prompt:
    st.session_state.chat.append(("user", prompt))
    with st.chat_message("user"):
        st.markdown(prompt)

    try:
        db = st.session_state.get("_jarvis_db")
        if db is None:
            db = get_supabase()
            st.session_state["_jarvis_db"] = db
        with st.spinner("JARVIS lekérdezi a szükséges adatokat és elemez…"):
            context, loaded_sources = retrieve_context(db, prompt)
            history = "\n".join(
                f"{role}: {message}" for role, message in st.session_state.chat[-9:-1]
            )
            answer = generate_text(
                "Te JARVIS vagy, magyar nyelvű B2B üzleti intelligencia-asszisztens. "
                "A felhasználó kérdésére a mellékelt, élő adatbázisból lekért kontextus alapján válaszolj. "
                "Ha elemzést kér, ténylegesen elemezd az adatokat: mutass számokat, arányokat, trendeket, "
                "korlátokat és konkrét, rangsorolt javaslatokat. Ne találj ki hiányzó adatot; jelezd, ha "
                "valami nem számítható ki. A személyes adatokat ne következtesd ki. "
                "Nem hozhatsz létre vagy módosíthatsz rekordot, nem küldhetsz e-mailt, és ne állítsd, hogy "
                "ilyen műveletet elvégeztél. Az automatikus e-mail-küldés nincs engedélyezve. "
                "Válaszolj magyarul, áttekinthetően, a kérdés mélységéhez igazodva.\n\n"
                f"LEKÉRDEZETT ADATFORRÁSOK: {', '.join(loaded_sources) or 'nincs'}\n"
                f"AKTUÁLIS ADATOK:\n{context}\n\n"
                f"BESZÉLGETÉSI ELŐZMÉNY:\n{history}\n\n"
                f"FELHASZNÁLÓ KÉRDÉSE: {prompt}"
            )
        if not answer:
            answer = "Nem kaptam értékelhető választ az AI-szolgáltatástól. Kérlek, próbáld újra."
        st.session_state.chat.append(("assistant", answer))
        with st.chat_message("assistant"):
            st.markdown(answer)
            st.caption("ADATFORRÁSOK  ·  " + (", ".join(loaded_sources) if loaded_sources else "nincs"))
    except Exception as exc:
        st.error("A lekérdezés vagy az AI-elemzés nem sikerült.")
        st.caption(f"Technikai hibakód: {type(exc).__name__}. Titkos kulcsot ne másolj ide.")
        st.session_state.chat.append(("assistant", "Most nem sikerült lekérdeznem vagy elemeznem az adatokat. Ellenőrizd a kapcsolatot, majd próbáld újra."))


st.markdown('<div class="jarvis-footer">JARVIS INTELLIGENCE CORE &nbsp;·&nbsp; READ-ONLY DATA ACCESS &nbsp;·&nbsp; HUMAN-LED DECISIONS</div>', unsafe_allow_html=True)
