"""Lead review workspace with evidence-aware ranking and human-only decisions."""
from __future__ import annotations

import ipaddress
import math
import re
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import streamlit as st



_COUNTRY_FLAGS = {
    "austria": "🇦🇹", "belgium": "🇧🇪", "canada": "🇨🇦", "czechia": "🇨🇿",
    "denmark": "🇩🇰", "finland": "🇫🇮", "france": "🇫🇷", "germany": "🇩🇪",
    "hungary": "🇭🇺", "ireland": "🇮🇪", "italy": "🇮🇹", "netherlands": "🇳🇱",
    "norway": "🇳🇴", "poland": "🇵🇱", "portugal": "🇵🇹", "romania": "🇷🇴",
    "slovakia": "🇸🇰", "spain": "🇪🇸", "sweden": "🇸🇪", "switzerland": "🇨🇭",
    "united kingdom": "🇬🇧", "united states": "🇺🇸", "usa": "🇺🇸",
    "uk": "🇬🇧", "unknown": "🏳️", "ismeretlen": "🏳️",
}
_COUNTRY_PATTERN = re.compile(r"tényleges ország\s*:\s*([^;,.]+)", re.I)
_SUMMARY_PATTERN = re.compile(r"Cégprofil\s*:\s*(.*?)(?:\s+Lehetséges illeszkedés\s*:|$)", re.I)
_FIT_PATTERN = re.compile(r"Lehetséges illeszkedés\s*:\s*(.*?)(?:\s+AI üzleti illeszkedési becslés\s*:|$)", re.I)
_NEED_PATTERN = re.compile(r"megfigyelhető üzleti igény\s*:\s*(.*?)(?:\s+alátámasztó jelek\s*:|$)", re.I)


def extract_country(lead: dict[str, Any]) -> str:
    """Extract the researched country from the existing grounded lead note."""
    notes = str(lead.get("notes") or "")
    match = _COUNTRY_PATTERN.search(notes)
    return (match.group(1).strip() if match else "ismeretlen")[:100]


def country_flag(country: str) -> str:
    return _COUNTRY_FLAGS.get(str(country or "").strip().casefold(), "🏳️")


def _note_value(pattern: re.Pattern[str], notes: str) -> str:
    match = pattern.search(notes or "")
    return re.sub(r"\s+", " ", match.group(1)).strip()[:900] if match else ""


def _safe_source_url(value: Any) -> str | None:
    raw = str(value or "").strip()
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return None
    host = parsed.hostname.rstrip(".").casefold()
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        return None
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        return None
    return raw[:2048]


def _load_rows(db: Any, table: str, columns: str, limit: int = 1000) -> list[dict[str, Any]]:
    response = db.table(table).select(columns).limit(limit).execute()
    rows = getattr(response, "data", None) or []
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _score_snapshot_assessment(dossier: dict[str, Any]) -> dict[str, Any]:
    """Score only the versioned, validated assessment stored in the latest snapshot."""
    assessment = dossier.get("lead_fit_assessment")
    if not isinstance(assessment, dict):
        return {"scored": False, "priority_score": None, "status": "missing_assessment",
                "reason": "Nincs még kutatási értékelés."}
    status = assessment.get("status")
    if status == "insufficient_evidence":
        return {"scored": False, "priority_score": None, "status": status,
                "reason": "A kutatás nem tartalmaz elegendő forrásolt bizonyítékot a pontozáshoz."}
    fit = assessment.get("fit_score")
    confidence = assessment.get("confidence")
    evidence = assessment.get("evidence")
    try:
        finite_values = (
            not isinstance(fit, bool) and isinstance(fit, (int, float)) and math.isfinite(float(fit))
            and not isinstance(confidence, bool) and isinstance(confidence, (int, float))
            and math.isfinite(float(confidence))
        )
    except (OverflowError, TypeError, ValueError):
        finite_values = False
    valid_evidence = [
        item for item in evidence if isinstance(item, dict)
        and isinstance(item.get("claim"), str) and item.get("claim").strip()
        and _safe_source_url(item.get("source_url"))
    ] if isinstance(evidence, list) else []
    if (
        assessment.get("assessment_version") != "1.0"
        or status != "assessed" or not finite_values
        or not 0 <= float(fit) <= 100 or not 0 <= float(confidence) <= 1
        or not valid_evidence
    ):
        return {"scored": False, "priority_score": None, "status": "invalid_assessment",
                "reason": "A mentett kutatási értékelés hiányos vagy érvénytelen; pontszám nem készült."}
    evidence_points = min(100, len(valid_evidence) * 25)
    priority = round(0.60 * float(fit) + 0.25 * (float(confidence) * 100) + 0.15 * evidence_points)
    return {
        "scored": True, "priority_score": priority, "status": "assessed",
        "business_fit_score": float(fit), "research_confidence": float(confidence),
        "evidence_count": len(valid_evidence),
        "reason": f"Üzleti illeszkedés {fit}/100 · bizonyosság {confidence:.0%} · forrásolt bizonyíték {len(evidence)}",
        "interpretation": "Kutatási prioritás, nem vásárlási szándék, fizetőképesség vagy kapcsolatfelvételi engedély.",
    }


def _latest_snapshot_dossiers(db: Any) -> dict[str, dict[str, Any]]:
    """Read latest snapshots under the caller's existing user/RLS database session."""
    response = (
        db.table("company_research_snapshots")
        .select("lead_id,researched_at,dossier")
        .order("researched_at", desc=True)
        .order("snapshot_id", desc=True)
        .limit(5000)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    if not isinstance(rows, list):
        raise RuntimeError("Invalid company research snapshot response.")
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        lead_id = str(row.get("lead_id") or "")
        dossier = row.get("dossier")
        if lead_id and lead_id not in latest and isinstance(dossier, dict):
            latest[lead_id] = {**dossier, "_snapshot_researched_at": row.get("researched_at")}
    return latest


def _record_event(
    db: Any,
    *,
    lead_id: str,
    event_type: str,
    note: str | None = None,
    ai_response: str | None = None,
    disposition: str | None = None,
    alternative_saas: str | None = None,
) -> None:
    db.rpc("record_lead_review_event", {
        "p_lead_id": lead_id,
        "p_event_type": event_type,
        "p_note": note,
        "p_ai_response": ai_response,
        "p_disposition": disposition,
        "p_alternative_saas": alternative_saas,
    }).execute()


def _company_context(lead: dict[str, Any], dossier: dict[str, Any]) -> str:
    notes = str(lead.get("notes") or "")
    facts = dossier.get("facts") if isinstance(dossier.get("facts"), list) else []
    fact_lines = [
        f"- {str(item.get('category') or 'Tény')}: {str(item.get('fact') or '')[:500]} (forrás: {str(item.get('source_url') or '')[:500]})"
        for item in facts[:10] if isinstance(item, dict)
    ]
    leader = dossier.get("decision_maker") if isinstance(dossier.get("decision_maker"), dict) else {}
    leader_line = " · ".join(str(leader.get(key) or "") for key in ("name", "role", "professional_background")).strip(" ·")
    return "\n".join([
        f"Cég: {lead.get('company_name') or 'Ismeretlen cég'}",
        f"Weboldal: {lead.get('website') or 'nincs adat'}",
        f"Ország: {extract_country(lead)}",
        f"AI-kutatási összefoglaló: {_note_value(_SUMMARY_PATTERN, notes) or 'nincs mentett összefoglaló'}",
        f"Illeszkedés: {_note_value(_FIT_PATTERN, notes) or 'nincs adat'}",
        f"Üzleti igény: {_note_value(_NEED_PATTERN, notes) or 'nincs adat'}",
        f"Nyilvános döntéshozó: {leader_line or 'nincs forrásolt adat'}",
        "Forrásolt tények:", *(fact_lines or ["- nincs mentett forrásolt tény"]),
    ])[:9000]


def render_lead_review_page(
    db: Any,
    *,
    auth_enabled: bool,
    role: str | None,
    generate_text_fn: Any,
    model_name_fn: Any,
    research_fn: Any = None,
) -> None:
    """Render the ranked lead queue; outbound email is deliberately out of scope."""
    # Page-local styling. The JARVIS sidebar and global application shell are untouched.
    st.markdown(
        """
        <style>
        .main .block-container { max-width:1680px; padding-top:1.8rem; }
        .main h1 { color:#f2f7ff; font-size:2.35rem; font-weight:780; letter-spacing:-.035em; }
        .main [data-testid="stMetric"] {
            background:linear-gradient(145deg,#14243b,#101b2e);
            border:1px solid #2a4261; border-radius:13px; padding:16px 18px;
            box-shadow:0 8px 22px rgba(0,0,0,.16); min-height:104px;
        }
        .main [data-testid="stMetricLabel"] { color:#b8c9df; font-weight:650; }
        .main [data-testid="stMetricValue"] { color:#eaf5ff; font-size:2rem; font-weight:780; }
        .main [data-testid="stAlert"] { border:1px solid #28547b; border-radius:10px; }
        .main [data-testid="stTabs"] [role="tab"] { font-weight:650; padding:12px 17px; }
        .main [data-testid="stTabs"] [aria-selected="true"] { color:#50d9ff; }
        .main [data-testid="stVerticalBlockBorderWrapper"] {
            border-color:#2b405b !important; border-radius:13px !important;
            background:linear-gradient(145deg,rgba(20,35,57,.94),rgba(12,23,39,.96));
            box-shadow:0 7px 20px rgba(0,0,0,.13);
        }
        .main div[data-testid="stExpander"] details {
            border:1px solid #2b4564; border-radius:10px; background:#0d192b;
        }
        .main div[data-testid="stTextInput"] input,
        .main div[data-testid="stTextArea"] textarea,
        .main div[data-baseweb="select"] > div {
            background:#101f34 !important; border-color:#315273 !important; color:#edf5ff !important;
        }
        .main div.stButton > button, .main div[data-testid="stFormSubmitButton"] > button {
            border-radius:9px !important; font-weight:700 !important; min-height:2.65rem;
        }
        .main hr { border-color:#263c58; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("Leadkezelő")
    st.caption(
        "A 0–100 pontos kutatási prioritás kizárólag a legfrissebb, forrásolt snapshot strukturált értékeléséből "
        "készül; hiányzó vagy elégtelen bizonyíték esetén a lead pontozatlan marad. "
        "A pontszám kutatási triázs, nem vásárlási szándék vagy kapcsolatfelvételi engedély."
    )
    can_decide = auth_enabled and str(role or "") in {"admin", "operator"}
    if not auth_enabled:
        st.info("A leadek megtekinthetők, de döntést csak egyéni Supabase Auth + RBAC munkamenetben lehet rögzíteni.")
    elif not can_decide:
        st.info("Olvasási jogosultságod van. Jóváhagyást és elutasítást admin vagy operator rögzíthet.")

    try:
        leads = _load_rows(
            db, "leads",
            "id,company_name,website,status,notes,source,research_evidence,approved_to_contact,opted_out,consent_basis,consent_confirmed_at",
        )
    except Exception as exc:
        st.error("A leadlista nem érhető el; az adatforráshibát nem tekintem üres listának.")
        st.caption(f"Hibatípus: {type(exc).__name__}")
        return
    if not leads:
        st.info("Még nincs megjeleníthető lead.")
        return

    try:
        states = _load_rows(db, "lead_review_states", "lead_id,review_status,rejection_note,disposition,alternative_saas,updated_at", 1500)
        events = _load_rows(db, "lead_review_events", "id,lead_id,event_type,note,ai_response,disposition,alternative_saas,created_at", 3000)
    except Exception as exc:
        states, events = [], []
        st.warning(
            "A döntési előzmények táblái még nem olvashatók. A leadek megjelennek, "
            "de a döntési folyamat a 20261127160000_lead_review_workflow.sql migrációig nem használható."
        )
        st.caption(f"Hibatípus: {type(exc).__name__}")

    snapshot_error: str | None = None
    try:
        dossier_by_lead = _latest_snapshot_dossiers(db)
    except Exception as exc:
        dossier_by_lead = {}
        snapshot_error = type(exc).__name__
        st.warning("A kutatási értékelések most nem olvashatók. Ez adatforrás-hiba, nem üres kutatási eredmény; pontszámot nem jelenítünk meg.")
        st.caption(f"Hibatípus: {snapshot_error}")

    state_by_lead = {str(row.get("lead_id")): row for row in states if row.get("lead_id")}
    event_by_lead: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        event_by_lead.setdefault(str(event.get("lead_id") or ""), []).append(event)

    ranked: list[dict[str, Any]] = []
    for lead in leads:
        if not lead.get("id"):
            continue
        dossier = dossier_by_lead.get(str(lead["id"]), {})
        score = (
            {"scored": False, "priority_score": None, "status": "snapshot_unavailable",
             "reason": "A kutatási pillanatkép nem olvasható."}
            if snapshot_error else
            _score_snapshot_assessment(dossier) if dossier else
            {"scored": False, "priority_score": None, "status": "research_required",
             "reason": "Kutatás szükséges – még nincs mentett kutatási pillanatkép."}
        )
        state = state_by_lead.get(str(lead["id"]), {})
        ranked.append({
            **lead,
            "_score": score,
            "_review_status": str(state.get("review_status") or "pending"),
            "_review_state": state,
            "_dossier": dossier,
        })
    ranked.sort(
        key=lambda row: (
            row["_score"].get("priority_score") is not None,
            row["_score"].get("priority_score") if row["_score"].get("priority_score") is not None else -1,
            str(row.get("company_name") or "").casefold(),
        ),
        reverse=True,
    )

    pending = [row for row in ranked if row["_review_status"] == "pending"]
    approved = [row for row in ranked if row["_review_status"] == "approved"]
    rejected = [row for row in ranked if row["_review_status"] == "rejected"]
    metrics = st.columns(5)
    metrics[0].metric("Összes lead", len(ranked))
    metrics[1].metric("Jóváhagyásra vár", len(pending))
    metrics[2].metric("Jóváhagyott", len(approved))
    metrics[3].metric("Elutasított", len(rejected))
    metrics[4].metric("Pontozott", sum(1 for row in ranked if row["_score"].get("priority_score") is not None))

    search_col, hint_col = st.columns([2.2, 1])
    with search_col:
        lead_search = st.text_input(
            "Keresés cégnév vagy weboldal alapján",
            placeholder="Kezdj el gépelni egy cégnevet…",
            key="lead_review_search",
            label_visibility="collapsed",
        ).strip().casefold()
    with hint_col:
        st.caption("A rangsor kizárólag a legfrissebb, forrásolt kutatási snapshot értékeléséből készül.")

    if lead_search:
        def matches_search(row: dict[str, Any]) -> bool:
            return lead_search in str(row.get("company_name") or "").casefold() or lead_search in str(row.get("website") or "").casefold()
        pending = [row for row in pending if matches_search(row)]
        approved = [row for row in approved if matches_search(row)]
        rejected = [row for row in rejected if matches_search(row)]

    status_filter = st.selectbox(
        "Státusz szűrése",
        options=["Összes", "Jóváhagyásra vár", "Jóváhagyott", "Elutasított"],
        key="lead_review_status_filter",
    )
    sort_order = st.selectbox(
        "Rendezés",
        options=["Kutatási prioritás szerint", "Cégnév szerint"],
        key="lead_review_sort_order",
    )
    filtered_rows = [
        row for row in ranked
        if (
            not lead_search
            or lead_search in str(row.get("company_name") or "").casefold()
            or lead_search in str(row.get("website") or "").casefold()
        )
        and (status_filter == "Összes"
        or (status_filter == "Jóváhagyásra vár" and row["_review_status"] == "pending")
        or (status_filter == "Jóváhagyott" and row["_review_status"] == "approved")
        or (status_filter == "Elutasított" and row["_review_status"] == "rejected"))
    ]
    if sort_order == "Cégnév szerint":
        filtered_rows.sort(key=lambda row: str(row.get("company_name") or "").casefold())
    if not filtered_rows:
        st.info("A keresési és státuszfeltételeknek megfelelő lead nem található.")
        return
    selected_id = str(st.session_state.get("lead_review_selected_id") or "")
    if not any(str(row["id"]) == selected_id for row in filtered_rows):
        selected_id = str(filtered_rows[0]["id"])
        st.session_state["lead_review_selected_id"] = selected_id
    list_col, detail_col = st.columns([1.08, 1.72], gap="large")

    def render_card(lead: dict[str, Any], index: int, section: str) -> None:
        lead_id = str(lead["id"])
        name = str(lead.get("company_name") or "Névtelen cég")
        score = lead["_score"]
        points = score.get("priority_score")
        country = extract_country(lead)
        flag = country_flag(country)
        state = lead["_review_state"]
        dossier = lead["_dossier"]
        notes = str(lead.get("notes") or "")
        with st.container(border=True):
            left, middle, right = st.columns([5, 1.25, 2.6])
            with left:
                st.markdown(f"**{index}. {name}**")
                st.caption(f"{flag} · {lead.get('website') or 'Nincs weboldal'}")
            with middle:
                st.metric("Lead score", f"{points}/100" if points is not None else "—")
            with right:
                if section == "pending" and can_decide:
                    if st.button("✓ Elfogadom", key=f"lead_approve_{lead_id}", width="stretch"):
                        try:
                            _record_event(db, lead_id=lead_id, event_type="approved")
                            st.success("A lead jóváhagyva.")
                            st.rerun()
                        except Exception as exc:
                            st.error("A jóváhagyást nem sikerült rögzíteni.")
                            st.caption(f"Hibatípus: {type(exc).__name__}")
                    if st.button("✕ Elutasítom", key=f"lead_reject_open_{lead_id}", width="stretch"):
                        st.session_state["lead_review_active_reject"] = lead_id
                        st.rerun()
                elif section == "pending":
                    st.caption("Jóváhagyásra vár")
                elif section == "approved":
                    st.caption("Jóváhagyva")
                elif section == "rejected":
                    st.caption("Elutasítva")
            if can_decide and callable(research_fn):
                st.markdown("**Forrásolt cégkutatás**")
                st.caption(
                    "A kérés a háttérsorba kerül. Ez a művelet nem indít azonnali worker-futtatást "
                    "és nem kezdeményez kapcsolatfelvételt."
                )
                if st.button("Kutatás kérése", key=f"lead_research_enqueue_{lead_id}", type="secondary"):
                    try:
                        with st.spinner("A kutatási kérés biztonságos rögzítése…"):
                            research_result = research_fn(lead_id)
                        if research_result.get("status") in {"queued", "running", "retry_wait"}:
                            st.success("A kutatási kérés a háttérsorban van.")
                            st.caption(
                                f"Állapot: {research_result.get('status')} · "
                                f"Azonosító: {research_result.get('operation_id') or '—'}"
                            )
                        elif research_result.get("status") == "not_eligible":
                            st.info(
                                "A lead most nem kerülhet a kutatási sorba. Ellenőrizd a weboldalt, "
                                "a kapcsolatfelvételi/opt-out állapotot és a kutatási pillanatkép korát."
                            )
                        else:
                            st.warning("A kutatási kérés állapota nem egyértelmű; ellenőrizd a kutatási sort.")
                    except Exception as exc:
                        st.error("A kutatási kérés nem került a háttérsorba.")
                        st.caption(f"Hibatípus: {type(exc).__name__}")

            with st.expander(
                "Részletek, források és döntés",
                expanded=True,
            ):
                details_left, details_right = st.columns(2)
                with details_left:
                    st.markdown("**AI-kutatási összefoglaló**")
                    st.write(_note_value(_SUMMARY_PATTERN, notes) or "Nincs mentett cégösszefoglaló.")
                    st.markdown("**Kutatási értékelés**")
                    st.write(score.get("reason") or "Nincs még kutatási értékelés.")
                    assessment = dossier.get("lead_fit_assessment") if isinstance(dossier.get("lead_fit_assessment"), dict) else {}
                    if assessment.get("rationale"):
                        st.write(assessment["rationale"])
                    if assessment.get("recommended_next_step"):
                        st.caption(f"Következő kutatási lépés: {assessment['recommended_next_step']}")
                    if assessment.get("fit_signals"):
                        st.markdown("**Illeszkedési jelek**")
                        for signal in assessment["fit_signals"][:12]:
                            st.write(f"• {signal}")
                    if assessment.get("risk_signals"):
                        st.markdown("**Kockázati jelek**")
                        for signal in assessment["risk_signals"][:12]:
                            st.write(f"• {signal}")
                with details_right:
                    st.markdown("**Nyilvános vezető / CEO**")
                    leader = dossier.get("decision_maker") if isinstance(dossier.get("decision_maker"), dict) else {}
                    leader_name = " · ".join(str(leader.get(key) or "") for key in ("name", "role")).strip(" ·")
                    st.write(leader_name or "Nincs forrásolt vezetői adat.")
                    if leader.get("professional_background"):
                        st.write(str(leader["professional_background"]))
                    leader_url = _safe_source_url(leader.get("source_url"))
                    if leader_url:
                        st.markdown(f"[Vezetői forrás]({leader_url})")
                    st.markdown("**Kutatási bizonyosság**")
                    if score.get("research_confidence") is not None:
                        st.metric("Bizonyosság", f"{score['research_confidence']:.0%}")
                    if score.get("interpretation"):
                        st.caption(score["interpretation"])
                    if dossier.get("_snapshot_researched_at"):
                        st.caption(f"Legutóbbi kutatás: {dossier['_snapshot_researched_at']}")
                facts = dossier.get("facts") if isinstance(dossier.get("facts"), list) else []
                if facts:
                    st.markdown("**Forrásolt céginformációk**")
                    for fact in facts[:12]:
                        if not isinstance(fact, dict):
                            continue
                        st.write(f"**{fact.get('category') or 'Tény'}:** {fact.get('fact') or ''}")
                        source_url = _safe_source_url(fact.get("source_url"))
                        if source_url:
                            st.markdown(f"[Forrás megnyitása]({source_url})")
                source_url = _safe_source_url(re.search(r"Forrás:\s*(https?://\S+)", notes).group(1) if re.search(r"Forrás:\s*(https?://\S+)", notes) else None)
                if source_url:
                    st.markdown(f"[Kutatási forrás]({source_url})")
                assessment = dossier.get("lead_fit_assessment") if isinstance(dossier.get("lead_fit_assessment"), dict) else {}
                evidence = assessment.get("evidence") if isinstance(assessment.get("evidence"), list) else []
                if evidence:
                    st.markdown("**Az értékelés forrásai**")
                    for item in evidence[:20]:
                        if not isinstance(item, dict):
                            continue
                        kind = item.get("evidence_type")
                        kind_label = {"fact": "Forrásolt tény", "hypothesis": "Hipotézis", "assessment": "AI-értékelés"}.get(kind, "Bizonyíték")
                        st.write(f"**{kind_label}:** {item.get('claim') or ''}")
                        evidence_url = _safe_source_url(item.get("source_url"))
                        if evidence_url:
                            st.markdown(f"[Forrás megnyitása]({evidence_url})")
                        if item.get("title"):
                            st.caption(str(item["title"])[:300])
                pains = dossier.get("pain_hypotheses") if isinstance(dossier.get("pain_hypotheses"), list) else []
                if pains:
                    st.markdown("**Lehetséges üzleti problémák – hipotézisek, nem bizonyított tények**")
                    for pain in pains[:10]:
                        if isinstance(pain, dict):
                            st.write(f"• {pain.get('statement') or ''}")
                            pain_evidence = pain.get("evidence") if isinstance(pain.get("evidence"), list) else []
                            for proof in pain_evidence[:3]:
                                if isinstance(proof, dict):
                                    pain_url = _safe_source_url(proof.get("source_url"))
                                    if pain_url:
                                        st.markdown(f"[Hipotézis forrása]({pain_url})")

                if section == "pending" and can_decide:
                    st.divider()
                    if st.button("✓ Jóváhagyás", key=f"lead_approve_detail_{lead_id}", width="stretch"):
                        try:
                            _record_event(db, lead_id=lead_id, event_type="approved")
                            st.success("A lead jóváhagyva.")
                            st.rerun()
                        except Exception as exc:
                            st.error("A jóváhagyást nem sikerült rögzíteni.")
                            st.caption(f"Hibatípus: {type(exc).__name__}")
                    with st.form(f"lead_reject_form_{lead_id}"):
                        rejection_note = st.text_area(
                            "Miért utasítod el? (kötelező megjegyzés)",
                            value=str(state.get("rejection_note") or ""),
                            max_chars=2000,
                            key=f"lead_reject_note_{lead_id}",
                        )
                        reject_submitted = st.form_submit_button("Elutasítás mentése")
                    if reject_submitted:
                        try:
                            _record_event(db, lead_id=lead_id, event_type="rejected", note=rejection_note.strip())
                            st.session_state.pop("lead_review_active_reject", None)
                            st.success("A lead az elutasítottak közé került.")
                            st.rerun()
                        except Exception as exc:
                            st.error("Az elutasítást nem sikerült rögzíteni. Legalább 5 karakteres indoklás szükséges.")
                            st.caption(f"Hibatípus: {type(exc).__name__}")

                if section == "rejected":
                    st.divider()
                    st.markdown("**Elutasítási megjegyzés**")
                    st.write(state.get("rejection_note") or "Nincs megjegyzés.")
                    if can_decide:
                        with st.form(f"lead_ai_discussion_form_{lead_id}"):
                            discussion_note = st.text_area(
                                "Mit szeretnél megvitatni a JARVIS-szal?",
                                max_chars=2000,
                                key=f"lead_ai_discussion_{lead_id}",
                            )
                            discuss_submitted = st.form_submit_button("Megvitatás az AI-val")
                        if discuss_submitted:
                            if len(discussion_note.strip()) < 5:
                                st.warning("Írj legalább 5 karakteres megjegyzést a megbeszéléshez.")
                            else:
                                prompt = (
                                    "Te egy óvatos B2B SaaS üzleti elemző vagy. A felhasználó egy elutasított leadről "
                                    "szeretne dönteni. Ne találj ki tényeket, különítsd el a bizonyítékot a hipotézistől. "
                                    "Értékeld a megtartás, másik SaaS ajánlása vagy várakozás lehetőségét. "
                                    "Ne küldj e-mailt és ne változtass státuszt.\n\n"
                                    + _company_context(lead, dossier)
                                    + "\n\nElutasítás oka: " + str(state.get("rejection_note") or "")
                                    + "\n\nFelhasználói megjegyzés: " + discussion_note.strip()
                                )
                                try:
                                    with st.spinner("A JARVIS átgondolja a megjegyzést…"):
                                        ai_response = str(generate_text_fn(prompt, max_output_tokens=1400)).strip()[:8000]
                                    if not ai_response:
                                        raise RuntimeError("Az AI nem adott értékelhető választ.")
                                    _record_event(
                                        db, lead_id=lead_id, event_type="discussion",
                                        note=discussion_note.strip(), ai_response=ai_response,
                                    )
                                    st.success("Az AI-válasz elmentve a lead döntési előzményeihez.")
                                    st.rerun()
                                except Exception as exc:
                                    st.error("Az AI-megbeszélés nem sikerült vagy nem menthető.")
                                    st.caption(f"Hibatípus: {type(exc).__name__}")
                        history = sorted(event_by_lead.get(lead_id, []), key=lambda item: str(item.get("created_at") or ""))
                        for event in history[-6:]:
                            if event.get("event_type") == "discussion":
                                st.markdown("**Megjegyzés**")
                                st.write(event.get("note") or "")
                                st.markdown("**JARVIS válasza**")
                                st.write(event.get("ai_response") or "")
                        with st.form(f"lead_disposition_form_{lead_id}"):
                            disposition = st.selectbox(
                                "Végső döntés",
                                options=["keep", "recommend_alternative", "wait"],
                                format_func=lambda value: {
                                    "keep": "Maradjon a listán",
                                    "recommend_alternative": "Másik SaaS-terméket ajánljunk",
                                    "wait": "Várjunk vele",
                                }[value],
                                key=f"lead_disposition_{lead_id}",
                            )
                            alternative = st.text_input(
                                "Milyen másik SaaS-terméket ajánljunk? (ha releváns)",
                                key=f"lead_alternative_{lead_id}",
                            )
                            disposition_submitted = st.form_submit_button("Döntés mentése")
                        if disposition_submitted:
                            try:
                                _record_event(
                                    db, lead_id=lead_id, event_type="disposition",
                                    disposition=disposition,
                                    alternative_saas=alternative.strip() or None,
                                )
                                st.success("A döntés elmentve.")
                                st.rerun()
                            except Exception as exc:
                                st.error("A döntést nem sikerült menteni. Alternatív terméknél add meg a termékötletet.")
                                st.caption(f"Hibatípus: {type(exc).__name__}")
                        if state.get("disposition"):
                            labels = {"keep": "Maradjon a listán", "recommend_alternative": "Másik SaaS-termék", "wait": "Várakozás"}
                            st.info(f"Legutóbbi döntés: {labels.get(state['disposition'], state['disposition'])}")
                            if state.get("alternative_saas"):
                                st.write(state["alternative_saas"])
                        if st.button("Vissza a jóváhagyásra várók közé", key=f"lead_restore_{lead_id}"):
                            try:
                                _record_event(db, lead_id=lead_id, event_type="approved")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"A státusz nem módosítható ({type(exc).__name__}).")

                if section == "approved":
                    contact_ready = bool(
                        lead.get("approved_to_contact")
                        and lead.get("consent_confirmed_at")
                        and not lead.get("opted_out")
                    )
                    st.caption(
                        "Kapcsolatfelvételi hozzájárulás: igazolt" if contact_ready
                        else "Kapcsolatfelvételi hozzájárulás: nincs igazolva; e-mail nem küldhető."
                    )
                    st.caption(
                        "Ez a jóváhagyott leadek előkészítési sora. A jóváhagyás nem állítja be "
                        "a hozzájárulást és nem indít e-mail-küldést."
                    )
                    if can_decide and st.button("Vissza a várakozók közé", key=f"lead_unapprove_{lead_id}"):
                        try:
                            _record_event(db, lead_id=lead_id, event_type="rejected", note="Visszavonva a jóváhagyás; újraértékelés szükséges.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"A jóváhagyás visszavonása nem sikerült ({type(exc).__name__}).")

                if can_decide:
                    st.markdown("**AI SaaS-termékjavaslat**")
                    if st.button("Javaslat generálása", key=f"lead_saas_suggest_{lead_id}"):
                        prompt = (
                            "Készíts egyetlen konkrét, újraértékesíthető B2B SaaS termékjavaslatot a cég számára. "
                            "Csak a megadott forrásolt tényekből indulj ki; a következtetéseket hipotézisként jelöld. "
                            "Add meg a problémát, célfelhasználót, MVP 3 fő funkcióját, üzleti értéket, "
                            "és azt, miért lehet más cégeknek is eladható. Ne írj kapcsolatfelvételi e-mailt.\n\n"
                            + _company_context(lead, dossier)
                        )
                        try:
                            with st.spinner("SaaS-javaslat készül…"):
                                suggestion = str(generate_text_fn(prompt, max_output_tokens=1200)).strip()
                            st.session_state[f"lead_saas_suggestion_{lead_id}"] = suggestion[:7000]
                        except Exception as exc:
                            st.error(f"A SaaS-javaslat nem készült el ({type(exc).__name__}).")
                        suggestion = st.session_state.get(f"lead_saas_suggestion_{lead_id}")
                        if suggestion:
                            st.write(suggestion)

    with list_col:
        st.markdown("### Leadlista")
        st.caption(f"{len(filtered_rows)} megjelenített vállalat · pontozott leadek előre sorolva")
        for index, row in enumerate(filtered_rows, start=1):
            row_id = str(row["id"])
            row_name = str(row.get("company_name") or "Névtelen cég")
            row_score = row["_score"].get("priority_score")
            row_status = {
                "pending": "Jóváhagyásra vár",
                "approved": "Jóváhagyott",
                "rejected": "Elutasított",
            }.get(row["_review_status"], row["_review_status"])
            selected = row_id == selected_id
            with st.container(border=True):
                if st.button(
                    f"{'▸ ' if selected else ''}{row_name}",
                    key=f"lead_select_{row_id}",
                    width="stretch",
                    type="primary" if selected else "secondary",
                ):
                    st.session_state["lead_review_selected_id"] = row_id
                    st.rerun()
                score_label = f"{row_score}/100" if row_score is not None else (
                    "Kutatási adatok nem elérhetők" if row["_score"].get("status") == "snapshot_unavailable"
                    else "Kutatás szükséges" if row["_score"].get("status") == "research_required"
                    else "Nincs még kutatási értékelés"
                )
                st.caption(
                    f"{country_flag(extract_country(row))}  ·  "
                    f"{row.get('website') or 'Nincs weboldal megadva'}  ·  "
                    f"{score_label}  ·  {row_status}"
                )
                assessment = row["_dossier"].get("lead_fit_assessment") if isinstance(row["_dossier"].get("lead_fit_assessment"), dict) else {}
                if row["_score"].get("research_confidence") is not None:
                    st.caption(
                        f"Bizonyosság: {row['_score']['research_confidence']:.0%} · "
                        f"Források: {row['_score'].get('evidence_count', 0)}"
                    )
                st.caption(str(assessment.get("rationale") or row["_score"].get("reason") or "Nincs még kutatási értékelés.")[:220])
                compact_signals = []
                if assessment.get("fit_signals"):
                    compact_signals.append("Illeszkedés: " + "; ".join(str(x) for x in assessment["fit_signals"][:2]))
                if assessment.get("risk_signals"):
                    compact_signals.append("Kockázat: " + "; ".join(str(x) for x in assessment["risk_signals"][:2]))
                if compact_signals:
                    st.caption(" · ".join(compact_signals)[:260])
                if row_score is None:
                    st.caption(row["_score"].get("reason") or "A pontozáshoz még nincs elegendő forrásolt értékelés.")
    with detail_col:
        selected_row = next((row for row in filtered_rows if str(row["id"]) == selected_id), None)
        if selected_row:
            st.markdown("### Kiválasztott vállalat")
            section = selected_row["_review_status"]
            render_card(selected_row, filtered_rows.index(selected_row) + 1, section)


    st.caption(
        f"A rangsor {len(ranked)} leadből készült. A pontozatlan rekordok a pontozottak után jelennek meg. "
        f"Az AI-modell: {str(model_name_fn())[:120]}. E-mail-küldés ezen az oldalon nem történik."
    )
