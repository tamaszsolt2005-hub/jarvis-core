"""JARVIS Intelligence Center — clean, responsive Streamlit dashboard."""
from __future__ import annotations

import hmac

import pandas as pd
import plotly.express as px
import streamlit as st

from jarvis_common import generate_text, get_secret, get_supabase, log_event
from lead_scoring import score_lead
from datetime import datetime, timedelta, timezone

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
    ["Áttekintés", "Leadek", "Értékesítési tölcsér", "Feladatok", "E-mail tervezetek", "Elemzések", "AI asszisztens", "Rendszer"],
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
for lead in leads:
    lead["lead_score"] = score_lead(lead)
try:
    tasks = db.table("tasks").select("*").order("due_at", desc=False).limit(500).execute().data or []
    tasks_available = True
except Exception:
    tasks, tasks_available = [], False
try:
    drafts = db.table("email_drafts").select("*").order("created_at", desc=True).limit(200).execute().data or []
    drafts_available = True
except Exception:
    drafts, drafts_available = [], False

st.markdown('<div class="eyebrow">JARVIS / INTELLIGENCE CENTER</div>', unsafe_allow_html=True)
st.title(
    {
        "Áttekintés": "Üzleti áttekintés",
        "Leadek": "Leadkezelés",
        "Értékesítési tölcsér": "Értékesítési tölcsér",
        "Feladatok": "Feladatközpont",
        "E-mail tervezetek": "E-mail tervezetek",
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

    with st.expander("＋ Új lead felvétele", expanded=False):
        with st.form("create_lead_form", clear_on_submit=True):
            company = st.text_input("Cégnév *")
            email = st.text_input("Kapcsolattartó e-mail-címe *")
            website = st.text_input("Weboldal")
            source = st.text_input("Forrás", placeholder="Pl. ajánlás, weboldal, rendezvény")
            notes = st.text_area("Megjegyzések")
            consent_basis = st.text_input(
                "Kapcsolatfelvétel jogalapja / engedély megjegyzése",
                help="Rögzítsd a kapcsolatfelvétel jogszerű alapját. A lead alapból nem lesz megkeresésre jóváhagyva.",
            )
            approved = st.checkbox("Kapcsolatfelvétel külön ellenőrizve és jóváhagyva", value=False)
            submitted = st.form_submit_button("Lead mentése", type="primary")
            if submitted:
                if not company.strip() or not email.strip():
                    st.error("A cégnév és az e-mail-cím kötelező.")
                elif "@" not in email or "." not in email.rsplit("@", 1)[-1]:
                    st.error("Adj meg érvényesnek tűnő e-mail-címet.")
                else:
                    try:
                        payload = {
                            "company_name": company.strip(),
                            "email": email.strip().lower(),
                            "website": website.strip() or None,
                            "source": source.strip() or None,
                            "notes": notes.strip() or None,
                            "consent_basis": consent_basis.strip().lower() or None,
                            "approved_to_contact": bool(approved and consent_basis.strip().lower() == "consent"),
                            "consent_confirmed_at": datetime.now(timezone.utc).isoformat()
                                if approved and consent_basis.strip().lower() == "consent" else None,
                            "status": "new",
                        }
                        db.table("leads").insert(payload).execute()
                        log_event(db, "lead_management", f"Új lead létrehozva: {company.strip()}")
                        st.success("A lead sikeresen elmentve.")
                        st.rerun()
                    except Exception as exc:
                        st.error("A lead mentése nem sikerült.")
                        st.caption(f"Technikai részlet: {type(exc).__name__}")

    if not df.empty:
        visible = [
            c for c in [
                "company_name", "email", "website", "status", "approved_to_contact",
                "opted_out", "reply_category", "created_at", "next_follow_up_at",
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

        st.divider()
        st.subheader("Lead szerkesztése")
        choices = {
            f"{row.get('company_name') or 'Névtelen cég'} · {row.get('email') or 'nincs e-mail'} · {str(row.get('id'))[:8]}": row
            for row in leads
        }
        selected_label = st.selectbox("Válaszd ki a módosítandó leadet", list(choices))
        selected = choices[selected_label]
        status_options = ["new", "sent", "followed_up", "replied", "opted_out", "qualified", "disqualified"]
        current_status = selected.get("status") or "new"
        if current_status not in status_options:
            status_options.insert(0, current_status)
        with st.form("edit_lead_form"):
            edit_company = st.text_input("Cégnév", value=selected.get("company_name") or "")
            edit_email = st.text_input("E-mail-cím", value=selected.get("email") or "")
            edit_website = st.text_input("Weboldal", value=selected.get("website") or "")
            edit_source = st.text_input("Forrás", value=selected.get("source") or "")
            edit_notes = st.text_area("Megjegyzések", value=selected.get("notes") or "")
            edit_status = st.selectbox(
                "Státusz",
                status_options,
                index=status_options.index(current_status),
            )
            edit_opted_out = st.checkbox("Leiratkozott / nem kereshető", value=bool(selected.get("opted_out")))
            edit_approved = st.checkbox(
                "Kapcsolatfelvétel jóváhagyva",
                value=bool(selected.get("approved_to_contact")),
            )
            save = st.form_submit_button("Módosítások mentése", type="primary")
            if save:
                if not edit_company.strip() or not edit_email.strip():
                    st.error("A cégnév és az e-mail-cím nem lehet üres.")
                elif "@" not in edit_email or "." not in edit_email.rsplit("@", 1)[-1]:
                    st.error("Adj meg érvényesnek tűnő e-mail-címet.")
                else:
                    try:
                        # A leiratkozást és a tiltást nem engedjük véletlenül feloldani.
                        updates = {
                            "company_name": edit_company.strip(),
                            "email": edit_email.strip().lower(),
                            "website": edit_website.strip() or None,
                            "source": edit_source.strip() or None,
                            "notes": edit_notes.strip() or None,
                            "status": "opted_out" if edit_opted_out else edit_status,
                            "opted_out": bool(edit_opted_out or selected.get("opted_out")),
                            "approved_to_contact": bool(
                                edit_approved
                                and not edit_opted_out
                                and not selected.get("opted_out")
                                and selected.get("consent_basis") == "consent"
                                and selected.get("consent_confirmed_at")
                            ),
                            "updated_at": pd.Timestamp.now(tz="UTC").isoformat(),
                        }
                        if selected.get("opted_out"):
                            updates["status"] = "opted_out"
                            updates["approved_to_contact"] = False
                        db.table("leads").update(updates).eq("id", selected["id"]).execute()
                        log_event(db, "lead_management", f"Lead módosítva: {edit_company.strip()} ({selected['id']})")
                        st.success("A lead módosításai elmentve.")
                        st.rerun()
                    except Exception as exc:
                        st.error("A módosítás mentése nem sikerült.")
                        st.caption(f"Technikai részlet: {type(exc).__name__}")

        st.download_button(
            "Leadlista letöltése CSV-ben",
            view.to_csv(index=False).encode("utf-8-sig"),
            "jarvis_leads.csv",
            "text/csv",
        )
    else:
        st.info("Még nincs lead az adatbázisban. Az „Új lead felvétele” résznél hozzáadhatod az elsőt.")

elif page == "Értékesítési tölcsér":
    st.subheader("Pipeline áttekintés")
    stages = ["new", "qualified", "sent", "followed_up", "replied", "opted_out", "disqualified"]
    cols = st.columns(len(stages))
    for col, stage in zip(cols, stages):
        with col:
            st.metric(stage.replace("_", " ").title(), counts.get(stage, 0))
    ranked = sorted(leads, key=lambda x: x.get("lead_score", 0), reverse=True)
    if ranked:
        st.subheader("Prioritási lista")
        st.dataframe(pd.DataFrame([{
            "Cég": x.get("company_name"), "E-mail": x.get("email"),
            "Pontszám": x.get("lead_score"), "Státusz": x.get("status"),
            "Jóváhagyva": bool(x.get("approved_to_contact")),
        } for x in ranked[:25]]), use_container_width=True, hide_index=True)
    st.caption("A pontszám prioritási becslés, nem kapcsolatfelvételi engedély.")

elif page == "Feladatok":
    st.subheader("Feladatok és utánkövetés")
    if not tasks_available:
        st.warning("A feladatmodul táblája még nincs telepítve. Futtasd a frissített supabase/schema.sql fájlt a Supabase SQL Editorban.")
    else:
        with st.expander("＋ Új feladat", expanded=True):
            with st.form("create_task_form", clear_on_submit=True):
                task_title = st.text_input("Feladat címe *")
                task_options = ["— nincs lead —"] + [f"{x.get('company_name')} · {x.get('id')}" for x in leads]
                task_lead = st.selectbox("Kapcsolódó lead", task_options)
                task_due = st.date_input("Határidő", value=datetime.now().date() + timedelta(days=1))
                task_priority = st.selectbox("Prioritás", ["normal", "high", "urgent"])
                task_notes = st.text_area("Leírás")
                task_submit = st.form_submit_button("Feladat létrehozása", type="primary")
                if task_submit:
                    if not task_title.strip():
                        st.error("A feladat címe kötelező.")
                    else:
                        linked_id = task_lead.rsplit(" · ", 1)[-1] if task_lead != "— nincs lead —" else None
                        try:
                            db.table("tasks").insert({
                                "title": task_title.strip(), "lead_id": linked_id,
                                "due_at": datetime.combine(task_due, datetime.min.time(), tzinfo=timezone.utc).isoformat(),
                                "priority": task_priority, "notes": task_notes.strip() or None, "status": "open",
                            }).execute()
                            log_event(db, "tasks", f"Feladat létrehozva: {task_title.strip()}")
                            st.success("Feladat elmentve."); st.rerun()
                        except Exception as exc:
                            st.error("A feladat mentése nem sikerült."); st.caption(type(exc).__name__)
        if tasks:
            task_df = pd.DataFrame(tasks)
            st.dataframe(task_df[[c for c in ["title", "status", "priority", "due_at", "lead_id", "notes"] if c in task_df]],
                         use_container_width=True, hide_index=True)
            open_tasks = [t for t in tasks if t.get("status") == "open"]
            if open_tasks:
                task_map = {f"{t.get('title')} · {str(t.get('id'))[:8]}": t for t in open_tasks}
                chosen = st.selectbox("Lezárandó feladat", list(task_map))
                if st.button("Feladat készre állítása"):
                    item = task_map[chosen]
                    db.table("tasks").update({"status": "done", "completed_at": datetime.now(timezone.utc).isoformat()}).eq("id", item["id"]).execute()
                    log_event(db, "tasks", f"Feladat lezárva: {item.get('title')}")
                    st.rerun()
        else:
            st.info("Még nincs feladat.")

elif page == "E-mail tervezetek":
    st.subheader("AI-alapú e-mail-tervező")
    st.warning("Ez a modul kizárólag piszkozatot készít és ment. E-mailt nem küld.")
    if not drafts_available:
        st.warning("A piszkozatok táblája még nincs telepítve. Futtasd a frissített supabase/schema.sql fájlt.")
    elif leads:
        chosen_lead = st.selectbox("Címzett lead", leads, format_func=lambda x: f"{x.get('company_name')} · {x.get('email')}")
        goal = st.text_input("E-mail célja", value="Rövid szakmai bemutatkozás")
        if st.button("Piszkozat generálása", type="primary"):
            try:
                generated = generate_text(
                    "Írj magyar, tényszerű B2B e-mail PISZKOZATOT. Ne találj ki tényt, ne állíts "
                    "nem igazolt személyre szabást. Adj tárgyat és törzset. Ne küldd el. "
                    + "Cég: " + str(chosen_lead.get("company_name"))
                    + "; weboldal: " + str(chosen_lead.get("website") or "nincs")
                    + "; cél: " + goal
                )
                db.table("email_drafts").insert({
                    "lead_id": chosen_lead.get("id"), "recipient": chosen_lead.get("email"),
                    "subject": "JARVIS tervezet – ellenőrizendő", "body": generated[:8000], "status": "draft",
                }).execute()
                log_event(db, "email_drafts", f"Piszkozat készült: {chosen_lead.get('company_name')}")
                st.success("Piszkozat elmentve. Küldés nem történt."); st.rerun()
            except Exception as exc:
                st.error("A piszkozat generálása nem sikerült."); st.caption(type(exc).__name__)
        if drafts:
            st.subheader("Mentett piszkozatok")
            for item in drafts:
                with st.expander(f"{item.get('recipient')} · {item.get('created_at')}"):
                    st.text_area("Tartalom", value=item.get("body") or "", height=180, key=f"draft_{item.get('id')}")
                    st.caption("Piszkozat – manuális ellenőrzés szükséges.")
    else:
        st.info("Előbb vegyél fel legalább egy leadet.")

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
                    "Képességhatárok: az összesített leadstátuszokból és naplókból elemzést, javaslatot és "
                    "szövegtervezetet adhatsz. A felhasználó a külön dashboard-oldalakon leadeket kezelhet, "
                    "feladatokat hozhat létre és e-mail-piszkozatot generálhat. Te magad nem hajthatsz végre "
                    "adatbázis-műveletet, nem módosíthatsz leadet vagy feladatot, és nem küldhetsz e-mailt. "
                    "Soha ne állítsd, hogy ilyen műveletet elvégeztél. Ne találj ki adatot vagy funkciót.\n"
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
