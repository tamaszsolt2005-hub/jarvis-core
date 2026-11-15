"""Read-only daily executive briefing from existing JARVIS records."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from intelligent_lead_scoring import rank_researched_leads

LOCAL_TZ = ZoneInfo("Europe/Budapest")


def _local_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=LOCAL_TZ)
        return parsed.astimezone(LOCAL_TZ).date()
    except (TypeError, ValueError):
        return None


def build_daily_briefing(db: Any, today: date | None = None) -> str:
    """Build a concise daily report; this function never writes to Supabase."""
    today = today or datetime.now(LOCAL_TZ).date()
    leads = db.table("leads").select(
        "id,company_name,website,status,approved_to_contact,opted_out,next_follow_up_at,created_at,notes,source"
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

    overdue, due_today, open_tasks = [], [], []
    for task in tasks:
        if str(task.get("status") or "open").casefold() != "open":
            continue
        open_tasks.append(task)
        due_date = _local_date(task.get("due_at"))
        due = due_date.isoformat() if due_date else ""
        item = {"title": str(task.get("title") or "Névtelen feladat"),
                "priority": task.get("priority") or "normal", "due": due}
        if due_date and due_date < today:
            overdue.append(item)
        elif due_date == today:
            due_today.append(item)

    overdue_followups = [
        {"company_name": str(lead.get("company_name") or "Ismeretlen cég"),
         "due": (_local_date(lead.get("next_follow_up_at")) or date.min).isoformat()}
        for lead in leads
        if lead.get("approved_to_contact") is True
        and not bool(lead.get("opted_out", False))
        and _local_date(lead.get("next_follow_up_at")) is not None
        and _local_date(lead.get("next_follow_up_at")) < today
    ]

    priority_tasks = [x for x in open_tasks if str(x.get("priority") or "normal").casefold() in {"urgent", "high"}]
    priority_tasks.sort(key=lambda x: (0 if str(x.get("priority")).casefold() == "urgent" else 1,
                                       str(x.get("due_at") or "9999")))
    overdue.sort(key=lambda x: (0 if str(x.get("priority")).casefold() == "urgent" else 1, x["due"]))
    due_today.sort(key=lambda x: (0 if str(x.get("priority")).casefold() == "urgent" else 1, x["title"]))
    fresh_today = [
        str(lead.get("company_name") or "Ismeretlen cég") for lead in leads
        if str(lead.get("created_at") or "")[:10] == today.isoformat()
    ]

    lines = [
        f"# JARVIS – napi vezetői jelentés ({today.isoformat()})", "",
        "## Vezetői összkép",
        f"- Vizsgált cégek (legfeljebb 1500): {len(leads)}",
        f"- Strukturált, saját leadkutatásból származó cégek: {len(research_leads)}",
        f"- Nyitott feladatok a vizsgált körben (legfeljebb 1000): {len(open_tasks)}",
        f"- Lejárt feladatok: {len(overdue)}",
        f"- Ma esedékes feladatok: {len(due_today)}",
        f"- Ma rögzített cégek: {len(fresh_today)}",
        f"- Lejárt, jóváhagyott utánkövetések: {len(overdue_followups)}", "",
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

    lines += ["", "## Kiemelt nyitott feladatok"]
    lines += [f"- {x.get('title') or 'Névtelen feladat'} (prioritás: {x.get('priority')})" for x in priority_tasks[:10]]
    if not priority_tasks:
        lines.append("- Nincs sürgős vagy magas prioritású nyitott feladat.")

    lines += ["", "## Lejárt feladatok"]
    lines += [f"- **{x['title']}** – határidő: {x['due']} (prioritás: {x['priority']})" for x in overdue[:10]]
    if not overdue:
        lines.append("- Nincs rögzített lejárt, nyitott feladat.")

    lines += ["", "## Lejárt, jóváhagyott utánkövetések"]
    lines += [f"- **{x['company_name']}** – esedékes: {x['due']}" for x in overdue_followups[:10]]
    if not overdue_followups:
        lines.append("- Nincs lejárt, engedélyezett utánkövetés.")

    lines += ["", "## Mai teendők"]
    lines += [f"- {x['title']} (prioritás: {x['priority']})" for x in due_today[:10]]
    if not due_today:
        lines.append("- Nincs mára határidőzött nyitott feladat.")

    lines += ["", "## Új cégek ma"]
    lines += [f"- {name}" for name in fresh_today[:15]]
    if not fresh_today:
        lines.append("- Ma még nem került új cég a nyilvántartásba.")

    lines += ["", "## Javasolt napi akcióterv"]
    action_items = []
    for task in overdue[:3]:
        action_items.append(
            f"{len(action_items) + 1}. Rendezd a lejárt feladatot vagy ütemezd újra: "
            f"**{task['title']}** (határidő: {task['due']}, prioritás: {task['priority']})."
        )
    for followup in overdue_followups[:2]:
        action_items.append(
            f"{len(action_items) + 1}. Vizsgáld felül a jóváhagyott utánkövetést: "
            f"**{followup['company_name']}** (esedékes: {followup['due']}); küldés előtt ellenőrizd az aktuális engedélyt."
        )
    for task in due_today[:2]:
        action_items.append(
            f"{len(action_items) + 1}. Végezd el vagy delegáld a mai feladatot: "
            f"**{task['title']}** (prioritás: {task['priority']})."
        )
    if ranked:
        lead = ranked[0]
        action_items.append(
            f"{len(action_items) + 1}. Ellenőrizd a legmagasabb kutatási prioritású céget: "
            f"**{lead['company_name']}** ({lead['priority_score']}/100); nézd át a forrásokat, "
            "mielőtt bármilyen kapcsolatfelvételi döntés születik."
        )
    if not action_items:
        action_items.append("Nincs sürgős, határidős feladat vagy rangsorolt kutatási lehetőség; frissítsd a következő üzleti célt.")
    lines += action_items[:5]
    lines += [
        "", "## Következő javasolt lépések",
        "- Ellenőrizd a magas kutatási prioritású cégek nyilvános bizonyítékait.",
        "- Először a lejárt és sürgős feladatokat rendezd.",
        "- Kapcsolatfelvétel előtt külön ellenőrizd a jogalapot és az explicit engedélyt.", "",
        "> A jelentés legfeljebb 1500 leadet és 1000 feladatot vizsgál; a darabszámok erre a mintára vonatkoznak. "
        "> A prioritási érték kutatási becslés, nem vásárlási szándék, fizetőképesség vagy konverziós valószínűség. "
        "A jelentés csak meglévő adatokat olvas; a napi monitor kizárólag a külön technikai pillanatképet frissíti. "
        "Leadet vagy feladatot nem módosít, és nem küld e-mailt.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    from jarvis_common import get_supabase
    from pathlib import Path
    from proactive_monitor import run_proactive_monitor

    db = get_supabase()
    report = build_daily_briefing(db)
    try:
        report += "\n" + run_proactive_monitor(db)
    except Exception as exc:
        report += (
            "\n## Proaktív változásfigyelés\n"
            f"- A monitor most nem futott le ({type(exc).__name__}). "
            "Ellenőrizd, hogy a frissített Supabase-séma telepítve van-e.\n"
        )
    Path("daily_briefing.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
