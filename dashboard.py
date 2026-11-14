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
    :root { --ink:#17243a; --muted:#68778d; --line:#e4eaf2; --canvas:#f4f7fb; --accent:#4263eb; }
    .stApp { background:var(--canvas); color:var(--ink); }
    .block-container { max-width:920px; padding-top:2.2rem; padding-bottom:4rem; }
    h1,h2,h3 { color:var(--ink); letter-spacing:-.03em; }
    h1 { font-weight:780; }
    [data-testid="stChatMessage"] { border:1px solid var(--line); border-radius:16px; background:white; padding:.9rem 1rem; }
    [data-testid="stChatInput"] { border-radius:16px; }
    .jarvis-eyebrow { color:var(--accent); font-size:.72rem; font-weight:800; letter-spacing:.15em; }
    .jarvis-subtitle { color:var(--muted); margin-top:-.5rem; margin-bottom:1.5rem; }
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

st.markdown('<div class="jarvis-eyebrow">JARVIS / INTELLIGENCE</div>', unsafe_allow_html=True)
st.title("Beszélgess JARVIS-szal")
st.markdown(
    '<div class="jarvis-subtitle">Egyetlen chatfelület. A JARVIS a kérdésed alapján lekérdezi az üzleti adatokat, '
    'majd a beszélgetésben összefoglalja és elemzi őket.</div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.caption("JARVIS AI WORKSPACE")
    st.caption("Az adatok lekérdezése csak olvasási művelet.")
    st.caption("Lead létrehozása, módosítása és e-mail-küldés innen nem történik.")
    if st.button("Kijelentkezés", use_container_width=True):
        st.session_state.clear()
        st.rerun()
    if st.button("Beszélgetés törlése", use_container_width=True):
        st.session_state.chat = []
        st.rerun()

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
            st.caption("Lekérdezett adatforrások: " + (", ".join(loaded_sources) if loaded_sources else "nincs"))
    except Exception as exc:
        st.error("A lekérdezés vagy az AI-elemzés nem sikerült.")
        st.caption(f"Technikai hibakód: {type(exc).__name__}. Titkos kulcsot ne másolj ide.")
        st.session_state.chat.append(("assistant", "Most nem sikerült lekérdeznem vagy elemeznem az adatokat. Ellenőrizd a kapcsolatot, majd próbáld újra."))
