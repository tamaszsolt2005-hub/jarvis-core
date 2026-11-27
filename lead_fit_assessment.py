"""Strict, grounding-backed lead-fit assessment contract."""
from __future__ import annotations
import math
import re
from typing import Any
from urllib.parse import urlparse

ASSESSMENT_VERSION = "1.0"

def _text(value: Any, limit: int = 1200) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()[:limit]

def _url_key(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) > 2048:
        return None
    try:
        p = urlparse(value)
        if p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password:
            return None
        host = p.hostname.casefold()
        port = p.port
        if port and not ((p.scheme == "http" and port == 80) or (p.scheme == "https" and port == 443)):
            host = f"{host}:{port}"
        return f"{p.scheme.casefold()}://{host}{p.path or '/'}" + (f"?{p.query}" if p.query else "")
    except ValueError:
        return None

def _number(value: Any, low: float, high: float, field: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"invalid_assessment_{field}")
    try:
        finite = math.isfinite(value)
    except (OverflowError, TypeError, ValueError):
        finite = False
    if not finite or not low <= value <= high:
        raise ValueError(f"invalid_assessment_{field}")
    return value

def validate_lead_fit_assessment(raw: Any, grounding_sources: list[dict[str, str]]) -> dict[str, Any]:
    """Accept evidence only when its exact page URL is present in provider grounding metadata."""
    if not isinstance(raw, dict) or raw.get("assessment_version") != ASSESSMENT_VERSION:
        raise ValueError("unsupported_assessment_version")
    sources: dict[str, dict[str, str]] = {}
    for source in grounding_sources:
        if not isinstance(source, dict):
            continue
        key = _url_key(source.get("source_url"))
        if key and key not in sources:
            sources[key] = {
                "source_url": source["source_url"],
                "title": _text(source.get("title"), 300),
                "snippet": _text(source.get("snippet"), 1200),
            }
    raw_evidence = raw.get("evidence")
    if not isinstance(raw_evidence, list):
        raise ValueError("invalid_assessment_evidence")
    evidence, seen = [], set()
    for item in raw_evidence[:20]:
        if not isinstance(item, dict):
            continue
        key, claim, kind = _url_key(item.get("source_url")), _text(item.get("claim")), item.get("evidence_type")
        if not key or key not in sources or not claim or kind not in {"fact", "hypothesis", "assessment"}:
            continue
        if (key, claim.casefold()) in seen:
            continue
        seen.add((key, claim.casefold()))
        evidence.append({**sources[key], "claim": claim, "evidence_type": kind})
    def string_list(name: str) -> list[str]:
        values = raw.get(name)
        if not isinstance(values, list):
            raise ValueError(f"invalid_assessment_{name}")
        return [v for v in (_text(x, 500) for x in values[:12]) if v]
    rationale, next_step = _text(raw.get("rationale")), _text(raw.get("recommended_next_step"), 500)
    if not rationale or not next_step:
        raise ValueError("invalid_assessment_narrative")
    risks = string_list("risk_signals")
    fits = string_list("fit_signals")
    if not evidence:
        return {"assessment_version": ASSESSMENT_VERSION, "status": "insufficient_evidence",
                "fit_score": None, "confidence": None, "rationale": rationale,
                "fit_signals": [], "risk_signals": risks,
                "recommended_next_step": next_step, "evidence": []}
    return {"assessment_version": ASSESSMENT_VERSION, "status": "assessed",
            "fit_score": _number(raw.get("fit_score"), 0, 100, "fit_score"),
            "confidence": _number(raw.get("confidence"), 0, 1, "confidence"),
            "rationale": rationale, "fit_signals": fits, "risk_signals": risks,
            "recommended_next_step": next_step, "evidence": evidence}
