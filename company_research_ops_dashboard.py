"""Human-controlled research worker operations dashboard.

The page uses authenticated RPCs only; it never creates or receives a service-role
client and never starts a worker itself.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st


def _rpc_payload(response: Any, *, operation: str) -> dict[str, Any]:
    data = getattr(response, "data", None)
    if isinstance(data, dict):
        return data
    if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):
        return data[0]
    raise RuntimeError(f"{operation} RPC returned an unexpected response shape.")


def _nonnegative_int(value: Any) -> int:
    """Normalize untrusted RPC counters without letting malformed values break the page."""
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        return 0


def _build_ops_alerts(state: dict[str, Any], *, now: Any = None) -> list[dict[str, str]]:
    """Derive actionable local alerts from the authenticated read-only ops snapshot."""
    from datetime import datetime, timezone

    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    counts = state.get("counts") if isinstance(state.get("counts"), dict) else {}
    budget = state.get("budget_today") if isinstance(state.get("budget_today"), dict) else {}
    alerts: list[dict[str, str]] = []

    dead_letter = _nonnegative_int(counts.get("dead_letter", 0))
    if dead_letter:
        alerts.append({
            "severity": "error",
            "message": f"{dead_letter} kutatási feladat a hibazsákban vár operátori felülvizsgálatra.",
        })
    if budget.get("over_budget") is True:
        alerts.append({
            "severity": "error",
            "message": "A napi kutatási költségfoglalás túllépte a rögzített keretet; új foglalást a DB-kapu blokkol.",
        })

    limit = _nonnegative_int(budget.get("limit_microusd", 0))
    committed = _nonnegative_int(
        budget.get("committed_microusd", budget.get("reserved_microusd", 0))
    )
    if limit > 0 and committed >= limit * 0.8 and budget.get("over_budget") is not True:
        alerts.append({
            "severity": "warning",
            "message": f"A napi költségkeret legalább 80%-a lekötve ({committed / limit:.0%}).",
        })

    expired_leases = 0
    for job in state.get("recent_jobs", []) if isinstance(state.get("recent_jobs"), list) else []:
        if not isinstance(job, dict) or job.get("status") != "running":
            continue
        raw_expiry = job.get("lease_expires_at")
        if not raw_expiry:
            expired_leases += 1
            continue
        try:
            expiry = raw_expiry if isinstance(raw_expiry, datetime) else datetime.fromisoformat(
                str(raw_expiry).replace("Z", "+00:00")
            )
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            if expiry <= reference:
                expired_leases += 1
        except (TypeError, ValueError, OverflowError):
            expired_leases += 1
    if expired_leases:
        alerts.append({
            "severity": "warning",
            "message": f"{expired_leases} futó job lease-e lejárt vagy hiányos; worker-újrafelvétel szükséges lehet.",
        })
    return alerts


def load_worker_control_state(db: Any) -> dict[str, Any]:
    if db is None or not callable(getattr(db, "rpc", None)):
        raise ValueError("An authenticated Supabase client is required.")
    try:
        response = db.rpc("company_research_worker_control_state", {}).execute()
    except Exception as exc:
        raise RuntimeError("Could not load company research worker state.") from exc
    return _rpc_payload(response, operation="company_research_worker_control_state")


def set_worker_paused(db: Any, *, paused: bool, note: str) -> dict[str, Any]:
    if not isinstance(paused, bool):
        raise ValueError("paused must be boolean")
    normalized_note = str(note or "").strip()
    if not 5 <= len(normalized_note) <= 500:
        raise ValueError("A pause/resume reason of 5–500 characters is required.")
    try:
        response = db.rpc(
            "company_research_worker_set_paused",
            {"p_paused": paused, "p_note": normalized_note},
        ).execute()
    except Exception as exc:
        raise RuntimeError("Could not change company research worker state.") from exc
    return _rpc_payload(response, operation="company_research_worker_set_paused")


def render_company_research_ops_page(db: Any, *, auth_enabled: bool, role: str | None) -> None:
    st.title("Kutatási műveletek")
    st.caption("A cégkutatási worker állapota, feladatai és napi költségkerete.")
    if not auth_enabled or role not in {"admin", "operator", "reader"}:
        st.error("Ehhez az oldalhoz ellenőrzött Supabase Auth-fiók szükséges.")
        return

    try:
        state = load_worker_control_state(db)
    except Exception as exc:
        st.error("A kutatási műveleti állapot nem érhető el.")
        st.caption(type(exc).__name__)
        return

    if not isinstance(state.get("paused"), bool) or not state.get("updated_at"):
        st.error("A worker vezérlési állapota hiányos; biztonsági okból nem tekinthető engedélyezettnek.")
        return
    paused = state["paused"]
    if paused:
        st.warning("A kutatási worker szünetel. Új feladatot nem vesz fel.")
    else:
        st.success("A kutatási worker engedélyezett állapotban van.")

    counts = state.get("counts") if isinstance(state.get("counts"), dict) else {}
    labels = (
        ("Várakozik", "queued"),
        ("Fut", "running"),
        ("Újrapróbálás", "retry_wait"),
        ("Sikeres", "succeeded"),
        ("Hibazsák", "dead_letter"),
    )
    columns = st.columns(len(labels))
    for column, (label, key) in zip(columns, labels):
        column.metric(label, _nonnegative_int(counts.get(key, 0)))

    budget = state.get("budget_today") if isinstance(state.get("budget_today"), dict) else {}
    reserved = _nonnegative_int(budget.get("reserved_microusd", 0)) / 1_000_000
    committed_raw = budget.get("committed_microusd", budget.get("reserved_microusd", 0))
    committed = _nonnegative_int(committed_raw) / 1_000_000
    actual = _nonnegative_int(budget.get("actual_microusd", 0)) / 1_000_000
    st.markdown("#### Mai költség")
    st.write(
        f"Függő foglalás: **${reserved:,.4f}** · "
        f"napi keretből lekötött összeg: **${committed:,.4f}** · "
        f"tényleges költség: **${actual:,.4f}**"
    )
    jobs_today = _nonnegative_int(budget.get("jobs_today", 0))
    st.caption(f"Mai kutatási jobok: {jobs_today}")
    daily_limit = _nonnegative_int(budget.get("limit_microusd", 0)) / 1_000_000
    if budget.get("over_budget") is True:
        st.error(
            f"A ténylegesen lekötött napi költség (${committed:,.4f}) meghaladta "
            f"a foglaláskor érvényes napi keretet (${daily_limit:,.4f}). Új jobot a DB kvótakapuja nem enged."
        )
    elif daily_limit > 0:
        st.caption(f"Napi költségkeret: ${daily_limit:,.4f}")

    st.markdown("#### Operátori riasztások")
    alerts = _build_ops_alerts(state)
    if not alerts:
        st.success("Nincs aktív költség-, lease- vagy hibazsák-riasztás.")
    for alert in alerts:
        if alert["severity"] == "error":
            st.error(alert["message"])
        else:
            st.warning(alert["message"])

    if role in {"admin", "operator"}:
        note = st.text_area(
            "Indoklás a szüneteltetéshez vagy újraindításhoz",
            key="research_worker_control_note",
            max_chars=500,
            placeholder="Például: karbantartás / ellenőrzés befejeződött",
        )
        action_columns = st.columns(2)
        with action_columns[0]:
            if st.button("Kutatás szüneteltetése", disabled=paused, key="research_worker_pause"):
                try:
                    set_worker_paused(db, paused=True, note=note)
                    st.success("A worker szüneteltetése rögzítve.")
                    st.rerun()
                except Exception as exc:
                    st.error("A szüneteltetés nem sikerült.")
                    st.caption(type(exc).__name__)
        with action_columns[1]:
            if st.button("Kutatás újraindítása", disabled=not paused, key="research_worker_resume"):
                try:
                    set_worker_paused(db, paused=False, note=note)
                    st.success("A worker újraindítása rögzítve.")
                    st.rerun()
                except Exception as exc:
                    st.error("Az újraindítás nem sikerült.")
                    st.caption(type(exc).__name__)
    else:
        st.info("Olvasási mód: a worker állapotát megtekintheted, de nem módosíthatod.")

    if state.get("note"):
        st.caption(f"Utolsó vezérlési indok: {state['note']}")
    st.caption(f"Utolsó vezérlési módosítás: {state['updated_at']}")
    st.markdown("#### Legutóbbi kutatási jobok leadenként")
    jobs = state.get("recent_jobs") if isinstance(state.get("recent_jobs"), list) else []
    if jobs:
        st.dataframe(pd.DataFrame(jobs), width="stretch", hide_index=True)
    else:
        st.info("Még nincs kutatási feladat.")
    st.markdown("#### Vezérlési előzmények")
    events = state.get("recent_events") if isinstance(state.get("recent_events"), list) else []
    if events:
        st.dataframe(pd.DataFrame(events), width="stretch", hide_index=True)
    else:
        st.caption("Még nincs szüneteltetési vagy újraindítási esemény.")

    st.markdown("#### Kutatási feladatok audit-eseményei")
    job_events = state.get("recent_job_events") if isinstance(state.get("recent_job_events"), list) else []
    if job_events:
        st.dataframe(pd.DataFrame(job_events), width="stretch", hide_index=True)
    else:
        st.caption("Még nincs worker-audit esemény.")
