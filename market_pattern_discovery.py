"""Source-grounded, deterministic cross-company pain clustering.

This module never invents evidence or validates a market pattern. It creates
candidate patterns and draft SaaS opportunities only; human review is required.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import Any


_STOPWORDS = frozenset({
    "the", "and", "for", "with", "from", "that", "this", "their", "they",
    "have", "has", "are", "was", "were", "into", "about", "company",
    "a", "an", "of", "to", "in", "on", "at", "by", "is", "it",
    "és", "vagy", "hogy", "a", "az", "egy", "ennek", "annak", "mint",
    "van", "vannak", "volt", "lettek", "nem", "is", "ezt", "azt",
    "cégek", "cég", "vállalat", "vállalatok", "számára", "miatt",
})
_CATEGORY_LABELS = {
    "operational_process": "Működési folyamat",
    "sales_marketing": "Értékesítési és marketing folyamat",
    "finance": "Pénzügyi folyamat",
    "customer_support": "Ügyfélszolgálati folyamat",
    "technology": "Technológiai folyamat",
    "compliance": "Megfelelőségi folyamat",
    "other": "Üzleti folyamat",
}


def _tokens(value: Any) -> set[str]:
    if not isinstance(value, str):
        return set()
    return {
        token for token in re.findall(r"[^\W_]{3,}", value.casefold(), flags=re.UNICODE)
        if token not in _STOPWORDS and not token.isdigit()
    }


def _pain_is_eligible(row: dict[str, Any]) -> bool:
    evidence = row.get("evidence")
    return (
        bool(row.get("id"))
        and bool(row.get("lead_id"))
        and row.get("status", "hypothesis") != "rejected"
        and isinstance(evidence, list)
        and any(
            isinstance(item, dict)
            and isinstance(item.get("source_url"), str)
            and item["source_url"].startswith(("https://", "http://"))
            and isinstance(item.get("excerpt"), str)
            and item["excerpt"].strip()
            for item in evidence
        )
    )


def build_cross_company_pattern_candidates(
    pains: list[dict[str, Any]],
    *,
    min_companies: int = 2,
    similarity_threshold: float = 0.45,
) -> list[dict[str, Any]]:
    """Build deterministic candidate clusters; no cluster is marked validated."""
    if isinstance(min_companies, bool) or not isinstance(min_companies, int) or min_companies < 2:
        raise ValueError("min_companies must be at least two")
    if isinstance(similarity_threshold, bool) or not isinstance(similarity_threshold, (int, float)) or not 0.1 <= similarity_threshold <= 1:
        raise ValueError("similarity_threshold must be between 0.1 and 1")

    eligible = []
    seen_ids = set()
    for row in pains:
        if not isinstance(row, dict) or not _pain_is_eligible(row):
            continue
        pain_id = str(row["id"])
        if pain_id in seen_ids:
            continue
        seen_ids.add(pain_id)
        tokens = _tokens(row.get("statement"))
        if len(tokens) < 2:
            continue
        eligible.append({**row, "_tokens": tokens, "_category": str(row.get("category") or "other")})

    adjacency = {str(row["id"]): set() for row in eligible}
    by_id = {str(row["id"]): row for row in eligible}
    for index, left in enumerate(eligible):
        for right in eligible[index + 1:]:
            if left["_category"] != right["_category"] or left.get("lead_id") == right.get("lead_id"):
                continue
            common = left["_tokens"] & right["_tokens"]
            union = left["_tokens"] | right["_tokens"]
            similarity = len(common) / len(union) if union else 0.0
            if len(common) >= 2 and similarity >= similarity_threshold:
                left_id, right_id = str(left["id"]), str(right["id"])
                adjacency[left_id].add(right_id)
                adjacency[right_id].add(left_id)

    components = []
    visited = set()
    for pain_id in sorted(adjacency):
        if pain_id in visited or not adjacency[pain_id]:
            continue
        stack = [pain_id]
        component_ids = []
        visited.add(pain_id)
        while stack:
            current = stack.pop()
            component_ids.append(current)
            for neighbour in sorted(adjacency[current]):
                if neighbour not in visited:
                    visited.add(neighbour)
                    stack.append(neighbour)
        component = [by_id[item] for item in sorted(component_ids)]
        if len({str(item.get("lead_id")) for item in component}) < min_companies:
            continue
        term_counts = Counter(token for item in component for token in item["_tokens"])
        min_frequency = max(2, math.ceil(len(component) * 0.6))
        shared_terms = sorted(
            (term for term, count in term_counts.items() if count >= min_frequency),
            key=lambda term: (-term_counts[term], term),
        )[:6]
        if len(shared_terms) < 2:
            continue
        category = component[0]["_category"]
        title = f"{_CATEGORY_LABELS.get(category, _CATEGORY_LABELS['other'])}: {' / '.join(shared_terms[:3])}"
        fingerprint_payload = category + "|" + "|".join(sorted(shared_terms))
        fingerprint = hashlib.sha256(fingerprint_payload.encode("utf-8")).hexdigest()
        statements = sorted({str(item.get("statement") or "").strip() for item in component})
        description = "Több vállalathoz kötött, forrásolt problémahipotézisek: " + " | ".join(statements)
        description = description[:1600]
        confidence = round(sum(float(item.get("confidence") or 0) for item in component) / len(component), 3)
        components.append({
            "fingerprint": fingerprint,
            "title": title[:240],
            "description": description,
            "confidence": min(0.75, max(0.1, confidence)),
            "status": "candidate",
            "company_pain_ids": [str(item["id"]) for item in component],
            "company_ids": sorted({str(item["lead_id"]) for item in component}),
            "saas_name": f"{title[:180]} – SaaS-jelölt"[:240],
            "saas_summary": (
                "Vizsgálatra váró termékhipotézis a kapcsolt vállalati problémák alapján. "
                "A fizetési hajlandóság és a tényleges kereslet még nincs igazolva."
            ),
        })
    return sorted(components, key=lambda item: (item["fingerprint"], item["title"]))


def _rows(response: Any, *, operation: str) -> list[dict[str, Any]]:
    rows = getattr(response, "data", None)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise RuntimeError(f"Unexpected database response while {operation}.")
    return rows


def persist_company_pain_hypotheses(
    db: Any,
    *,
    lead_id: str,
    snapshot_id: str,
    hypotheses: list[dict[str, Any]],
) -> int:
    """Persist validated dossier hypotheses once per immutable research snapshot."""
    if not hypotheses:
        return 0
    existing = _rows(
        db.table("business_pain_hypotheses")
        .select("id,statement")
        .eq("lead_id", lead_id)
        .eq("snapshot_id", snapshot_id)
        .execute(),
        operation="checking existing company pain hypotheses",
    )
    if existing:
        return 0
    rows = []
    for item in hypotheses[:8]:
        if not isinstance(item, dict):
            continue
        row = {
            "lead_id": lead_id,
            "snapshot_id": snapshot_id,
            "statement": str(item.get("statement") or "")[:1200],
            "category": str(item.get("category") or "other"),
            "confidence": float(item.get("confidence") or 0.1),
            "status": "hypothesis",
            "evidence": item.get("evidence") if isinstance(item.get("evidence"), list) else [],
        }
        if row["statement"] and row["evidence"]:
            rows.append(row)
    if not rows:
        return 0
    try:
        db.table("business_pain_hypotheses").insert(rows).execute()
        return len(rows)
    except Exception:
        # A concurrent replay can win the snapshot-scoped unique constraint.
        existing_after_race = _rows(
            db.table("business_pain_hypotheses")
            .select("id")
            .eq("lead_id", lead_id)
            .eq("snapshot_id", snapshot_id)
            .execute(),
            operation="checking concurrently persisted company pain hypotheses",
        )
        if len(existing_after_race) >= len(rows):
            return 0
        raise


def discover_market_patterns(db: Any, *, pain_limit: int = 2000) -> dict[str, int]:
    """Persist candidate patterns and draft product ideas from source-backed pains."""
    if isinstance(pain_limit, bool) or not isinstance(pain_limit, int) or not 1 <= pain_limit <= 10000:
        raise ValueError("pain_limit must be between 1 and 10000")
    pains = _rows(
        db.table("business_pain_hypotheses")
        .select("id,lead_id,statement,category,confidence,status,evidence,created_at")
        .order("created_at", desc=True)
        .limit(pain_limit)
        .execute(),
        operation="loading company pain hypotheses",
    )
    candidates = build_cross_company_pattern_candidates(pains)
    patterns_created = links_created = opportunities_created = 0
    for candidate in candidates:
        existing_patterns = _rows(
            db.table("market_problem_patterns")
            .select("id,fingerprint")
            .eq("fingerprint", candidate["fingerprint"])
            .limit(1)
            .execute(),
            operation="checking existing market pattern",
        )
        if existing_patterns:
            pattern_id = str(existing_patterns[0]["id"])
        else:
            inserted = _rows(
                db.table("market_problem_patterns")
                .insert({
                    "fingerprint": candidate["fingerprint"],
                    "title": candidate["title"],
                    "description": candidate["description"],
                    "confidence": candidate["confidence"],
                    "status": "candidate",
                })
                .execute(),
                operation="creating market pattern candidate",
            )
            if not inserted:
                raise RuntimeError("Market pattern insert returned no row.")
            pattern_id = str(inserted[0]["id"])
            patterns_created += 1

        existing_links = _rows(
            db.table("market_pattern_pains")
            .select("company_pain_id")
            .eq("market_pattern_id", pattern_id)
            .execute(),
            operation="loading market pattern evidence links",
        )
        linked_ids = {str(item.get("company_pain_id")) for item in existing_links}
        for pain_id in candidate["company_pain_ids"]:
            if pain_id not in linked_ids:
                db.table("market_pattern_pains").insert({
                    "market_pattern_id": pattern_id,
                    "company_pain_id": pain_id,
                }).execute()
                links_created += 1

        existing_opportunities = _rows(
            db.table("saas_opportunities")
            .select("id")
            .eq("discovery_fingerprint", candidate["fingerprint"])
            .limit(1)
            .execute(),
            operation="checking existing SaaS candidate",
        )
        if not existing_opportunities:
            db.table("saas_opportunities").insert({
                "market_pattern_id": pattern_id,
                "discovery_fingerprint": candidate["fingerprint"],
                "name": candidate["saas_name"],
                "summary": candidate["saas_summary"],
                "status": "draft",
            }).execute()
            opportunities_created += 1
    return {
        "pain_hypotheses": len(pains),
        "pattern_candidates": len(candidates),
        "patterns_created": patterns_created,
        "evidence_links_created": links_created,
        "saas_candidates_created": opportunities_created,
    }
