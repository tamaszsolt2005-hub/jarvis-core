"""Human-controlled CRM lifecycle for approved leads; no outbound delivery."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import streamlit as st


_STAGES = {
    "approved_lead": "Jóváhagyott lead",
    "contacted": "Kapcsolatfelvétel megtörtént",
    "responded": "Válaszolt",
    "qualified": "Minősített érdeklődő",
    "proposal": "Ajánlat előkészítése / elküldve",
    "pilot": "Pilot",
    "customer": "Ügyfél",
    "lost": "Lezárt / elvesztett",
}
_CHANNELS = {
    "email": "E-mail (kézzel rögzített)",
    "phone": "Telefon",
    "meeting": "Megbeszélés",
    "note": "Belső megjegyzés",
    "other": "Egyéb",
}


def _rows(db: Any, table: str, columns: str, limit: int = 1500) -> list[dict[str, Any]]:
    response = db.table(table).select(columns).limit(limit).execute()
    rows = getattr(response, "data", None)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise RuntimeError(f"Unexpected {table} response.")
    return rows


def _record(db: Any, **payload: Any) -> None:
    db.rpc("record_lead_customer_lifecycle_event", payload).execute()


def _is_overdue(state: dict[str, Any], *, today: date | None = None) -> bool:
    """Return true only for actionable follow-ups whose due date is in the past."""
    if not isinstance(state, dict) or not str(state.get("next_action") or "").strip():
        return False
    due_value = state.get("next_action_due")
    if not due_value:
        return False
    try:
        if isinstance(due_value, datetime):
            due = due_value.date()
        elif isinstance(due_value, date):
            due = due_value
        else:
            due = date.fromisoformat(str(due_value)[:10])
    except (TypeError, ValueError):
        return False
    reference_day = today or datetime.now(ZoneInfo("Europe/Budapest")).date()
    return due < reference_day


def _matches_owner_filter(state: dict[str, Any], selected_owner: str) -> bool:
    """Match the CRM owner selector without treating missing state as an assigned owner."""
    if selected_owner == "all":
        return True
    assigned_to = str((state or {}).get("assigned_to") or "")
    if selected_owner == "unassigned":
        return not assigned_to
    return assigned_to == selected_owner


def _build_crm_conversion_funnel(
    approved_lead_ids: set[str] | list[str],
    lifecycle_rows: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build a deduplicated, history-aware funnel for approved leads only."""
    stages = (
        ("approved_lead", "Jóváhagyott"),
        ("contacted", "Kapcsolatfelvétel"),
        ("responded", "Válaszolt"),
        ("qualified", "Minősített"),
        ("proposal", "Ajánlat"),
        ("pilot", "Pilot"),
        ("customer", "Ügyfél"),
    )
    stage_rank = {stage: index for index, (stage, _label) in enumerate(stages)}
    approved = {str(lead_id) for lead_id in approved_lead_ids if lead_id}
    max_rank = {lead_id: 0 for lead_id in approved}
    lost_ids: set[str] = set()

    for row in lifecycle_rows:
        lead_id = str(row.get("lead_id") or "")
        if lead_id not in approved:
            continue
        stage = str(row.get("stage") or "approved_lead")
        if stage == "lost":
            lost_ids.add(lead_id)
        elif stage in stage_rank:
            max_rank[lead_id] = max(max_rank[lead_id], stage_rank[stage])

    for event in events:
        lead_id = str(event.get("lead_id") or "")
        if lead_id not in approved:
            continue
        if event.get("event_type") == "inbound_reply_recorded":
            max_rank[lead_id] = max(max_rank[lead_id], stage_rank["responded"])
        for field in ("from_stage", "to_stage"):
            stage = str(event.get(field) or "")
            if stage == "lost":
                lost_ids.add(lead_id)
            elif stage in stage_rank:
                max_rank[lead_id] = max(max_rank[lead_id], stage_rank[stage])

    previous_count = len(approved)
    rows: list[dict[str, Any]] = []
    for index, (stage, label) in enumerate(stages):
        reached = sum(1 for rank in max_rank.values() if rank >= index)
        rows.append({
            "Szakasz": label,
            "Elért leadek": reached,
            "Konverzió az elfogadott leadekből (%)": round(reached / len(approved) * 100, 1) if approved else 0.0,
            "Konverzió az előző szakaszból (%)": round(reached / previous_count * 100, 1) if previous_count else 0.0,
        })
        previous_count = reached
    rows.append({
        "Szakasz": "Elvesztett",
        "Elért leadek": len(lost_ids),
        "Konverzió az elfogadott leadekből (%)": round(len(lost_ids) / len(approved) * 100, 1) if approved else 0.0,
        "Konverzió az előző szakaszból (%)": 0.0,
    })
    return rows


def _parse_due_date(value: str) -> str | None:
    if not value.strip():
        return None
    normalized = value.strip()
    if len(normalized) != 10 or normalized[4:5] != "-" or normalized[7:8] != "-":
        raise ValueError("A határidő formátuma YYYY-MM-DD legyen.")
    try:
        return date.fromisoformat(normalized).isoformat()
    except ValueError as exc:
        raise ValueError("A határidő formátuma YYYY-MM-DD legyen.") from exc


def render_lead_customer_page(db: Any, *, auth_enabled: bool, role: str | None) -> None:
    """Render a read-first CRM pipeline with explicit authenticated event writes."""
    st.title("Ügyfélkapcsolatok")
    st.caption(
        "A jóváhagyott leadek ügyfél-életciklusát és kézzel rögzített interakcióit követi. "
        "Egyetlen művelet sem küld e-mailt vagy automatikus választ."
    )
    can_manage = auth_enabled and str(role or "") in {"admin", "operator"}
    if not auth_enabled:
        st.info("A CRM megtekinthető, de módosítani csak egyéni Supabase Auth + RBAC munkamenetben lehet.")
    elif not can_manage:
        st.info("Olvasási jogosultságod van. CRM-eseményt admin vagy operator rögzíthet.")

    try:
        leads = _rows(db, "leads", "id,company_name,website")
        review_states = _rows(db, "lead_review_states", "lead_id,review_status")
        lifecycle_rows = _rows(
            db, "lead_customer_lifecycle",
            "lead_id,stage,next_action,next_action_due,last_interaction_at,updated_at,assigned_to",
        )
        events = _rows(
            db, "lead_customer_lifecycle_events",
            "id,lead_id,event_type,from_stage,to_stage,channel,summary,next_action,next_action_due,actor_id,assigned_to_user_id,created_at",
            3000,
        )
    except Exception as exc:
        st.error("A CRM-adatok nem érhetők el. Ellenőrizd a migrációt és az RLS-jogosultságokat.")
        st.caption(f"Hibatípus: {type(exc).__name__}")
        return

    approved_ids = {
        str(row.get("lead_id"))
        for row in review_states
        if row.get("lead_id") and row.get("review_status") == "approved"
    }
    approved_leads = [
        row for row in leads
        if row.get("id") and str(row.get("id")) in approved_ids
    ]
    state_by_lead = {
        str(row.get("lead_id")): row for row in lifecycle_rows if row.get("lead_id")
    }
    events_by_lead: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        lead_id = str(event.get("lead_id") or "")
        if lead_id:
            events_by_lead.setdefault(lead_id, []).append(event)

    if not approved_leads:
        st.info("Még nincs jóváhagyott lead az ügyfélkapcsolati folyamatban.")
        return

    assignable_users: list[dict[str, Any]] = []
    if can_manage:
        try:
            response = db.rpc("list_crm_assignable_users", {}).execute()
            assignable_users = getattr(response, "data", None)
            if not isinstance(assignable_users, list):
                raise RuntimeError("Unexpected CRM user directory response.")
        except Exception as exc:
            st.warning("A felelőslista nem érhető el; a CRM többi funkciója tovább használható.")
            st.caption("Hibatípus: " + type(exc).__name__)

    assignable_user_by_id = {
        str(user.get("user_id")): user
        for user in assignable_users
        if user.get("user_id")
    }
    counts = {stage: 0 for stage in _STAGES}
    for lead in approved_leads:
        state = state_by_lead.get(str(lead["id"]), {})
        stage = str(state.get("stage") or "approved_lead")
        counts[stage if stage in counts else "approved_lead"] += 1
    today = datetime.now(ZoneInfo("Europe/Budapest")).date()
    overdue_ids = {
        str(lead["id"])
        for lead in approved_leads
        if _is_overdue(state_by_lead.get(str(lead["id"]), {}), today=today)
    }
    metric_columns = st.columns(5)
    metric_columns[0].metric("Jóváhagyott lead", len(approved_leads))
    metric_columns[1].metric("Lejárt teendő", len(overdue_ids))
    metric_columns[2].metric("Minősített", counts["qualified"])
    metric_columns[3].metric("Ajánlat / pilot", counts["proposal"] + counts["pilot"])
    metric_columns[4].metric("Ügyfél", counts["customer"])

    st.markdown("#### Értékesítési konverziós tölcsér")
    funnel_rows = _build_crm_conversion_funnel(
        {str(lead["id"]) for lead in approved_leads}, lifecycle_rows, events
    )
    st.dataframe(funnel_rows, width="stretch", hide_index=True)
    st.caption(
        "A szakaszokba jutást az aktuális CRM-státusz és az append-only eseménytörténet alapján, "
        "lead-azonosítónként egyszer számolja. Az elvesztett leadek külön kimenetként láthatók."
    )

    stage_filter = st.selectbox(
        "Folyamat szűrése",
        options=["all", "overdue", *_STAGES.keys()],
        format_func=lambda value: (
            "Minden státusz" if value == "all"
            else "Lejárt teendők" if value == "overdue"
            else _STAGES[value]
        ),
        key="lead_customer_stage_filter",
    )
    owner_filter = "all"
    if can_manage and assignable_users:
        owner_options = ["all", "unassigned", *assignable_user_by_id]
        owner_filter = st.selectbox(
            "Felelős szűrése",
            options=owner_options,
            format_func=lambda value: (
                "Minden felelős" if value == "all"
                else "Nincs felelős" if value == "unassigned"
                else str(
                    assignable_user_by_id[value].get("display_name")
                    or assignable_user_by_id[value].get("email")
                    or "Ismeretlen felhasználó"
                ),
            ),
            key="lead_customer_owner_filter",
        )
    ordered = sorted(
        approved_leads,
        key=lambda lead: (
            0 if str(lead["id"]) in overdue_ids else 1,
            str(state_by_lead.get(str(lead["id"]), {}).get("next_action_due") or "9999-12-31"),
            str(lead.get("company_name") or "").casefold(),
        ),
    )
    visible = [
        lead for lead in ordered
        if (
            (
                stage_filter == "all"
                or (stage_filter == "overdue" and str(lead["id"]) in overdue_ids)
                or str(state_by_lead.get(str(lead["id"]), {}).get("stage") or "approved_lead") == stage_filter
            )
            and _matches_owner_filter(state_by_lead.get(str(lead["id"]), {}), owner_filter)
        )
    ]
    if not visible:
        st.info("Ebben a státuszban nincs jóváhagyott lead.")

    for lead in visible:
        lead_id = str(lead["id"])
        name = str(lead.get("company_name") or "Névtelen cég")
        state = state_by_lead.get(lead_id, {})
        stage = str(state.get("stage") or "approved_lead")
        history = sorted(
            events_by_lead.get(lead_id, []),
            key=lambda item: str(item.get("created_at") or ""),
            reverse=True,
        )
        with st.expander(f"{name} · {_STAGES.get(stage, stage)}", expanded=False):
            st.caption(str(lead.get("website") or "Nincs weboldal"))
            assigned_to = str(state.get("assigned_to") or "")
            assigned_user = next(
                (user for user in assignable_users if str(user.get("user_id")) == assigned_to),
                None,
            )
            if assigned_user:
                st.write("**Felelős:** " + str(assigned_user.get("display_name") or assigned_user.get("email")))
            elif assigned_to:
                st.write("**Felelős:** Inaktív vagy már nem hozzárendelhető felhasználó")
            else:
                st.write("**Felelős:** Nincs hozzárendelve")
            st.write(f"**Következő teendő:** {state.get('next_action') or 'Nincs megadva'}")
            if lead_id in overdue_ids:
                st.warning("A következő teendő határideje lejárt.")
            st.caption(
                f"Határidő: {state.get('next_action_due') or '—'} · "
                f"Utolsó interakció: {state.get('last_interaction_at') or '—'}"
            )
            if history:
                st.markdown("**Interakció- és döntési előzmények**")
                for event in history[:8]:
                    label = {
                        "stage_changed": "Státuszváltozás",
                        "interaction_logged": f"Interakció ({_CHANNELS.get(str(event.get('channel') or ''), 'Egyéb')})",
                        "next_action_set": "Következő teendő",
                        "owner_assigned": "Felelős-hozzárendelés",
                        "inbound_reply_recorded": "Beérkező e-mail-válasz",
                    }.get(str(event.get("event_type") or ""), "Esemény")
                    stage_label = _STAGES.get(str(event.get("to_stage") or ""), "")
                    st.write(f"**{label} · {event.get('created_at') or '—'}**")
                    if stage_label:
                        st.caption(f"Új státusz: {stage_label}")
                    if str(event.get("event_type") or "") == "owner_assigned":
                        historical_assignee_id = str(event.get("assigned_to_user_id") or "")
                        historical_assignee = assignable_user_by_id.get(historical_assignee_id)
                        if historical_assignee:
                            assignee_name = str(
                                historical_assignee.get("display_name")
                                or historical_assignee.get("email")
                                or "Ismeretlen felhasználó"
                            )
                            st.caption(f"Felelős az esemény után: {assignee_name}")
                        elif historical_assignee_id:
                            st.caption("A történeti felelős már nem aktív vagy nem hozzárendelhető.")
                        else:
                            st.caption("A felelősség visszavonásra került.")
                    st.write(str(event.get("summary") or ""))
                    if event.get("next_action"):
                        st.caption(f"Teendő: {event['next_action']} · {event.get('next_action_due') or 'határidő nélkül'}")
            if not can_manage:
                continue

            st.divider()
            if assignable_users:
                user_options = [""] + [str(user["user_id"]) for user in assignable_users]
                current_assignment = assigned_to if assigned_to in user_options else ""
                with st.form(f"crm_owner_form_{lead_id}"):
                    st.markdown("**Felelős hozzárendelése**")
                    selected_owner = st.selectbox(
                        "Admin/operator felelős",
                        options=user_options,
                        index=user_options.index(current_assignment),
                        format_func=lambda value: (
                            "Nincs felelős" if not value else next(
                                (
                                    str(user.get("display_name") or user.get("email")) + " · " + str(user.get("role"))
                                    for user in assignable_users
                                    if str(user.get("user_id")) == value
                                ),
                                "Ismeretlen felhasználó",
                            )
                        ),
                        key=f"crm_owner_{lead_id}",
                    )
                    owner_note = st.text_input(
                        "Hozzárendelés indoka (kötelező)",
                        max_chars=500,
                        key=f"crm_owner_note_{lead_id}",
                    )
                    owner_submit = st.form_submit_button("Felelős mentése")
                if owner_submit:
                    if len(owner_note.strip()) < 5:
                        st.warning("Legalább 5 karakteres indoklás szükséges.")
                    else:
                        try:
                            db.rpc("assign_lead_customer_owner", {
                                "p_lead_id": lead_id,
                                "p_assignee_id": selected_owner or None,
                                "p_note": owner_note.strip(),
                            }).execute()
                            st.success("A felelős-hozzárendelés elmentve.")
                            st.rerun()
                        except Exception as exc:
                            st.error("A felelős nem rendelhető hozzá. Ellenőrizd a jogosultságot és a célfelhasználót.")
                            st.caption("Hibatípus: " + type(exc).__name__)

            with st.form(f"crm_stage_form_{lead_id}"):
                st.markdown("**Életciklus-státusz módosítása**")
                new_stage = st.selectbox(
                    "Új státusz",
                    options=list(_STAGES),
                    index=list(_STAGES).index(stage) if stage in _STAGES else 0,
                    format_func=lambda value: _STAGES[value],
                    key=f"crm_stage_{lead_id}",
                )
                stage_note = st.text_area(
                    "Mi indokolja a státuszváltozást? (kötelező)",
                    max_chars=2000,
                    key=f"crm_stage_note_{lead_id}",
                )
                stage_submit = st.form_submit_button("Státusz mentése")
            if stage_submit:
                if len(stage_note.strip()) < 5:
                    st.warning("Legalább 5 karakteres indoklás szükséges.")
                else:
                    try:
                        _record(
                            db, p_lead_id=lead_id, p_event_type="stage_changed",
                            p_stage=new_stage, p_channel=None, p_summary=stage_note.strip(),
                            p_next_action=None, p_next_action_due=None,
                        )
                        st.success("A státusz és az indoklás elmentve.")
                        st.rerun()
                    except Exception as exc:
                        st.error("A státuszváltozás nem menthető. Ellenőrizd az engedélyezett leadet és a CRM-migrációt.")
                        st.caption(f"Hibatípus: {type(exc).__name__}")

            with st.form(f"crm_interaction_form_{lead_id}"):
                st.markdown("**Ügyfélinterakció rögzítése**")
                channel = st.selectbox(
                    "Csatorna", options=list(_CHANNELS),
                    format_func=lambda value: _CHANNELS[value],
                    key=f"crm_channel_{lead_id}",
                )
                interaction_note = st.text_area(
                    "Mi történt? (kötelező)",
                    max_chars=2000,
                    key=f"crm_interaction_{lead_id}",
                )
                interaction_submit = st.form_submit_button("Interakció naplózása")
            if interaction_submit:
                if len(interaction_note.strip()) < 5:
                    st.warning("Legalább 5 karakteres összefoglaló szükséges.")
                else:
                    try:
                        _record(
                            db, p_lead_id=lead_id, p_event_type="interaction_logged",
                            p_stage=None, p_channel=channel, p_summary=interaction_note.strip(),
                            p_next_action=None, p_next_action_due=None,
                        )
                        st.success("Az interakció elmentve. E-mailt nem küldtem.")
                        st.rerun()
                    except Exception as exc:
                        st.error("Az interakció nem menthető.")
                        st.caption(f"Hibatípus: {type(exc).__name__}")

            with st.form(f"crm_next_action_form_{lead_id}"):
                st.markdown("**Következő teendő beállítása**")
                next_action = st.text_input(
                    "Teendő", max_chars=500, key=f"crm_next_action_{lead_id}"
                )
                due_date = st.text_input(
                    "Határidő (YYYY-MM-DD, opcionális)",
                    key=f"crm_due_date_{lead_id}",
                )
                action_note = st.text_area(
                    "Megjegyzés (kötelező)", max_chars=2000,
                    key=f"crm_action_note_{lead_id}",
                )
                action_submit = st.form_submit_button("Teendő mentése")
            if action_submit:
                if not next_action.strip() or len(action_note.strip()) < 5:
                    st.warning("A teendő és legalább 5 karakteres megjegyzés kötelező.")
                else:
                    try:
                        due = _parse_due_date(due_date)
                        _record(
                            db, p_lead_id=lead_id, p_event_type="next_action_set",
                            p_stage=None, p_channel=None, p_summary=action_note.strip(),
                            p_next_action=next_action.strip(), p_next_action_due=due,
                        )
                        st.success("A következő teendő elmentve.")
                        st.rerun()
                    except Exception as exc:
                        st.error("A teendő nem menthető. Ellenőrizd a határidő formátumát.")
                        st.caption(f"Hibatípus: {type(exc).__name__}")
