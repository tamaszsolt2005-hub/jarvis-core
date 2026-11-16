"""Read-only learning insights from explicit memories and grounded lead research."""
from __future__ import annotations

import re
import unicodedata
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


def _normalise(value: str) -> str:
    value = unicodedata.normalize("NFKD", (value or "").casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _decision_matches(decision: str, recorded: str) -> bool:
    """Conservative text match; outcome links require a decision field explicitly saved."""
    left, right = _normalise(decision), _normalise(recorded)
    if not left or not right:
        return False
    if left == right:
        return True
    a, b = {x for x in left.split() if len(x) >= 4}, {x for x in right.split() if len(x) >= 4}
    return bool(a and b and len(a & b) / len(a | b) >= 0.75)


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
    parsed_outcomes: list[dict[str, str]] = []

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
            parsed_outcomes.append({
                "decision": decision, "method": method, "industry": industry,
                "polarity": polarity, "result": result, "record": content,
            })
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

    # Connect only explicitly recorded decision fields; no inferred causality.
    decision_outcome_links = []
    for decision in decisions[-20:]:
        linked = [item for item in parsed_outcomes if item["decision"] and _decision_matches(decision, item["decision"])]
        if linked:
            decision_outcome_links.append({
                "decision": decision,
                "linked_outcome_count": len(linked),
                "positive": sum(item["polarity"] == "positive" for item in linked),
                "negative": sum(item["polarity"] == "negative" for item in linked),
                "unclassified": sum(item["polarity"] == "unclassified" for item in linked),
                "evidence": [item["record"] for item in linked[-5:]],
                "interpretation": "Kifejezetten ehhez a döntéshez címkézett tapasztalatok; együttjárás, nem bizonyított okság.",
            })

    # Repeated patterns are descriptive groupings, not causal success rates.
    pattern_groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for item in parsed_outcomes:
        if item["method"] or item["industry"]:
            pattern_groups[(item["industry"], item["method"])].append(item)
    repeated_outcome_patterns = [
        {
            "industry": industry or "Nincs megadva",
            "method": method or "Nincs megadva",
            "record_count": len(items),
            "positive": sum(item["polarity"] == "positive" for item in items),
            "negative": sum(item["polarity"] == "negative" for item in items),
            "unclassified": sum(item["polarity"] == "unclassified" for item in items),
            "evidence": [item["record"] for item in items[-3:]],
        }
        for (industry, method), items in sorted(pattern_groups.items(), key=lambda pair: len(pair[1]), reverse=True)
        if len(items) >= 2
    ][:10]

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
        "decision_outcome_links": decision_outcome_links,
        "repeated_outcome_patterns": repeated_outcome_patterns,
        "recorded_decisions": decisions[-20:],
        "recorded_outcomes": outcomes[-30:],
        "recorded_lessons": lessons[-20:],
        "interpretation": (
            "A kutatási iparágak és módszerek rangsora a mentett cégek üzleti illeszkedési becslését mutatja, "
            "nem bizonyított konverziót. Módszer vagy iparág csak akkor számít eredményesnek vagy sikertelennek, "
            "ha ezt a felhasználó kifejezetten rögzítette eredményként. A döntés-eredmény kapcsolat kizárólag "
            "az eredményrekordban explicit módon megadott döntésmező alapján készül; a szöveges hasonlóság "
            "csak konzervatív egyezéskeresés, nem oksági bizonyíték. A nem egyértelmű eredmények külön maradnak."
        ),
    }
