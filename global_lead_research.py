"""Grounded, global company discovery. Never sends outreach or grants contact consent."""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from google import genai
from google.genai import types

from jarvis_common import get_model_name, log_event


MAX_RESULTS = 15
SOURCE_TAG = "gemini_google_search_grounding"


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _grounded_sources(response: Any) -> list[str]:
    candidates = _field(response, "candidates", []) or []
    urls: list[str] = []
    for candidate in candidates:
        metadata = _field(candidate, "grounding_metadata")
        chunks = _field(metadata, "grounding_chunks", []) or []
        for chunk in chunks:
            web = _field(chunk, "web")
            uri = _field(web, "uri")
            if uri:
                urls.append(str(uri))
    return urls


def _valid_http_url(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw or len(raw) > 2048:
        return None
    try:
        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        if parsed.username or parsed.password:
            return None
        if parsed.hostname.lower() in {"localhost", "localhost.localdomain"}:
            return None
        return raw
    except ValueError:
        return None


def _domain(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def _parse_companies(text: str) -> list[dict[str, Any]]:
    """Parse only a JSON object; tolerate a surrounding Markdown code fence."""
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^\x60{3}(?:json)?\s*|\s*\x60{3}$", "", cleaned, flags=re.I)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        return []
    try:
        payload = json.loads(cleaned[start:end + 1])
    except (TypeError, ValueError):
        return []
    companies = payload.get("companies", []) if isinstance(payload, dict) else []
    return [item for item in companies if isinstance(item, dict)] if isinstance(companies, list) else []


def research_global_companies(db: Any, request: str, client: Any | None = None,
                              max_results: int = MAX_RESULTS) -> dict[str, Any]:
    """Find public business entities worldwide and save unapproved company-only leads.

    Search results are treated as untrusted. Only entries tied to a Google Search
    grounding source are accepted. No personal emails are collected and every
    inserted record has approved_to_contact=False.
    """
    client = client or genai.Client()
    prompt = (
        "Perform live Google Search research for real, currently operating companies worldwide. "
        "No country, industry or company-size restriction. Interpret the user's business context "
        "as a broad prospecting brief, but include diverse sectors and regions rather than only "
        "one market. Return up to " + str(max(1, min(int(max_results), MAX_RESULTS))) + " distinct companies. "
        "Return ONLY valid JSON: {\"companies\":[{\"company_name\":\"...\","
        "\"website\":\"https://official-domain\",\"country\":\"...\",\"industry\":\"...\","
        "\"business_summary\":\"short factual summary\",\"potential_fit\":\"why it may fit\","
        "\"source_url\":\"URL of a Google Search source supporting this company\"}]}. "
        "Use official company websites where possible. Do not invent companies, domains or facts. "
        "Do not collect personal names, personal email addresses, phone numbers or private data. "
        "A public business contact address is not consent to marketing. Do not infer consent. "
        "User's business/prospecting brief: " + str(request)[:2000]
    )
    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        temperature=0.2,
    )
    response = client.models.generate_content(
        model=get_model_name(), contents=prompt, config=config
    )
    companies = _parse_companies(_field(response, "text", "") or "")
    grounded_urls = _grounded_sources(response)
    grounded_domains = {_domain(url) for url in grounded_urls if _valid_http_url(url)}
    if not grounded_domains:
        raise RuntimeError("A Google Search nem adott ellenőrizhető forráshivatkozásokat; lead nem került mentésre.")

    existing = db.table("leads").select("company_name,website").limit(5000).execute().data or []
    known_names = {str(row.get("company_name") or "").strip().casefold() for row in existing}
    known_sites = {_domain(url) for row in existing if (url := _valid_http_url(row.get("website")))}
    inserted, skipped = [], 0

    for item in companies[:max(1, min(int(max_results), MAX_RESULTS))]:
        name = re.sub(r"\s+", " ", str(item.get("company_name") or "")).strip()[:200]
        website = _valid_http_url(item.get("website"))
        source_url = _valid_http_url(item.get("source_url"))
        if not name or not website or not source_url:
            skipped += 1
            continue
        site_domain = _domain(website)
        source_domain = _domain(source_url)
        # Require both the official site and the supporting source to appear
        # in Google's grounding references; this reduces unsupported model output.
        if site_domain not in grounded_domains or source_domain not in grounded_domains:
            skipped += 1
            continue
        if name.casefold() in known_names or site_domain in known_sites:
            skipped += 1
            continue
        country = str(item.get("country") or "ismeretlen")[:100]
        industry = str(item.get("industry") or "ismeretlen")[:120]
        summary = str(item.get("business_summary") or "")[:700]
        fit = str(item.get("potential_fit") or "")[:700]
        notes = (
            f"Globális kutatás; ország: {country}; iparág: {industry}. "
            f"Cégprofil: {summary} Lehetséges illeszkedés: {fit} "
            f"Forrás: {source_url}"
        )[:2000]
        # No email, no permission, no outreach status: discovery is not consent.
        db.table("leads").insert({
            "company_name": name,
            "email": None,
            "website": website,
            "notes": notes,
            "source": f"{SOURCE_TAG}:{source_domain}"[:200],
            "status": "research",
            "consent_basis": None,
            "approved_to_contact": False,
            "opted_out": False,
        }).execute()
        known_names.add(name.casefold())
        known_sites.add(site_domain)
        inserted.append({"company_name": name, "website": website, "country": country,
                         "industry": industry, "source_url": source_url})
    result = {
        "searched": True,
        "saved_count": len(inserted),
        "skipped_count": skipped,
        "companies": inserted,
        "grounding_sources": grounded_urls[:30],
        "scope": "worldwide",
        "email_sending": "disabled",
        "contact_permission": "not_granted",
    }
    log_event(db, "global_lead_research",
              f"Globális kutatás: {len(inserted)} új céges lead, {skipped} kihagyva; e-mail-küldés tiltva.")
    return result
