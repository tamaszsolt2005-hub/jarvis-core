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
DEFAULT_MARKET = "Hungary"
MARKET_ALIASES = {
    "magyarország": "Hungary", "magyarorszag": "Hungary", "magyar": "Hungary", "hungary": "Hungary",
    "németország": "Germany", "nemetorszag": "Germany", "német": "Germany", "nemet": "Germany", "germany": "Germany",
    "franciaország": "France", "franciaorszag": "France", "francia": "France", "france": "France",
    "ausztria": "Austria", "osztrák": "Austria", "austria": "Austria",
    "svájc": "Switzerland", "svajc": "Switzerland", "switzerland": "Switzerland",
    "egyesült királyság": "United Kingdom", "anglia": "United Kingdom", "uk": "United Kingdom",
    "olaszország": "Italy", "olaszorszag": "Italy", "olasz": "Italy", "italy": "Italy",
    "spanyolország": "Spain", "spanyolorszag": "Spain", "spanyol": "Spain", "spain": "Spain",
    "lengyelország": "Poland", "lengyelorszag": "Poland", "lengyel": "Poland", "poland": "Poland",
    "románia": "Romania", "romania": "Romania", "román": "Romania",
    "hollandia": "Netherlands", "holland": "Netherlands", "netherlands": "Netherlands",
    "portugália": "Portugal", "portugalia": "Portugal", "portugál": "Portugal", "portugal": "Portugal",
    "belgium": "Belgium", "belga": "Belgium",
    "csehország": "Czechia", "csehorszag": "Czechia", "cseh": "Czechia", "czechia": "Czechia",
    "szlovákia": "Slovakia", "szlovakia": "Slovakia", "szlovák": "Slovakia", "slovakia": "Slovakia",
    "svédország": "Sweden", "svedorszag": "Sweden", "svéd": "Sweden", "sweden": "Sweden",
    "dánia": "Denmark", "dania": "Denmark", "dán": "Denmark", "denmark": "Denmark",
    "norvégia": "Norway", "norvegia": "Norway", "norvég": "Norway", "norway": "Norway",
    "finnország": "Finland", "finnorszag": "Finland", "finn": "Finland", "finland": "Finland",
    "írország": "Ireland", "irorszag": "Ireland", "ír": "Ireland", "ireland": "Ireland",
    "egyesült államok": "United States", "amerika": "United States", "amerikai": "United States", "usa": "United States",
    "kanada": "Canada", "canada": "Canada",
    "egész világ": "Worldwide", "egesz vilag": "Worldwide", "világszerte": "Worldwide", "vilagszerte": "Worldwide",
    "világ": "Worldwide", "worldwide": "Worldwide",
}
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


def get_research_market(db: Any) -> str:
    """Read the persistent lead-research market; default to Hungary."""
    try:
        rows = db.table("settings").select("value").eq("key", "lead_research_market").limit(1).execute().data or []
        value = rows[0].get("value") if rows else None
        if isinstance(value, dict) and isinstance(value.get("country"), str):
            return value["country"]
    except Exception:
        pass
    return DEFAULT_MARKET


def set_research_market(db: Any, country: str) -> str:
    """Persist the active market without changing email permissions."""
    if country not in set(MARKET_ALIASES.values()):
        raise ValueError("Nem támogatott vagy nem ismert célország.")
    db.table("settings").upsert({
        "key": "lead_research_market",
        "value": {"country": country},
    }).execute()
    return country


def detect_market_change(message: str) -> str | None:
    """Recognize explicit Hungarian market-switch commands."""
    q = (message or "").casefold().strip()
    if not any(word in q for word in ("válts", "valts", "állítsd", "allitsd", "átáll", "atall", "piac", "ország", "orszag")):
        return None
    for alias, country in sorted(MARKET_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if alias in q:
            return country
    return None


def research_global_companies(db: Any, request: str, client: Any | None = None,
                              max_results: int = MAX_RESULTS, market_country: str | None = None) -> dict[str, Any]:
    """Find public business entities worldwide and save unapproved company-only leads.

    Search results are treated as untrusted. Only entries tied to a Google Search
    grounding source are accepted. No personal emails are collected and every
    inserted record has approved_to_contact=False.
    """
    client = client or genai.Client()
    market_country = market_country or get_research_market(db)
    market_instruction = (
        "Focus ONLY on companies operating in " + market_country + ". Prioritize companies headquartered there "
        "or with substantial operations there. Do not return unrelated countries."
        if market_country != "Worldwide" else
        "Search worldwide with no country, industry or company-size restriction; include diverse regions."
    )
    prompt = (
        "Perform live Google Search research for real, currently operating companies. "
        + market_instruction + " Interpret the user's business context as a broad prospecting brief. Return up to " + str(max(1, min(int(max_results), MAX_RESULTS))) + " distinct companies. "
        "Return ONLY valid JSON: {\"companies\":[{\"company_name\":\"...\","
        "\"website\":\"https://official-domain\",\"country\":\"...\",\"industry\":\"...\","
        "\"business_summary\":\"factual company profile\",\"potential_fit\":\"specific fit for AI and business automation services\","
        "\"business_need\":\"observable business problem or opportunity, otherwise unknown\","
        "\"business_fit_score\":0,\"fit_evidence\":[\"specific public evidence\"],"
        "\"recommended_next_step\":\"research-only next step\",\"research_confidence\":\"high|medium|low\","
        "\"source_url\":\"URL of a Google Search source supporting this company\"}]}. "
        "Assess fit separately from website quality: business_fit_score is a provisional 0-100 estimate of fit for AI/automation services, "
        "not purchase intent, financial capacity, or consent. Base it only on explicit public evidence; use a low score or low confidence when evidence is weak. "
        "Name the evidence behind every score, and never treat absence of evidence as a negative fact. "
        "Prefer detailed official-company pages, products, workflows, scale indicators and credible public case studies. "
        "Do not invent companies, domains or facts. "
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
        fit_score_raw = item.get("business_fit_score")
        try:
            fit_score = max(0, min(100, int(float(fit_score_raw))))
        except (TypeError, ValueError, OverflowError):
            fit_score = None
        fit_evidence = item.get("fit_evidence")
        if not isinstance(fit_evidence, list):
            fit_evidence = [str(fit_evidence)] if fit_evidence else []
        fit_evidence = [str(value).strip()[:220] for value in fit_evidence[:5] if str(value).strip()]
        business_need = str(item.get("business_need") or "A nyilvános forrásokból nem állapítható meg.")[:500]
        next_step = str(item.get("recommended_next_step") or "További nyilvános cégkutatás; kapcsolatfelvétel nélkül.")[:400]
        confidence = str(item.get("research_confidence") or "low").casefold()
        if confidence not in {"high", "medium", "low"}:
            confidence = "low"
        notes = (
            f"Leadkutatás; célpiac: {market_country}; tényleges ország: {country}; iparág: {industry}; "
            f"kutatási módszer: Google Search grounding + hivatalos weboldal és forrás-keresztellenőrzés. "
            f"Cégprofil: {summary} Lehetséges illeszkedés: {fit} "
            f"AI üzleti illeszkedési becslés: {fit_score if fit_score is not None else 'nincs adat'}/100; "
            f"bizonyosság: {confidence}; megfigyelhető üzleti igény: {business_need}; "
            f"alátámasztó jelek: {'; '.join(fit_evidence)}; javasolt kutatási lépés: {next_step} "
            f"Forrás: {source_url}"
        )[:3500]
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
                         "industry": industry, "business_summary": summary, "potential_fit": fit,
                         "business_fit_score": fit_score, "fit_evidence": fit_evidence,
                         "business_need": business_need, "recommended_next_step": next_step,
                         "research_confidence": confidence, "source_url": source_url})
    result = {
        "searched": True,
        "saved_count": len(inserted),
        "skipped_count": skipped,
        "companies": inserted,
        "grounding_sources": grounded_urls[:30],
        "scope": market_country,
        "market_country": market_country,
        "email_sending": "disabled",
        "contact_permission": "not_granted",
    }
    log_event(db, "global_lead_research",
              f"Leadkutatás ({market_country}): {len(inserted)} új céges lead, {skipped} kihagyva; e-mail-küldés tiltva.")
    return result
