"""Daily change monitor; writes only its dedicated technical snapshot row."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo


STATE_KEY = "daily_proactive_snapshot"
LOCAL_TZ = ZoneInfo("Europe/Budapest")


def _rows(db: Any, table: str, columns: str, limit: int) -> list[dict]:
    return db.table(table).select(columns).limit(limit).execute().data or []


def run_proactive_monitor(db: Any, today: date | None = None) -> str:
    today = today or datetime.now(LOCAL_TZ).date()
    leads = _rows(db, "leads", "id,company_name,status,created_at,updated_at,source", 2000)
    tasks = _rows(db, "tasks", "id,title,status,priority,due_at,updated_at,completed_at", 1000)
    prior_rows = (
        db.table("jarvis_proactive_state").select("snapshot")
        .eq("key", STATE_KEY).limit(1).execute().data or []
    )
    has_baseline = bool(prior_rows)
    previous = prior_rows[0].get("snapshot") if prior_rows else {}
    previous = previous if isinstance(previous, dict) else {}
    old_leads = {str(x.get("id")): x for x in previous.get("leads", []) if x.get("id")}
    old_tasks = {str(x.get("id")): x for x in previous.get("tasks", []) if x.get("id")}

    new_leads = [x for x in leads if has_baseline and x.get("id") and str(x["id"]) not in old_leads]
    changed_leads = [
        {"company": x.get("company_name"), "from": old_leads[str(x["id"])].get("status"), "to": x.get("status")}
        for x in leads if x.get("id") and str(x["id"]) in old_leads
        and old_leads[str(x["id"])].get("status") != x.get("status")
    ]
    new_tasks = [x for x in tasks if has_baseline and x.get("id") and str(x["id"]) not in old_tasks]
    changed_tasks = []
    for task in tasks:
        task_id = str(task.get("id") or "")
        if not task_id or task_id not in old_tasks:
            continue
        old = old_tasks[task_id]
        changes = []
        for field, label in (("status", "állapot"), ("due_at", "határidő"), ("priority", "prioritás")):
            if old.get(field) != task.get(field):
                changes.append(f"{label}: {old.get(field) or 'nincs'} → {task.get(field) or 'nincs'}")
        if changes:
            changed_tasks.append({"title": task.get("title"), "changes": changes})

    status_change_count = sum(1 for item in changed_tasks if any(change.startswith("állapot:") for change in item["changes"]))
    overdue = [
        x for x in tasks if str(x.get("status") or "open").casefold() == "open"
        and str(x.get("due_at") or "")[:10] and str(x.get("due_at"))[:10] < today.isoformat()
    ]
    due_today = [
        x for x in tasks if str(x.get("status") or "open").casefold() == "open"
        and str(x.get("due_at") or "")[:10] == today.isoformat()
    ]
    urgent_open = [x for x in tasks if str(x.get("status") or "open").casefold() == "open"
                   and str(x.get("priority") or "normal").casefold() == "urgent"]

    lines = [
        "## Változások az előző napi ellenőrzés óta",
        f"- Új cégek: {len(new_leads)}",
        *[f"  - {x.get('company_name') or 'Ismeretlen cég'}" for x in new_leads[:10]],
        f"- Leadstátusz-változások: {len(changed_leads)}",
        *[f"  - {x['company']}: {x['from']} → {x['to']}" for x in changed_leads[:10]],
        f"- Új feladatok: {len(new_tasks)}",
        *[f"  - {x.get('title') or 'Névtelen feladat'}" for x in new_tasks[:10]],
        f"- Feladatstátusz-változások: {status_change_count}",
        f"- Módosult feladatok: {len(changed_tasks)}",
        *[f"  - {x['title']}: {'; '.join(x['changes'])}" for x in changed_tasks[:10]],
        "",
        "## Elmaradások és prioritások",
        f"- Lejárt, nyitott feladatok: {len(overdue)}",
        *[f"  - {x.get('title') or 'Névtelen feladat'} (határidő: {str(x.get('due_at'))[:10]}, prioritás: {x.get('priority') or 'normal'})" for x in overdue[:10]],
        f"- Ma esedékes nyitott feladatok: {len(due_today)}",
        *[f"  - {x.get('title') or 'Névtelen feladat'} (prioritás: {x.get('priority') or 'normal'})" for x in due_today[:10]],
        f"- Sürgős nyitott feladatok: {len(urgent_open)}",
        *[f"  - {x.get('title') or 'Névtelen feladat'}" for x in urgent_open[:10]],
        "",
        "## Javasolt következő lépések",
    ]
    next_steps = []
    for task in sorted(overdue, key=lambda x: (0 if str(x.get("priority")).casefold() == "urgent" else 1,
                                                str(x.get("due_at") or "")))[:3]:
        next_steps.append(f"- Egyeztesd vagy ütemezd újra a lejárt feladatot: {task.get('title') or 'Névtelen feladat'}.")
    for task in due_today[:2]:
        next_steps.append(f"- Végezd el vagy delegáld a mai feladatot: {task.get('title') or 'Névtelen feladat'}.")
    if not next_steps:
        next_steps.append("- Nincs azonosított lejárt vagy mára esedékes feladat; ellenőrizd a következő üzleti célt.")
    lines.extend(next_steps[:5])
    lines.extend([
        "",
        ("> Az első futás csak alapállapotot rögzít; a meglévő rekordokat nem jelenti tévesen újnak. A következő futások ettől az alapállapottól jelzik az új rekordokat és változásokat." if not has_baseline else "> A változásokat az előző sikeres pillanatképhez viszonyítjuk."),
        "> A monitor kizárólag ezt a technikai pillanatkép-táblát frissíti; leadet vagy feladatot nem módosít.",
    ])

    snapshot = {
        "captured_at": datetime.now(LOCAL_TZ).isoformat(),
        "leads": [{"id": x.get("id"), "company_name": x.get("company_name"), "status": x.get("status")} for x in leads if x.get("id")],
        "tasks": [{"id": x.get("id"), "title": x.get("title"), "status": x.get("status"),
                   "due_at": x.get("due_at"), "priority": x.get("priority")} for x in tasks if x.get("id")],
    }
    db.table("jarvis_proactive_state").upsert({"key": STATE_KEY, "snapshot": snapshot}).execute()
    return "\n".join(lines) + "\n"
