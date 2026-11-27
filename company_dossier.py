"""Validated, source-grounded company dossier helpers.

The dossier intentionally stores business facts and public professional context only.
It never collects private contact details or grants outreach permission.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from urllib.parse import urlparse

from intelligence_engine import evidence_records_from_dossier


_ALLOWED_FACT_CATEGORIES = {
    "business_model",
    "products_services",
    "customer_segments",
    "markets",
    "growth_signal",
    "technology_signal",
    "operational_process",
    "leadership",
    "public_news",
}


def _text(value: Any, limit: int = 260) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _url(value: Any) -> str | None:
    raw = _text(value, 2048)
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.hostname.casefold() in {"localhost", "localhost.localdomain"}
        or parsed.hostname.casefold().endswith((".localhost", ".local"))
    ):
        return None
    try:
        if not ipaddress.ip_address(parsed.hostname).is_global:
            return None
    except ValueError:
        pass
    return raw


def _domain(value: str) -> str:
    return (urlparse(value).hostname or "").casefold().removeprefix("www.")


def _grounding_key(value: str) -> str | None:
    """Normalize a source URL for exact-page comparison with Google grounding."""
    try:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        host = parsed.hostname.casefold()
        port = parsed.port
        if port and not ((parsed.scheme == "http" and port == 80) or (parsed.scheme == "https" and port == 443)):
            host = f"{host}:{port}"
        return f"{parsed.scheme.casefold()}://{host}{parsed.path or '/'}" + (
            f"?{parsed.query}" if parsed.query else ""
        )
    except ValueError:
        return None


def build_company_dossier(
    item: dict[str, Any], grounded_sources: set[str] | list[dict[str, str]]
) -> dict[str, Any]:
    """Keep only facts and assessments backed by exact Google grounding URLs."""
    grounded_keys = set()
    for value in grounded_sources:
        source_url = value.get("source_url") if isinstance(value, dict) else value
        if isinstance(source_url, str) and (key := _grounding_key(source_url)):
            grounded_keys.add(key)
    raw_facts = item.get("company_facts")
    facts: list[dict[str, str]] = []
    if isinstance(raw_facts, list):
        for raw in raw_facts[:12]:
            if not isinstance(raw, dict):
                continue
            category = _text(raw.get("category"), 40).casefold()
            fact = _text(raw.get("fact"), 260)
            source_url = _url(raw.get("source_url"))
            if (
                category not in _ALLOWED_FACT_CATEGORIES
                or not fact
                or not source_url
                or _grounding_key(source_url) not in grounded_keys
            ):
                continue
            facts.append({
                "category": category,
                "fact": fact,
                "source_url": source_url,
            })

    pain_hypotheses: list[dict[str, Any]] = []
    raw_pains = item.get("pain_hypotheses")
    allowed_pain_categories = {
        "operational_process", "sales_marketing", "finance",
        "customer_support", "technology", "compliance", "other",
    }
    if isinstance(raw_pains, list):
        for raw in raw_pains[:8]:
            if not isinstance(raw, dict):
                continue
            statement = _text(raw.get("statement"), 600)
            category = _text(raw.get("category"), 40).casefold()
            excerpt = _text(raw.get("excerpt"), 1200)
            source_url = _url(raw.get("source_url"))
            confidence = raw.get("confidence", 0.55)
            if (
                not statement or not excerpt or category not in allowed_pain_categories
                or not source_url or _grounding_key(source_url) not in grounded_keys
                or isinstance(confidence, bool) or not isinstance(confidence, (int, float))
                or not 0.1 <= confidence <= 0.75
            ):
                continue
            pain_hypotheses.append({
                "statement": statement,
                "category": category,
                "confidence": float(confidence),
                "evidence": [{
                    "source_url": source_url,
                    "excerpt": excerpt,
                    "evidence_type": "supporting",
                }],
            })

    leader: dict[str, str] = {}
    raw_leader = item.get("decision_maker")
    if isinstance(raw_leader, dict):
        source_url = _url(raw_leader.get("source_url"))
        role = _text(raw_leader.get("role"), 100)
        name = _text(raw_leader.get("name"), 100)
        background = _text(raw_leader.get("professional_background"), 260)
        if source_url and _grounding_key(source_url) in grounded_keys and (role or name or background):
            leader = {
                "name": name,
                "role": role,
                "professional_background": background,
                "source_url": source_url,
            }

    result = {"facts": facts[:8], "decision_maker": leader}
    if pain_hypotheses:
        result["pain_hypotheses"] = pain_hypotheses
    assessment = item.get("lead_fit_assessment")
    if isinstance(assessment, dict):
        from lead_fit_assessment import validate_lead_fit_assessment
        result["lead_fit_assessment"] = validate_lead_fit_assessment(
            assessment, [x for x in grounded_sources if isinstance(x, dict)])
    return result


def render_company_dossier(dossier: dict[str, Any], max_chars: int = 1250) -> str:
    """Render a compact, auditable dossier fragment for the existing lead notes field."""
    lines: list[str] = []
    leader = dossier.get("decision_maker") or {}
    if leader:
        identity = " – ".join(part for part in (leader.get("name"), leader.get("role")) if part)
        if identity:
            lines.append(f"Nyilvános szakmai döntéshozó: {identity}.")
        if leader.get("professional_background"):
            lines.append(f"Szakmai háttér: {leader['professional_background']}.")
        if leader.get("source_url"):
            lines.append(f"Vezetői forrás: {leader['source_url']}")
    for fact in dossier.get("facts", []):
        line = f"[{fact['category']}] {fact['fact']} (forrás: {fact['source_url']})"
        lines.append(line)
    selected: list[str] = []
    remaining = max(0, int(max_chars))
    for line in lines:
        separator = 3 if selected else 0
        if len(line) + separator > remaining:
            break
        selected.append(line)
        remaining -= len(line) + separator
    return " | ".join(selected)



def stamp_company_dossier(dossier: dict[str, Any]) -> dict[str, Any]:
    """Attach immutable snapshot metadata without changing the research facts."""
    content = {
        "facts": dossier.get("facts", []),
        "decision_maker": dossier.get("decision_maker", {}),
    }
    if dossier.get("pain_hypotheses"):
        content["pain_hypotheses"] = dossier["pain_hypotheses"]
    if dossier.get("lead_fit_assessment"):
        content["lead_fit_assessment"] = dossier["lead_fit_assessment"]
    canonical = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    stamped = dict(content)
    stamped.update({
        "schema_version": 1,
        "snapshot_id": str(uuid4()),
        "researched_at": datetime.now(timezone.utc).isoformat(),
        "content_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    })
    # Keep the original dossier contract intact while exposing a shared,
    # source-traceable view for cross-domain Intelligence Engine consumers.
    stamped["evidence_records"] = evidence_records_from_dossier(stamped)
    return stamped

def is_company_dossier_stale(
    dossier: dict[str, Any],
    *,
    max_age_days: int = 30,
    now: datetime | None = None,
) -> bool:
    """Return whether a dossier needs refresh; malformed or future timestamps fail closed."""
    if isinstance(max_age_days, bool) or not isinstance(max_age_days, int) or max_age_days < 0:
        raise ValueError("max_age_days must be a non-negative integer")
    raw_timestamp = dossier.get("researched_at")
    if not isinstance(raw_timestamp, str) or not raw_timestamp.strip():
        return True
    try:
        researched_at = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
        if researched_at.tzinfo is None:
            return True
        reference_time = now or datetime.now(timezone.utc)
        if reference_time.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        age_seconds = (reference_time.astimezone(timezone.utc) - researched_at.astimezone(timezone.utc)).total_seconds()
    except (TypeError, ValueError, OverflowError):
        return True
    if age_seconds < 0:
        return True
    return age_seconds >= max_age_days * 86400
