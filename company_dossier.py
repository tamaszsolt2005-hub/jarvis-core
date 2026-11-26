"""Validated, source-grounded company dossier helpers.

The dossier intentionally stores business facts and public professional context only.
It never collects private contact details or grants outreach permission.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse


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
    ):
        return None
    return raw


def _domain(value: str) -> str:
    return (urlparse(value).hostname or "").casefold().removeprefix("www.")


def build_company_dossier(
    item: dict[str, Any], grounded_domains: set[str]
) -> dict[str, Any]:
    """Keep only concise facts whose cited domains are in Google grounding metadata."""
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
                or _domain(source_url) not in grounded_domains
            ):
                continue
            facts.append({
                "category": category,
                "fact": fact,
                "source_url": source_url,
            })

    leader: dict[str, str] = {}
    raw_leader = item.get("decision_maker")
    if isinstance(raw_leader, dict):
        source_url = _url(raw_leader.get("source_url"))
        role = _text(raw_leader.get("role"), 100)
        name = _text(raw_leader.get("name"), 100)
        background = _text(raw_leader.get("professional_background"), 260)
        if source_url and _domain(source_url) in grounded_domains and (role or name or background):
            leader = {
                "name": name,
                "role": role,
                "professional_background": background,
                "source_url": source_url,
            }

    return {"facts": facts[:8], "decision_maker": leader}


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
