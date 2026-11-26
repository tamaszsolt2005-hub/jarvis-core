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

_WORKFLOW_STAGES = (
    ("research_validation", "Kutatási bizonyítékok ellenőrzése"),
    ("business_need_validation", "Üzleti igény és szolgáltatási illeszkedés ellenőrzése"),
    ("offer_preparation", "Ajánlati koncepció előkészítése"),
    ("offer_review", "Ajánlati koncepció emberi felülvizsgálata"),
    ("follow_up_review", "Utánkövetési jogosultság és következő lépés ellenőrzése"),
    ("outcome_measurement", "Eredmény és üzleti hatás rögzítésének ellenőrzése"),
)
_STAGE_MARKER = re.compile(r"\[JARVIS_STAGE:([a-z_]+)\]")


def _clean(value: Any, limit: int = 240) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _task_stage(task: dict[str, Any]) -> str | None:
    match = _STAGE_MARKER.search(str(task.get("notes") or ""))
    stage = match.group(1) if match else None
    return stage if stage in {item[0] for item in _WORKFLOW_STAGES} else None


def _next_stage(tasks: list[dict[str, Any]], initial_stage: str) -> str | None:
    """Return the next safe stage; open work blocks, cancelled work is retryable."""
    if any(str(task.get("status") or "open").casefold() == "open" for task in tasks):
        return None

    staged = [task for task in tasks if _task_stage(task)]
    if not staged:
        return initial_stage

    latest = max(
        staged,
        key=lambda task: str(task.get("completed_at") or task.get("created_at") or ""),
    )
    stage = _task_stage(latest)
    status = str(latest.get("status") or "open").casefold()
    stage_index = next(i for i, item in enumerate(_WORKFLOW_STAGES) if item[0] == stage)
    if status == "cancelled":
        return stage
    if status != "done":
        return None
    next_index = stage_index + 1
    return _WORKFLOW_STAGES[next_index][0] if next_index < len(_WORKFLOW_STAGES) else None


def build_lead_workflow_recommendations(
    leads: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Suggest the next internal workflow stage from grounded lead research.

    Stage history is encoded in task notes. This function is read-only and never
    grants outreach consent or sends messages.
    """
    tasks_by_lead: dict[str, list[dict[str, Any]]] = {}
    for task in tasks:
        lead_id = _clean(task.get("lead_id"), 64)
        if lead_id:
            tasks_by_lead.setdefault(lead_id, []).append(task)

    recommendations: list[dict[str, Any]] = []
    for lead in leads:
        lead_id = _clean(lead.get("id"), 64)
        company = _clean(lead.get("company_name"), 180) or "Ismeretlen cég"
        if not lead_id:
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
        initial_stage = (
            "research_validation"
            if confidence == "low" or evidence_count < 2
            else "business_need_validation"
        )
        stage = _next_stage(tasks_by_lead.get(lead_id, []), initial_stage)
        if stage is None:
            continue

        stage_label = dict(_WORKFLOW_STAGES)[stage]
        task_title = f"{stage_label} – {company}"[:180]
        task_priority = (
            "high" if stage == "business_need_validation" and priority_score >= 85
            else "normal"
        )
        stage_guidance = {
            "research_validation": "Ellenőrizd a forrásokat, dátumokat és a bizonyítékok valódiságát.",
            "business_need_validation": "Emberi ellenőrzéssel pontosítsd a problémát, döntéshozói szerepet és szolgáltatási illeszkedést.",
            "offer_preparation": "Készíts belső ajánlati vázlatot; ne küldd el és ne ígérj vállalást.",
            "offer_review": "Ellenőrizd az árazást, teljesíthetőséget, kockázatokat és az ajánlat pontosságát; külső küldéshez külön jóváhagyás kell.",
            "follow_up_review": "Csak meglévő, érvényes hozzájárulás, jóváhagyott cím és leiratkozás hiánya esetén készíts utánkövetési javaslatot. Ne küldj üzenetet.",
            "outcome_measurement": "Rögzítsd a döntést, az ügyfél reakcióját, a következő lépést és a mérhető üzleti eredményt a feladat lezárása előtt.",
        }[stage]
        evidence = score.get("evidence", [])
        marker = f"[JARVIS_STAGE:{stage}]"
        notes = (
            f"{marker} Leadazonosító: {lead_id}. Kutatási prioritás: {priority_score}/100; "
            f"üzleti illeszkedés: {score['business_fit_score']}/100; "
            f"bizonyosság: {confidence}; bizonyítékok: {evidence_count}. "
            f"Iparág: {industry or 'nincs strukturált adat'}. "
            f"Megfigyelt igény: {business_need or 'nincs strukturált adat'}. "
            f"Nyilvános jelek: {', '.join(evidence) if evidence else 'nincs részletezve'}. "
            f"Szakaszfeladat: {stage_guidance} Ez nem kapcsolatfelvételi engedély."
        )[:1000]
        recommendations.append({
            "lead_id": lead_id,
            "company_name": company,
            "task_title": task_title,
            "task_priority": task_priority,
            "workflow_stage": stage,
            "workflow_stage_label": stage_label,
            "priority_score": priority_score,
            "business_fit_score": score["business_fit_score"],
            "research_confidence": confidence,
            "evidence_count": evidence_count,
            "industry": industry or "Ismeretlen",
            "business_need": business_need,
            "rationale": stage_guidance,
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
