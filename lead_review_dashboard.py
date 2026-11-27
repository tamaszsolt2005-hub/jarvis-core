"""Lead review workspace with evidence-aware ranking and human-only decisions."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from intelligent_lead_scoring import score_researched_lead


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
    if parsed.hostname.casefold() == "localhost" or parsed.hostname.casefold().endswith((".localhost", ".local")):
        return None
    return raw[:2048]


def _load_rows(db: Any, table: str, columns: str, limit: int = 1000) -> list[dict[str, Any]]:
    response = db.table(table).select(columns).limit(limit).execute()
    rows = getattr(response, "data", None) or []
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


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
) -> None:
    """Render the ranked lead queue; outbound email is deliberately out of scope."""
    st.title("Leadkezelő")
    st.caption(
        "A strukturált kutatási adatokkal rendelkező leadek 0–100 pontos kutatási prioritás szerint "
        "jelennek meg; a hiányos kutatási adatokkal rendelkező rekordok pontozatlanok maradnak. "
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

    try:
        snapshots = _load_rows(db, "company_research_snapshots", "lead_id,researched_at,dossier", 1500)
    except Exception:
        snapshots = []
    dossier_by_lead: dict[str, dict[str, Any]] = {}
    for snapshot in sorted(snapshots, key=lambda row: str(row.get("researched_at") or ""), reverse=True):
        lead_id = str(snapshot.get("lead_id") or "")
        if lead_id and lead_id not in dossier_by_lead and isinstance(snapshot.get("dossier"), dict):
            dossier_by_lead[lead_id] = snapshot["dossier"]

    state_by_lead = {str(row.get("lead_id")): row for row in states if row.get("lead_id")}
    event_by_lead: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        event_by_lead.setdefault(str(event.get("lead_id") or ""), []).append(event)

    ranked: list[dict[str, Any]] = []
    for lead in leads:
        if not lead.get("id"):
            continue
        scoring_input = dict(lead)
        if not scoring_input.get("research_intelligence"):
            scoring_input["research_intelligence"] = scoring_input.get("notes") or ""
        score = score_researched_lead(scoring_input)
        state = state_by_lead.get(str(lead["id"]), {})
        ranked.append({
            **lead,
            "_score": score,
            "_review_status": str(state.get("review_status") or "pending"),
            "_review_state": state,
            "_dossier": dossier_by_lead.get(str(lead["id"]), {}),
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
    metrics = st.columns(4)
    metrics[0].metric("Összes lead", len(ranked))
    metrics[1].metric("Jóváhagyásra vár", len(pending))
    metrics[2].metric("Jóváhagyott", len(approved))
    metrics[3].metric("Elutasított", len(rejected))
    pending_tab, approved_tab, rejected_tab = st.tabs([
        f"Várakozó ({len(pending)})",
        f"Jóváhagyott / e-mail előkészítés ({len(approved)})",
        f"Elutasított ({len(rejected)})",
    ])

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
            with st.expander(
                "⌄ Cégadatok, AI-összefoglaló és döntés",
                expanded=st.session_state.get("lead_review_active_reject") == lead_id,
            ):
                details_left, details_right = st.columns(2)
                with details_left:
                    st.markdown("**AI-kutatási összefoglaló**")
                    st.write(_note_value(_SUMMARY_PATTERN, notes) or "Nincs mentett cégösszefoglaló.")
                    st.markdown("**Üzleti illeszkedés**")
                    st.write(_note_value(_FIT_PATTERN, notes) or "Nincs mentett illeszkedési javaslat.")
                    st.markdown("**Megfigyelhető üzleti igény**")
                    st.write(_note_value(_NEED_PATTERN, notes) or "Nincs rögzített üzleti igény.")
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
                    st.markdown("**Kutatási bizonyosság és indoklás**")
                    st.write(score.get("reason") or "Nem számítható pontszám.")
                    if score.get("interpretation"):
                        st.caption(score["interpretation"])
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
                if lead.get("research_evidence"):
                    st.caption(f"Forrásolt bizonyítékok: {len(lead['research_evidence']) if isinstance(lead['research_evidence'], list) else 'elérhető'}")

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

    with pending_tab:
        if not pending:
            st.info("Nincs jóváhagyásra váró lead.")
        for index, lead in enumerate(pending, start=1):
            render_card(lead, index, "pending")
    with approved_tab:
        if not approved:
            st.info("Még nincs jóváhagyott lead.")
        for index, lead in enumerate(approved, start=1):
            render_card(lead, index, "approved")
    with rejected_tab:
        if not rejected:
            st.info("Még nincs elutasított lead.")
        for index, lead in enumerate(rejected, start=1):
            render_card(lead, index, "rejected")

    st.caption(
        f"A rangsor {len(ranked)} leadből készült. A pontozatlan rekordok a pontozottak után jelennek meg. "
        f"Az AI-modell: {str(model_name_fn())[:120]}. E-mail-küldés ezen az oldalon nem történik."
    )
