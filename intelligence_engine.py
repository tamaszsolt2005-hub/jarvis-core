"""Shared evidence and provenance contracts for the JARVIS Intelligence Engine.

This module normalizes existing domain evidence without inventing sources or
changing domain-specific scoring semantics. It has no database or provider I/O.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import urlparse


EVIDENCE_TYPES = frozenset({"supporting", "contradicting", "context"})
SOURCE_KINDS = frozenset({
    "company_dossier_fact",
    "company_dossier_leadership",
    "company_pain_hypothesis",
    "lead_research_note",
    "other",
})


def _text(value: Any, field: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ValueError(f"{field} must be a non-empty string of at most {limit} characters")
    return value.strip()


def _public_url(value: Any) -> str:
    raw = _text(value, "source_url", 2048)
    parsed = urlparse(raw)
    if (
        parsed.scheme not in {"http", "https"} or not parsed.hostname
        or parsed.username or parsed.password
        or parsed.hostname.casefold() in {"localhost", "localhost.localdomain"}
        or parsed.hostname.casefold().endswith((".localhost", ".local"))
    ):
        raise ValueError("source_url must be a public HTTP(S) URL")
    try:
        if not ipaddress.ip_address(parsed.hostname).is_global:
            raise ValueError("source_url must not target a private or reserved IP address")
    except ValueError as exc:
        if "private or reserved" in str(exc):
            raise
    return raw


def _timestamp(value: Any, field: str) -> str:
    if value in (None, ""):
        return "undated"
    raw = _text(value, field, 80)
    if raw == "undated":
        return raw
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp or undated") from exc
    if parsed.tzinfo is None and len(raw) != 10:
        raise ValueError(f"{field} must include a timezone")
    # Preserve the source representation for exact-match compatibility; the
    # value has still been parsed and validated as an ISO-8601 timestamp/date.
    return raw


@dataclass(frozen=True)
class EvidenceRecord:
    """Canonical source record shared by Lead, dossier and Opportunity domains."""

    source_url: str
    excerpt: str
    # Keep the original Opportunity Evidence positional field order compatible.
    observed_at: str = "undated"
    evidence_type: str = "supporting"
    source_kind: str = "other"
    captured_at: str = "undated"
    entity_type: str = "company"
    entity_id: str = ""
    snapshot_id: str = ""
    evidence_id: str = ""

    def to_dict(self) -> dict[str, str]:
        result = asdict(self)
        result["evidence_id"] = self.evidence_id or _fingerprint(result)
        return result

    @classmethod
    def from_dict(
        cls,
        raw: dict[str, Any],
        *,
        default_observed_at: Any = None,
        default_source_kind: str = "other",
        entity_type: str = "company",
        entity_id: str = "",
        snapshot_id: str = "",
    ) -> "EvidenceRecord":
        if not isinstance(raw, dict):
            raise ValueError("evidence must be an object")
        kind = _text(raw.get("evidence_type", "supporting"), "evidence_type", 40)
        if kind not in EVIDENCE_TYPES:
            raise ValueError("unsupported evidence_type")
        source_kind = _text(raw.get("source_kind", default_source_kind), "source_kind", 60)
        if source_kind not in SOURCE_KINDS:
            raise ValueError("unsupported source_kind")
        normalized = cls(
            source_url=_public_url(raw.get("source_url")),
            excerpt=_text(raw.get("excerpt"), "excerpt", 1200),
            source_kind=source_kind,
            observed_at=_timestamp(raw.get("observed_at") or default_observed_at, "observed_at"),
            captured_at=_timestamp(raw.get("captured_at") or default_observed_at, "captured_at"),
            evidence_type=kind,
            entity_type=_text(raw.get("entity_type", entity_type), "entity_type", 60),
            entity_id=_text(raw.get("entity_id", entity_id), "entity_id", 100) if raw.get("entity_id", entity_id) else "",
            snapshot_id=_text(raw.get("snapshot_id", snapshot_id), "snapshot_id", 100) if raw.get("snapshot_id", snapshot_id) else "",
        )
        return cls(**{**asdict(normalized), "evidence_id": _fingerprint(asdict(normalized))})


def _fingerprint(payload: dict[str, Any]) -> str:
    stable = {key: value for key, value in payload.items() if key != "evidence_id"}
    canonical = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def evidence_records_from_dossier(dossier: dict[str, Any]) -> list[dict[str, str]]:
    """Convert already-grounded dossier facts into canonical source records."""
    if not isinstance(dossier, dict):
        raise ValueError("dossier must be an object")
    researched_at = dossier.get("researched_at", "undated")
    snapshot_id = str(dossier.get("snapshot_id") or "")
    records: list[dict[str, str]] = []
    facts = dossier.get("facts", [])
    for fact in facts if isinstance(facts, list) else []:
        if not isinstance(fact, dict):
            continue
        record = EvidenceRecord.from_dict(
            {"source_url": fact.get("source_url"), "excerpt": fact.get("fact"),
             "source_kind": "company_dossier_fact"},
            default_observed_at=researched_at, default_source_kind="company_dossier_fact",
            entity_type="company", snapshot_id=snapshot_id,
        )
        records.append(record.to_dict())
    leader = dossier.get("decision_maker") or {}
    if isinstance(leader, dict) and leader.get("source_url"):
        excerpt = " – ".join(str(leader.get(key) or "").strip() for key in
                             ("name", "role", "professional_background") if leader.get(key))
        if excerpt:
            record = EvidenceRecord.from_dict(
                {"source_url": leader["source_url"], "excerpt": excerpt,
                 "source_kind": "company_dossier_leadership"},
                default_observed_at=researched_at, default_source_kind="company_dossier_leadership",
                entity_type="company", snapshot_id=snapshot_id,
            )
            records.append(record.to_dict())
    return records


def evidence_records_from_lead(lead: dict[str, Any]) -> list[dict[str, str]]:
    """Normalize only explicitly structured Lead sources; free-text notes are not sources."""
    if not isinstance(lead, dict):
        raise ValueError("lead must be an object")
    raw_sources = lead.get("research_evidence")
    if raw_sources is None:
        return []
    if not isinstance(raw_sources, list):
        raise ValueError("research_evidence must be a list")
    records: list[dict[str, str]] = []
    for raw in raw_sources:
        record = EvidenceRecord.from_dict(
            raw,
            default_observed_at=lead.get("researched_at") or lead.get("updated_at"),
            default_source_kind="lead_research_note",
            entity_type="lead",
            entity_id=str(lead.get("id") or ""),
        )
        records.append(record.to_dict())
    return records


def evidence_records_from_pains(pains: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    """Normalize Opportunity pain evidence without promoting hypotheses to facts."""
    records: list[dict[str, str]] = []
    for pain in pains:
        if not isinstance(pain, dict):
            continue
        pain_id = str(pain.get("id") or "")
        observed_at = pain.get("created_at") or pain.get("researched_at")
        for raw in pain.get("evidence", []) if isinstance(pain.get("evidence"), list) else []:
            record = EvidenceRecord.from_dict(
                raw, default_observed_at=observed_at,
                default_source_kind="company_pain_hypothesis",
                entity_type="company_pain_hypothesis", entity_id=pain_id,
            )
            records.append(record.to_dict())
    return records


def build_intelligence_snapshot(
    *,
    dossier_evidence: Iterable[dict[str, Any]] = (),
    pain_evidence: Iterable[dict[str, Any]] = (),
    lead_evidence: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Build a deterministic, deduplicated evidence view across JARVIS domains."""
    merged: dict[str, dict[str, str]] = {}
    for raw in (*list(dossier_evidence), *list(pain_evidence), *list(lead_evidence)):
        record = EvidenceRecord.from_dict(raw)
        merged[record.evidence_id or _fingerprint(asdict(record))] = record.to_dict()
    records = sorted(merged.values(), key=lambda item: (item["source_url"], item["evidence_id"]))
    return {
        "schema_version": 1,
        "evidence_count": len(records),
        "source_count": len({item["source_url"] for item in records}),
        "domain_count": len({(urlparse(item["source_url"]).hostname or "").casefold() for item in records}),
        "records": records,
    }
