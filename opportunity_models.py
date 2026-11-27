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
