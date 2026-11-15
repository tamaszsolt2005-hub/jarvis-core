"""Daily change monitor; writes only its dedicated technical snapshot row."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any


STATE_KEY = "daily_proactive_snapshot"


def _rows(db: Any, table: str, columns: str, limit: int) -> list[dict]:
    return db.table(table).select(columns).limit(limit).execute().data or []


def run_proactive_monitor(db: Any, today: date | None = None) -> str:
    today = today or datetime.now(timezone.utc).date()
    leads = _rows(db, "leads", "id,company_name,status,created_at,updated_at,source", 2000)
    tasks = _rows(db, "tasks", "id,title,status,priority,due_at,updated_at,completed_at", 1000)
    prior_rows = (
        db.table("jarvis_proactive_state").select("snapshot")
        .eq("key", STATE_KEY).limit(1).execute().data or []
    )
    previous = prior_rows[0].get("snapshot") if prior_rows else {}
    previous = previous if isinstance(previous, dict) else {}
    old_leads = {str(x.get("id")): x for x in previous.get("leads", []) if x.get("id")}
    old_tasks = {str(x.get("id")): x for x in previous.get("tasks", []) if x.get("id")}

    new_leads = [x for x in leads if x.get("id") and str(x["id"]) not in old_leads]
    changed_leads = [
        {"company": x.get("company_name"), "from": old_leads[str(x["id"])].get("status"), "to": x.get("status")}
        for x in leads if x.get("id") and str(x["id"]) in old_leads
        and old_leads[str(x["id"])].get("status") != x.get("status")
    ]
    new_tasks = [x for x in tasks if x.get("id") and str(x["id"]) not in old_tasks]
    changed_tasks = [
        {"title": x.get("title"), "from": old_tasks[str(x["id"])].get("status"), "to": x.get("status")}
        for x in tasks if x.get("id") and str(x["id"]) in old_tasks
        and any(old_tasks[str(x["id"])].get(field) != x.get(field) for field in ("status", "due_at", "priority"))
    ]
    overdue = [
        x for x in tasks if str(x.get("status") or "open").casefold() == "open"
        and str(x.get("due_at") or "")[:10] and str(x.get("due_at"))[:10] < today.isoformat()
    ]

    lines = [
        "## Változások az előző napi ellenőrzés óta",
        f"- Új cégek: {len(new_leads)}",
        *[f"  - {x.get('company_name') or 'Ismeretlen cég'}" for x in new_leads[:10]],
        f"- Leadstátusz-változások: {len(changed_leads)}",
        *[f"  - {x['company']}: {x['from']} → {x['to']}" for x in changed_leads[:10]],
        f"- Új feladatok: {len(new_tasks)}",
        *[f"  - {x.get('title') or 'Névtelen feladat'}" for x in new_tasks[:10]],
        f"- Feladatstátusz-változások: {len(changed_tasks)}",
        *[f"  - {x['title']}: {x['from']} → {x['to']}" for x in changed_tasks[:10]],
        "",
        "## Elmaradások és prioritások",
        f"- Lejárt, nyitott feladatok: {len(overdue)}",
        *[f"  - {x.get('title') or 'Névtelen feladat'} (határidő: {str(x.get('due_at'))[:10]}, prioritás: {x.get('priority') or 'normal'})" for x in overdue[:10]],
        "- Javaslat: először a sürgős és lejárt feladatokat rendezd, majd vizsgáld felül a frissen változott leadeket.",
        "",
        "> Első futáskor nincs korábbi pillanatkép, ezért az aktuális rekordokat újként mutathatja. A monitor kizárólag ezt a technikai pillanatkép-táblát frissíti; leadet vagy feladatot nem módosít.",
    ]

    snapshot = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "leads": [{"id": x.get("id"), "company_name": x.get("company_name"), "status": x.get("status")} for x in leads if x.get("id")],
        "tasks": [{"id": x.get("id"), "title": x.get("title"), "status": x.get("status"), "due_at": x.get("due_at"), "priority": x.get("priority")} for x in tasks if x.get("id")],
    }
    db.table("jarvis_proactive_state").upsert({"key": STATE_KEY, "snapshot": snapshot}).execute()
    return "\n".join(lines) + "\n"
