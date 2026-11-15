"""Read-only daily executive briefing from existing JARVIS records."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from intelligent_lead_scoring import rank_researched_leads


def build_daily_briefing(db: Any, today: date | None = None) -> str:
    """Build a concise daily report; this function never writes to Supabase."""
    today = today or datetime.now(timezone.utc).date()
    leads = db.table("leads").select(
        "id,company_name,website,status,approved_to_contact,opted_out,created_at,notes,source"
    ).order("created_at", desc=True).limit(1500).execute().data or []
    tasks = db.table("tasks").select(
        "id,title,status,priority,due_at,completed_at,lead_id"
    ).limit(1000).execute().data or []

    research_leads = []
    for row in leads:
        source = str(row.get("source") or "")
        note = str(row.get("notes") or "")
        if source.startswith("gemini_google_search_grounding:") and note.startswith("Leadkutatás;"):
            research_leads.append({
                "company_name": row.get("company_name"),
                "website": row.get("website"),
                "status": row.get("status"),
                "research_intelligence": note,
            })
    ranked = rank_researched_leads(research_leads, limit=10)

    overdue = []
    due_today = []
    open_tasks = []
    for task in tasks:
        if str(task.get("status") or "open") != "open":
            continue
        open_tasks.append(task)
        due = str(task.get("due_at") or "")[:10]
        item = {"title": str(task.get("title") or "Névtelen feladat"), "priority": task.get("priority") or "normal"}
        if due and due < today.isoformat():
            overdue.append({**item, "due": due})
        elif due == today.isoformat():
            due_today.append(item)

    fresh_today = []
    for lead in leads:
        created = str(lead.get("created_at") or "")[:10]
        if created == today.isoformat():
            fresh_today.append(str(lead.get("company_name") or "Ismeretlen cég"))

    lines = [
        f"# JARVIS – napi vezetői jelentés ({today.isoformat()})",
        "",
        "## Vezetői összkép",
        f"- Nyilvántartott cégek: {len(leads)}",
        f"- Strukturált, saját leadkutatásból származó cégek: {len(research_leads)}",
        f"- Nyitott feladatok: {len(open_tasks)}",
        f"- Lejárt feladatok: {len(overdue)}",
        f"- Ma esedékes feladatok: {len(due_today)}",
        f"- Ma rögzített cégek: {len(fresh_today)}",
        "",
        "## Elsőként kezelendő kutatási lehetőségek",
    ]
    if ranked:
        for item in ranked[:5]:
            lines.append(
                f"- **{item['company_name']}** – prioritás {item['priority_score']}/100 "
                f"(üzleti illeszkedés {item['business_fit_score']}/100; "
                f"bizonyosság: {item['research_confidence']}; bizonyítékok: {item['evidence_count']}). "
                f"{item['reason']}"
            )
    else:
        lines.append("- Még nincs elegendő strukturált kutatási adat a rangsoroláshoz.")

    lines += ["", "## Lejárt feladatok"]
    lines += [f"- **{x['title']}** – határidő: {x['due']} (prioritás: {x['priority']})" for x in overdue[:10]]
    if not overdue:
        lines.append("- Nincs rögzített lejárt, nyitott feladat.")

    lines += ["", "## Mai teendők"]
    lines += [f"- {x['title']} (prioritás: {x['priority']})" for x in due_today[:10]]
    if not due_today:
        lines.append("- Nincs mára határidőzött nyitott feladat.")

    lines += ["", "## Új cégek ma"]
    lines += [f"- {name}" for name in fresh_today[:15]]
    if not fresh_today:
        lines.append("- Ma még nem került új cég a nyilvántartásba.")

    lines += [
        "",
        "## Következő javasolt lépések",
        "- Ellenőrizd a magas kutatási prioritású cégek nyilvános bizonyítékait.",
        "- Először a lejárt és sürgős feladatokat rendezd.",
        "- Kapcsolatfelvétel előtt külön ellenőrizd a jogalapot és az explicit engedélyt.",
        "",
        "> A prioritási érték kutatási becslés, nem vásárlási szándék, fizetőképesség vagy konverziós valószínűség. A jelentés csak meglévő adatokat olvas; nem küld e-mailt és nem módosít rekordokat.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    from jarvis_common import get_supabase
    from pathlib import Path
    from proactive_monitor import run_proactive_monitor

    db = get_supabase()
    report = build_daily_briefing(db)
    report += "\n" + run_proactive_monitor(db)
    Path("daily_briefing.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
