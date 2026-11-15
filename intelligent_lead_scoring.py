"""Evidence-aware business-fit prioritization for researched company leads.

The priority score is a research triage aid, not purchase intent, ability to pay,
conversion probability, or permission to contact.
"""
from __future__ import annotations

import re
from typing import Any


_FIT = re.compile(
    r"AI üzleti illeszkedési becslés:\s*(\d{1,3})/100;\s*bizonyosság:\s*(high|medium|low)",
    re.I,
)
_EVIDENCE = re.compile(r"alátámasztó jelek:\s*(.*?);\s*javasolt kutatási lépés:", re.I)


def score_researched_lead(lead: dict[str, Any]) -> dict[str, Any]:
    """Return a transparent 0-100 research-priority estimate or an unscored result."""
    note = str(lead.get("research_intelligence") or "")
    if not note.startswith("Leadkutatás;"):
        return {"scored": False, "priority_score": None, "reason": "Nincs strukturált, saját leadkutatási adat."}
    match = _FIT.search(note)
    if not match:
        return {"scored": False, "priority_score": None, "reason": "Hiányzik az üzleti illeszkedési pontszám vagy bizonyosság."}

    fit = max(0, min(100, int(match.group(1))))
    confidence = match.group(2).lower()
    evidence_match = _EVIDENCE.search(note)
    evidence = [x.strip() for x in (evidence_match.group(1).split(";") if evidence_match else []) if x.strip()]
    confidence_points = {"high": 100, "medium": 65, "low": 30}[confidence]
    evidence_points = min(100, len(evidence) * 25)
    # Fit dominates; confidence and explicit evidence reduce over-ranking weak research.
    priority = round(fit * 0.60 + confidence_points * 0.25 + evidence_points * 0.15)
    if confidence == "low":
        priority = min(priority, 69)
    reasons = [
        f"üzleti illeszkedés {fit}/100",
        f"kutatási bizonyosság: {confidence}",
        f"azonosított nyilvános bizonyíték: {len(evidence)}",
    ]
    return {
        "scored": True,
        "priority_score": priority,
        "business_fit_score": fit,
        "research_confidence": confidence,
        "evidence_count": len(evidence),
        "evidence": evidence[:5],
        "reason": "; ".join(reasons),
        "interpretation": "Kutatási prioritás, nem vásárlási szándék, fizetőképesség vagy kapcsolatfelvételi engedély.",
    }


def rank_researched_leads(leads: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    ranked = []
    for lead in leads:
        score = score_researched_lead(lead)
        if score["scored"]:
            ranked.append({
                "company_name": str(lead.get("company_name") or "Ismeretlen cég")[:180],
                "website": str(lead.get("website") or "")[:300],
                "status": str(lead.get("status") or ""),
                **score,
            })
    ranked.sort(key=lambda row: (row["priority_score"], row["business_fit_score"]), reverse=True)
    return ranked[:max(1, min(int(limit), 100))]
