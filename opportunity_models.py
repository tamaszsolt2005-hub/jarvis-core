"""Typed, source-traceable contracts for the JARVIS Opportunity Center.

This module validates records only; it performs no inference, persistence, or network I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


def _required_text(value: Any, field: str, limit: int = 500) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ValueError(f"{field} must be a non-empty string of at most {limit} characters")
    return value.strip()


def _confidence(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise ValueError("confidence must be a number between 0 and 1")
    return float(value)


def _source_url(value: Any) -> str:
    raw = _required_text(value, "source_url", 2048)
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("source_url must be a public HTTP(S) URL")
    return raw


@dataclass(frozen=True)
class Evidence:
    source_url: str
    excerpt: str
    observed_at: str
    evidence_type: str = "supporting"

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Evidence":
        if not isinstance(raw, dict):
            raise ValueError("evidence must be an object")
        kind = _required_text(raw.get("evidence_type", "supporting"), "evidence_type", 40)
        if kind not in {"supporting", "contradicting", "context"}:
            raise ValueError("unsupported evidence_type")
        return cls(
            source_url=_source_url(raw.get("source_url")),
            excerpt=_required_text(raw.get("excerpt"), "excerpt", 1200),
            observed_at=_required_text(raw.get("observed_at"), "observed_at", 80),
            evidence_type=kind,
        )


@dataclass(frozen=True)
class CompanyPain:
    id: str
    company_id: str
    statement: str
    confidence: float
    evidence: tuple[Evidence, ...]
    status: str = "hypothesis"

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "CompanyPain":
        if not isinstance(raw, dict):
            raise ValueError("company pain must be an object")
        status = _required_text(raw.get("status", "hypothesis"), "status", 40)
        if status not in {"hypothesis", "under_review", "supported", "rejected"}:
            raise ValueError("unsupported company pain status")
        evidence = raw.get("evidence")
        if not isinstance(evidence, list):
            raise ValueError("evidence must be a list")
        return cls(
            id=_required_text(raw.get("id"), "id", 80),
            company_id=_required_text(raw.get("company_id"), "company_id", 80),
            statement=_required_text(raw.get("statement"), "statement", 1200),
            confidence=_confidence(raw.get("confidence")),
            evidence=tuple(Evidence.from_dict(item) for item in evidence),
            status=status,
        )


@dataclass(frozen=True)
class MarketPattern:
    id: str
    title: str
    company_pain_ids: tuple[str, ...]
    confidence: float
    status: str = "candidate"

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "MarketPattern":
        if not isinstance(raw, dict):
            raise ValueError("market pattern must be an object")
        linked = raw.get("company_pain_ids")
        if not isinstance(linked, list) or not linked or any(not isinstance(item, str) or not item for item in linked):
            raise ValueError("market pattern must link to at least one company pain")
        status = _required_text(raw.get("status", "candidate"), "status", 40)
        if status not in {"candidate", "under_review", "validated", "rejected"}:
            raise ValueError("unsupported market pattern status")
        return cls(
            id=_required_text(raw.get("id"), "id", 80),
            title=_required_text(raw.get("title"), "title", 240),
            company_pain_ids=tuple(dict.fromkeys(linked)),
            confidence=_confidence(raw.get("confidence")),
            status=status,
        )


@dataclass(frozen=True)
class SaaSOpportunity:
    id: str
    market_pattern_id: str
    name: str
    summary: str
    status: str = "draft"

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "SaaSOpportunity":
        if not isinstance(raw, dict):
            raise ValueError("SaaS opportunity must be an object")
        status = _required_text(raw.get("status", "draft"), "status", 40)
        if status not in {"draft", "under_review", "shortlisted", "rejected"}:
            raise ValueError("unsupported SaaS opportunity status")
        return cls(
            id=_required_text(raw.get("id"), "id", 80),
            market_pattern_id=_required_text(raw.get("market_pattern_id"), "market_pattern_id", 80),
            name=_required_text(raw.get("name"), "name", 240),
            summary=_required_text(raw.get("summary"), "summary", 1600),
            status=status,
        )


OPPORTUNITY_SCORE_WEIGHTS = {
    "problem_evidence": 0.25,
    "business_value": 0.20,
    "willingness_to_pay": 0.15,
    "feasibility": 0.15,
    "reusability": 0.15,
    "risk": 0.10,
}


def calculate_opportunity_score(scores: dict[str, Any]) -> float | None:
    """Return a 0-100 score, or None until all dimensions have evidence.

    Risk is reverse-scored: higher risk lowers the final opportunity score.
    Missing dimensions are never silently treated as zero.
    """
    if not isinstance(scores, dict):
        raise ValueError("scores must be an object")
    if any(key not in scores or scores[key] is None for key in OPPORTUNITY_SCORE_WEIGHTS):
        return None
    values: dict[str, float] = {}
    for key in OPPORTUNITY_SCORE_WEIGHTS:
        value = scores[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
            raise ValueError(f"{key} must be a number between 0 and 100")
        values[key] = float(value)
    total = (
        values["problem_evidence"] * 0.25
        + values["business_value"] * 0.20
        + values["willingness_to_pay"] * 0.15
        + values["feasibility"] * 0.15
        + values["reusability"] * 0.15
        + (100 - values["risk"]) * 0.10
    )
    return round(total, 2)


SCORE_EVIDENCE_DIMENSIONS = tuple(OPPORTUNITY_SCORE_WEIGHTS)


def validate_opportunity_score_evidence(
    raw: dict[str, Any],
    company_pains: list[dict[str, Any]],
) -> dict[str, list[dict[str, str]]]:
    """Validate that every scored dimension cites evidence already stored on a company pain.

    This is deliberately a validator, not an inference engine: it never creates
    evidence, changes scores, or treats a hypothesis as a proven customer fact.
    """
    if not isinstance(raw, dict):
        raise ValueError("score_evidence must be an object")
    if not isinstance(company_pains, list):
        raise ValueError("company_pains must be a list")

    evidence_by_pain: dict[str, set[tuple[str, str, str, str]]] = {}
    for pain_raw in company_pains:
        pain = CompanyPain.from_dict(pain_raw)
        evidence_by_pain[pain.id] = {
            (item.source_url, item.excerpt, item.observed_at, item.evidence_type)
            for item in pain.evidence
        }

    validated: dict[str, list[dict[str, str]]] = {}
    for dimension in SCORE_EVIDENCE_DIMENSIONS:
        references = raw.get(dimension)
        if not isinstance(references, list) or not references:
            raise ValueError(f"{dimension} requires at least one source evidence reference")
        normalized: list[dict[str, str]] = []
        seen: set[tuple[str, str, str, str, str]] = set()
        for reference in references:
            if not isinstance(reference, dict):
                raise ValueError(f"{dimension} evidence references must be objects")
            pain_id = _required_text(reference.get("pain_hypothesis_id"), "pain_hypothesis_id", 80)
            if pain_id not in evidence_by_pain:
                raise ValueError(f"{dimension} references an unknown company pain")
            evidence = Evidence.from_dict(reference)
            exact_reference = (
                evidence.source_url, evidence.excerpt,
                evidence.observed_at, evidence.evidence_type,
            )
            if exact_reference not in evidence_by_pain[pain_id]:
                raise ValueError(
                    f"{dimension} evidence must exactly match a stored company-pain source"
                )
            dedupe_key = (pain_id, *exact_reference)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            normalized.append({
                "pain_hypothesis_id": pain_id,
                "source_url": evidence.source_url,
                "excerpt": evidence.excerpt,
                "observed_at": evidence.observed_at,
                "evidence_type": evidence.evidence_type,
            })
        validated[dimension] = normalized
    return validated
