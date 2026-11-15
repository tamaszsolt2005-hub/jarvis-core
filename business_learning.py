"""Read-only learning insights from explicit memories and grounded lead research."""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any


def _tag(text: str, name: str) -> str:
    match = re.search(rf"(?:^|[;|,])\s*{re.escape(name)}\s*[:=]\s*([^;|,]+)", text, re.I)
    return re.sub(r"\s+", " ", match.group(1)).strip()[:160] if match else ""


def _research_method(note: str) -> str:
    explicit = _tag(note, "kutatási módszer")
    return explicit or "Google Search grounding + hivatalos weboldal és forrás-keresztellenőrzés"


def _outcome_polarity(result: str) -> str:
    """Classify only clearly stated outcomes; negation always takes precedence."""
    value = re.sub(r"\s+", " ", (result or "").casefold()).strip()
    negative = (
        r"\bsikertelen\b", r"\bnem (?:volt )?(?:sikeres|működött|mukodott|hozott|teljesült|teljesult)",
        r"\bnem hozott (?:eredményt|eredmenyt)\b", r"\bveszteség\b",
        r"\bveszteseg\b", r"\belmaradt\b", r"\bromlott\b",
    )
    if any(re.search(pattern, value) for pattern in negative):
        return "negative"
    positive = (
        r"\bsikeres\b", r"\bműködött\b", r"\bmukodott\b",
        r"\bhozott eredményt\b", r"\bhozott eredmenyt\b",
        r"\bnyereség\b", r"\bnyereseg\b", r"\bbevétel nőtt\b",
        r"\bkonverzió nőtt\b", r"\bkonverzio nott\b",
    )
    if any(re.search(pattern, value) for pattern in positive):
        return "positive"
    return "unclassified"


def build_business_learning(memories: list[dict[str, Any]], leads: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize only saved research and explicitly recorded decisions/outcomes/lessons."""
    industry_groups: dict[str, list[int]] = defaultdict(list)
    method_groups: dict[str, list[int]] = defaultdict(list)
    for lead in leads:
        note = str(lead.get("research_intelligence") or lead.get("notes") or "")
        if not note.startswith("Leadkutatás;"):
            continue
        industry_match = re.search(r"iparág:\s*(.*?)(?:\.\s|;)", note, re.I)
        industry = industry_match.group(1).strip() if industry_match else "Ismeretlen"
        fit_match = re.search(r"AI üzleti illeszkedési becslés:\s*(\d{1,3})/100", note, re.I)
        if not fit_match:
            continue
        score = max(0, min(100, int(fit_match.group(1))))
        industry_groups[industry].append(score)
        method_groups[_research_method(note)].append(score)

    outcomes, decisions, lessons = [], [], []
    successful_methods: dict[str, list[str]] = defaultdict(list)
    successful_industries: dict[str, list[str]] = defaultdict(list)
    successful_decisions: dict[str, list[str]] = defaultdict(list)
    unsuccessful_methods: dict[str, list[str]] = defaultdict(list)
    unsuccessful_industries: dict[str, list[str]] = defaultdict(list)
    unsuccessful_decisions: dict[str, list[str]] = defaultdict(list)
    polarity_counts = {"positive": 0, "negative": 0, "unclassified": 0}

    for item in memories:
        category = str(item.get("category") or "")
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        if category == "decision":
            decisions.append(content)
        elif category == "lesson":
            lessons.append(content)
        elif category == "outcome":
            outcomes.append(content)
            method = _tag(content, "módszer") or _tag(content, "kutatási módszer")
            industry = _tag(content, "iparág") or _tag(content, "szektor")
            decision = _tag(content, "döntés") or _tag(content, "dontes")
            result = _tag(content, "eredmény") or _tag(content, "eredmeny") or content
            polarity = _outcome_polarity(result)
            polarity_counts[polarity] += 1
            if polarity == "positive":
                if method:
                    successful_methods[method].append(content)
                if industry:
                    successful_industries[industry].append(content)
                if decision:
                    successful_decisions[decision].append(content)
            elif polarity == "negative":
                if method:
                    unsuccessful_methods[method].append(content)
                if industry:
                    unsuccessful_industries[industry].append(content)
                if decision:
                    unsuccessful_decisions[decision].append(content)

    def summarize(groups: dict[str, list[int]]) -> list[dict[str, Any]]:
        return [
            {"name": name, "sample_size": len(scores), "average_fit_score": round(sum(scores) / len(scores), 1)}
            for name, scores in sorted(groups.items(), key=lambda pair: (sum(pair[1]) / len(pair[1]), len(pair[1])), reverse=True)
        ]

    def outcome_summary(groups: dict[str, list[str]]) -> list[dict[str, Any]]:
        return [
            {"name": name, "recorded_outcomes": len(items)}
            for name, items in sorted(groups.items(), key=lambda pair: len(pair[1]), reverse=True)
        ]

    return {
        "research_record_count": sum(len(values) for values in industry_groups.values()),
        "observed_industries": summarize(industry_groups)[:12],
        "observed_research_methods": summarize(method_groups)[:8],
        "outcome_record_count": len(outcomes),
        "outcome_polarity_counts": polarity_counts,
        "explicitly_successful_methods": outcome_summary(successful_methods),
        "explicitly_successful_decisions": outcome_summary(successful_decisions),
        "explicitly_successful_industries": outcome_summary(successful_industries),
        "explicitly_unsuccessful_methods": outcome_summary(unsuccessful_methods),
        "explicitly_unsuccessful_decisions": outcome_summary(unsuccessful_decisions),
        "explicitly_unsuccessful_industries": outcome_summary(unsuccessful_industries),
        "recorded_decisions": decisions[-20:],
        "recorded_outcomes": outcomes[-30:],
        "recorded_lessons": lessons[-20:],
        "interpretation": (
            "A kutatási iparágak és módszerek rangsora a mentett cégek üzleti illeszkedési becslését mutatja, "
            "nem bizonyított konverziót. Módszer vagy iparág csak akkor számít eredményesnek vagy sikertelennek, "
            "ha ezt a felhasználó kifejezetten rögzítette eredményként. A nem egyértelmű eredmények külön "
            "kategóriában maradnak. Döntés és eredmény között oksági kapcsolatot a rendszer nem talál ki."
        ),
    }
