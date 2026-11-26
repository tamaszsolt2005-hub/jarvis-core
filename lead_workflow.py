"""Read-only lead-to-task workflow planning from grounded research records.

This module proposes the next internal validation task for a researched company.
It never writes to the database, grants outreach consent, or sends messages.
"""
from __future__ import annotations

import re
from typing import Any

from intelligent_lead_scoring import score_researched_lead


_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.I)
_RECOMMENDED_TASK_PREFIXES = ("hozz létre javasolt feladat:", "hozz letre javasolt feladat:")

_INDUSTRY = re.compile(r"tényleges ország:\s*(.*?);\s*iparág:\s*(.*?)\.\s", re.I)
_NEED = re.compile(r"megfigyelhető üzleti igény:\s*(.*?);\s*alátámasztó jelek:", re.I)


def _clean(value: Any, limit: int = 240) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def build_lead_workflow_recommendations(
    leads: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Suggest one evidence-based internal next task per lead, without side effects.

    Any existing task linked to a lead suppresses another first-stage suggestion.
    This deliberately avoids creating repeated tasks until the workflow has explicit
    stage transitions and completion outcomes.
    """
    linked_lead_ids = {
        str(task.get("lead_id"))
        for task in tasks
        if task.get("lead_id") and str(task.get("status") or "open").casefold() != "cancelled"
    }
    recommendations: list[dict[str, Any]] = []

    for lead in leads:
        lead_id = _clean(lead.get("id"), 64)
        company = _clean(lead.get("company_name"), 180) or "Ismeretlen cég"
        if not lead_id or lead_id in linked_lead_ids:
            continue

        research = _clean(lead.get("research_intelligence"), 3500)
        if not research.startswith("Leadkutatás;"):
            continue
        score = score_researched_lead({"research_intelligence": research})
        if not score.get("scored"):
            continue

        industry_match = _INDUSTRY.search(research)
        need_match = _NEED.search(research)
        industry = _clean(industry_match.group(2), 120) if industry_match else ""
        business_need = _clean(need_match.group(1), 300) if need_match else ""
        confidence = score["research_confidence"]
        evidence_count = score["evidence_count"]
        priority_score = score["priority_score"]

        if confidence == "low" or evidence_count < 2:
            task_title = f"Kutatási bizonyítékok kiegészítése – {company}"[:180]
            task_priority = "normal"
            rationale = "A bizonyosság vagy a nyilvános bizonyítékok száma még nem elég erős üzleti döntéshez."
        else:
            task_title = f"Üzleti igény és szolgáltatási illeszkedés ellenőrzése – {company}"[:180]
            task_priority = "high" if priority_score >= 85 else "normal"
            rationale = "A kutatási jelzések alapján indokolt a konkrét üzleti igény emberi ellenőrzése."

        evidence = score.get("evidence", [])
        notes = (
            f"Leadazonosító: {lead_id}. Kutatási prioritás: {priority_score}/100; "
            f"üzleti illeszkedés: {score['business_fit_score']}/100; "
            f"bizonyosság: {confidence}; bizonyítékok: {evidence_count}. "
            f"Iparág: {industry or 'nincs strukturált adat'}. "
            f"Megfigyelt igény: {business_need or 'nincs strukturált adat'}. "
            f"Nyilvános jelek: {', '.join(evidence) if evidence else 'nincs részletezve'}. "
            f"Következő lépés: {rationale} Ez nem kapcsolatfelvételi engedély."
        )[:1000]
        recommendations.append({
            "lead_id": lead_id,
            "company_name": company,
            "task_title": task_title,
            "task_priority": task_priority,
            "priority_score": priority_score,
            "business_fit_score": score["business_fit_score"],
            "research_confidence": confidence,
            "evidence_count": evidence_count,
            "industry": industry or "Ismeretlen",
            "business_need": business_need,
            "rationale": rationale,
            "notes": notes,
            "outreach_allowed": False,
        })

    recommendations.sort(
        key=lambda item: (
            item["priority_score"],
            item["business_fit_score"],
            item["evidence_count"],
        ),
        reverse=True,
    )
    return recommendations[:max(0, min(int(limit), 20))]


def parse_recommended_task_command(message: str) -> dict[str, str] | None:
    """Parse an explicit request to prepare a researched lead's suggested task."""
    text = _clean(message, 240).strip()
    if not text.casefold().startswith(_RECOMMENDED_TASK_PREFIXES):
        return None
    if ":" not in text:
        return {"error": "A leadazonosítót a kettőspont után add meg."}
    lead_id = text.split(":", 1)[1].strip()
    if not _UUID.fullmatch(lead_id):
        return {"error": "Érvényes lead UUID szükséges a javasolt feladat előkészítéséhez."}
    return {"lead_id": lead_id.lower()}


def build_recommended_task_action(
    lead: dict[str, Any],
    linked_tasks: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Convert one current research recommendation into an approval-ready task payload.

    This is still only preparation: the caller must stage the action through the
    existing one-use approval flow before the database RPC can create anything.
    """
    lead_id = _clean(lead.get("id"), 64).lower()
    source = _clean(lead.get("source"), 180)
    research = _clean(lead.get("notes"), 3500)
    if not _UUID.fullmatch(lead_id) or not source.startswith("gemini_google_search_grounding:"):
        return None

    recommendations = build_lead_workflow_recommendations(
        [{
            "id": lead_id,
            "company_name": lead.get("company_name"),
            "research_intelligence": research,
        }],
        linked_tasks,
        limit=1,
    )
    if not recommendations:
        return None

    item = recommendations[0]
    return {
        "type": "create",
        "title": item["task_title"],
        "priority": item["task_priority"],
        "due_at": None,
        "notes": item["notes"],
        "lead_id": lead_id,
    }
