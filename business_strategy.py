"""Evidence-based, read-only market intelligence from saved company research."""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any


_COUNTRY_INDUSTRY = re.compile(r"tényleges ország:\s*(.*?);\s*iparág:\s*(.*?)\.\s", re.I)
_FIT = re.compile(r"AI üzleti illeszkedési becslés:\s*(\d{1,3})/100;\s*bizonyosság:\s*(high|medium|low)", re.I)
_NEED = re.compile(r"megfigyelhető üzleti igény:\s*(.*?);\s*alátámasztó jelek:", re.I)


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _research_record(lead: dict) -> dict | None:
    note = _clean(lead.get("research_intelligence"))
    if not note.startswith("Leadkutatás;"):
        return None
    match = _COUNTRY_INDUSTRY.search(note)
    fit = _FIT.search(note)
    if not match or not fit:
        return None
    score = max(0, min(100, int(fit.group(1))))
    need = _NEED.search(note)
    return {
        "company": _clean(lead.get("company_name"))[:180],
        "country": _clean(match.group(1))[:100] or "Ismeretlen",
        "industry": _clean(match.group(2))[:120] or "Ismeretlen",
        "fit_score": score,
        "confidence": fit.group(2).lower(),
        "business_need": _clean(need.group(1))[:300] if need else "",
    }


def _aggregate(records: list[dict], dimension: str) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        groups[record[dimension] or "Ismeretlen"].append(record)
    output = []
    for name, items in groups.items():
        scores = [item["fit_score"] for item in items]
        high = sum(item["confidence"] == "high" for item in items)
        medium = sum(item["confidence"] == "medium" for item in items)
        output.append({
            "name": name,
            "sample_size": len(items),
            "average_fit_score": round(sum(scores) / len(scores), 1),
            "high_confidence_count": high,
            "medium_confidence_count": medium,
            "low_confidence_count": len(items) - high - medium,
            "strong_fit_count": sum(score >= 70 for score in scores),
            "evidence_strength": "erősebb" if high + medium >= max(2, len(items) * 0.6) else "korlátozott",
        })
    return sorted(output, key=lambda item: (item["average_fit_score"], item["sample_size"]), reverse=True)


def build_market_intelligence(leads: list[dict]) -> dict:
    """Summarize only saved, grounded research records; never mutates data."""
    records = [record for lead in leads if (record := _research_record(lead))]
    if not records:
        return {
            "research_record_count": 0,
            "message": "Még nincs elegendő strukturált, korábbi leadkutatási adat a piaci mintázatok elemzéséhez.",
            "industry_patterns": [],
            "country_patterns": [],
        }

    industries = _aggregate(records, "industry")
    countries = _aggregate(records, "country")
    overall = round(sum(item["fit_score"] for item in records) / len(records), 1)
    usable_industries = [item for item in industries if item["sample_size"] >= 2]
    usable_countries = [item for item in countries if item["sample_size"] >= 2]
    return {
        "research_record_count": len(records),
        "overall_average_business_fit": overall,
        "high_confidence_share_percent": round(
            100 * sum(item["confidence"] == "high" for item in records) / len(records), 1
        ),
        "industry_patterns": industries[:15],
        "country_patterns": countries[:15],
        "best_observed_industries_with_multiple_examples": usable_industries[:5],
        "best_observed_countries_with_multiple_examples": usable_countries[:5],
        "interpretation_limits": [
            "Leíró minta a korábban megtalált és elmentett cégekről, nem a teljes piac reprezentatív felmérése.",
            "Az átlagos üzleti illeszkedési pontszám AI-becslés, nem vásárlási szándék, fizetőképesség vagy konverziós arány.",
            "Két vagy több példa nélküli szegmens csak előzetes jelzés; kis elemszámnál a rangsor bizonytalan.",
            "A weboldal-információs pontszám ettől külön mérőszám, itt nem kerül felhasználásra.",
            "A hiányzó kutatási adat nem számít nulla pontnak.",
        ],
    }
