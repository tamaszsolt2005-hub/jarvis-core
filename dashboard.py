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
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    :root { color-scheme:dark; --ink:#edf4ff; --muted:#9bb0ce; --line:rgba(91,160,238,.24); --blue:#168cff; }
    html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"], .stApp,
    [data-testid="stMain"], [data-testid="stMainBlockContainer"] {
        background:#041326 !important; color:var(--ink) !important;
    }
    [data-testid="stHeader"] { background:transparent !important; }
    [data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer { visibility:hidden !important; }
    [data-testid="stSidebar"], [data-testid="collapsedControl"] { display:none !important; }
    .block-container { max-width:1220px !important; padding:1.8rem 2rem 9rem !important; }
    .jarvis-topbar { display:flex; align-items:center; gap:14px; padding:14px 18px; margin:0 auto 1rem;
        max-width:1120px; border:1px solid rgba(94,163,239,.2); border-radius:18px;
        background:linear-gradient(110deg,rgba(9,36,68,.96),rgba(7,23,44,.88));
        box-shadow:0 12px 45px rgba(0,0,0,.2); }
    .jarvis-mark { width:42px;height:42px;display:grid;place-items:center;border-radius:14px;
        color:white;font-size:24px;background:linear-gradient(145deg,#36a4ff,#0755bd);
        box-shadow:0 0 28px rgba(28,137,255,.42); }
    .jarvis-brand { color:#f2f7ff;font-weight:850;letter-spacing:.24em;font-size:.9rem; }
    .jarvis-brand-sub { color:#819cbd;font-size:.62rem;letter-spacing:.16em;margin-top:3px; }
    .jarvis-live { margin-left:auto;color:#a6e4ce;font-size:.68rem;letter-spacing:.13em;
        padding:7px 12px;border-radius:30px;border:1px solid rgba(86,213,164,.3);background:rgba(29,155,111,.12); }
    .jarvis-hero { text-align:center; padding:3.2rem 0 1.2rem; }
    .jarvis-orb-wrap { width:190px;height:190px;margin:0 auto 2rem;display:grid;place-items:center;
        border-radius:50%;position:relative;background:radial-gradient(circle,rgba(34,139,255,.22),rgba(13,65,132,.12) 58%,transparent 72%);
        filter:drop-shadow(0 0 38px rgba(19,117,255,.25)); }
    .jarvis-orb { width:154px;height:154px;border-radius:50%;display:grid;place-items:center;position:relative;
        color:#f3fbff;font-size:65px;
        background:radial-gradient(circle at 32% 24%,#55c8ff 0%,#126bd0 27%,#061b4c 62%,#020b20 100%);
        border:2px solid rgba(89,190,255,.9);
        box-shadow:inset -15px -18px 34px rgba(0,0,0,.65),inset 9px 8px 22px rgba(99,203,255,.5),
        0 0 0 10px rgba(31,130,255,.08),0 0 55px rgba(20,132,255,.42); }
    .jarvis-orb:before { content:"";position:absolute;inset:13px;border-radius:50%;border:1px solid rgba(132,211,255,.36);
        box-shadow:0 0 22px rgba(64,169,255,.22); }
    .jarvis-kicker { color:#69b8ff;font-size:.7rem;font-weight:850;letter-spacing:.27em;margin-bottom:1rem; }
    .jarvis-hero h1 { color:#f0f6ff;font-size:clamp(2.2rem,5vw,4rem);font-weight:820;letter-spacing:-.055em;margin:0 0 .75rem; }
    .jarvis-hero h1 span { background:linear-gradient(90deg,#d8eaff,#64b7ff);-webkit-background-clip:text;background-clip:text;color:transparent; }
    .jarvis-hero p { max-width:690px;margin:0 auto;color:#a3b5ce;font-size:1rem;line-height:1.75; }
    .jarvis-prompts { display:flex;justify-content:center;flex-wrap:wrap;gap:12px;margin:2rem auto 1.5rem;max-width:920px; }
    .jarvis-prompt { border:1px solid rgba(65,153,239,.34);border-radius:999px;padding:11px 17px;
        background:linear-gradient(180deg,rgba(16,63,112,.72),rgba(7,31,60,.88));color:#d2e6ff;
        font-size:.82rem;box-shadow:inset 0 1px rgba(255,255,255,.05); }
    [data-testid="stChatMessage"] { background:rgba(7,28,52,.9) !important;border:1px solid rgba(67,150,232,.28) !important;
        border-radius:18px !important;padding:1rem 1.15rem !important;color:#eaf3ff !important; }
    [data-testid="stChatMessage"] p,[data-testid="stChatMessage"] li { color:#eaf3ff !important;line-height:1.7; }
    [data-testid="stBottom"] { background:linear-gradient(180deg,rgba(4,19,38,0),#041326 32%) !important;
        border-top:0 !important;padding:1.2rem 1rem 1.6rem !important; }
    [data-testid="stBottom"] > div { max-width:960px !important; }
    [data-testid="stChatInput"],[data-testid="stChatInput"] > div { background:rgba(5,27,53,.98) !important;
        border:1px solid rgba(58,157,255,.62) !important;border-radius:22px !important;
        box-shadow:0 12px 48px rgba(0,0,0,.42),0 0 24px rgba(20,116,226,.12) !important; }
    [data-testid="stChatInput"] textarea { color:#f0f7ff !important;caret-color:#5bb8ff !important; }
    [data-testid="stChatInput"] textarea::placeholder { color:#8ba7c8 !important; }
    [data-testid="stChatInput"] button { color:#6dbaff !important; }
    [data-testid="stMarkdownContainer"] p { line-height:1.7; }
    [data-testid="stCaptionContainer"] p { color:#7f9bbb !important;font-size:.7rem; }
    .jarvis-footer { text-align:center;color:#6684a7;font-size:.65rem;letter-spacing:.15em;margin:2.2rem 0 1rem; }
    @media(max-width:700px) {
        .block-container { padding:1rem 1rem 8rem !important; }
        .jarvis-topbar { margin-bottom:.4rem;padding:11px 13px; }
        .jarvis-hero { padding:2.2rem 0 1rem; }
        .jarvis-orb-wrap { width:145px;height:145px;margin-bottom:1.4rem; }
        .jarvis-orb { width:118px;height:118px;font-size:48px; }
        .jarvis-prompts { gap:8px;margin-top:1.3rem; }
        .jarvis-prompt { font-size:.74rem;padding:9px 13px; }
        [data-testid="stBottom"] { padding:1rem .7rem 1.2rem !important; }
    }
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
        # Existing Supabase projects may have an older leads schema. Read the
        # actual row shape, then pass only explicitly approved, non-personal fields
        # into the model context. This avoids failing on optional columns such as
        # website that may not exist in an older database.
        raw_rows = _safe_rows(db, "leads", "*", 1500)
        allowed_lead_fields = {
            "id", "company_name", "source", "status", "approved_to_contact",
            "opted_out", "reply_category", "created_at", "next_follow_up_at",
            "follow_up_count",
        }
        rows = [
            {key: value for key, value in row.items() if key in allowed_lead_fields}
            for row in raw_rows
        ]
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
        # Reuse the schema-tolerant lead snapshot; never require optional columns.
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
st.markdown(
    '<div class="jarvis-hero"><div class="jarvis-orb-wrap"><div class="jarvis-orb">✦</div></div>'
    '<div class="jarvis-kicker">YOUR AI BUSINESS PARTNER</div>'
    '<h1>Welcome to <span>JARVIS</span></h1>'
    '<p>Kérdezz az üzleti működésedről. JARVIS valós időben lekérdezi a releváns adatokat, '
    'összefüggéseket tár fel, és döntéstámogató elemzést készít.</p></div>',
    unsafe_allow_html=True,
)


if "chat" not in st.session_state or not st.session_state.chat:
    st.markdown(
        '<div class="jarvis-prompts">'
        '<div class="jarvis-prompt">✧ &nbsp; Értékesítési elemzés</div>'
        '<div class="jarvis-prompt">◈ &nbsp; Növekedési lehetőségek</div>'
        '<div class="jarvis-prompt">⌖ &nbsp; Lead- és pipeline áttekintés</div>'
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

    stage = "Supabase-kapcsolat"
    try:
        db = st.session_state.get("_jarvis_db")
        if db is None:
            db = get_supabase()
            st.session_state["_jarvis_db"] = db

        stage = "Supabase-adatlekérdezés"
        with st.spinner("JARVIS lekérdezi a szükséges adatokat és elemez…"):
            context, loaded_sources = retrieve_context(db, prompt)

        stage = "Gemini AI-szolgáltatás"
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
            raise RuntimeError("A Gemini üres választ adott vissza.")
        st.session_state.chat.append(("assistant", answer))
        with st.chat_message("assistant"):
            st.markdown(answer)
            st.caption("ADATFORRÁSOK  ·  " + (", ".join(loaded_sources) if loaded_sources else "nincs"))

    except Exception as exc:
        # Show actionable diagnostics without ever printing configured credentials.
        import re
        detail = str(exc).replace("\\n", " ").strip()
        detail = re.sub(r"(?i)(api[_ -]?key|service[_ -]?role[_ -]?key|password|token)(\\s*[:=]\\s*)\\S+", r"\\1\\2[REDACTED]", detail)
        detail = re.sub(r"(?i)eyJ[A-Za-z0-9_-]{20,}\\.?[A-Za-z0-9_.-]*", "[REDACTED_TOKEN]", detail)
        detail = detail[:500] or "Nincs további hibaüzenet."
        st.error(f"A JARVIS művelet a következő szakaszban állt meg: {stage}.")
        st.warning(f"Hiba típusa: {type(exc).__name__} · Részlet: {detail}")
        st.info("A fenti hibaüzenet alapján célzottan javítható a kapcsolat vagy a konfiguráció. API-kulcsot és jelszót ne küldj be.")
        st.session_state.chat.append(("assistant", f"A művelet itt akadt el: {stage}. Hibatípus: {type(exc).__name__}. A részletes hiba a képernyőn látható."))


st.markdown('<div class="jarvis-footer">J.A.R.V.I.S &nbsp;·&nbsp; BUSINESS INTELLIGENCE &nbsp;·&nbsp; SECURE SESSION</div>', unsafe_allow_html=True)
