"""Grounded, global company discovery. Never sends outreach or grants contact consent."""
from __future__ import annotations

import json
import re
import time
from uuid import uuid4
from typing import Any
from urllib.parse import urlparse

from google.genai import types

from jarvis_common import get_gemini_client, get_model_name, log_event, audit_event, get_enforced_user_supabase
from jarvis_errors import report_error
from lead_identity import upsert_company_lead
from company_dossier import build_company_dossier, render_company_dossier, stamp_company_dossier
from company_research_store import save_company_research_snapshot


MAX_RESULTS = 15
RESEARCH_API_MAX_ATTEMPTS = 3
EXISTING_LEAD_PAGE_SIZE = 1000
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


def _load_existing_company_keys(db: Any) -> tuple[set[str], set[str]]:
    """Load every existing lead key in bounded pages; never silently cap dedupe."""
    names: set[str] = set()
    sites: set[str] = set()
    offset = 0
    while True:
        rows = (
            db.table("leads")
            .select("id,company_name,website")
            .order("id")
            .range(offset, offset + EXISTING_LEAD_PAGE_SIZE - 1)
            .execute()
            .data
            or []
        )
        for row in rows:
            name = str(row.get("company_name") or "").strip().casefold()
            if name:
                names.add(name)
            website = _valid_http_url(row.get("website"))
            if website:
                sites.add(_domain(website))
        if len(rows) < EXISTING_LEAD_PAGE_SIZE:
            break
        offset += EXISTING_LEAD_PAGE_SIZE
    return names, sites


def _is_retryable_research_error(exc: Exception) -> bool:
    """Retry only transient upstream failures, never auth/config/validation errors."""
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    try:
        status = int(status)
    except (TypeError, ValueError):
        status = None
    if status in {408, 425, 429, 500, 502, 503, 504}:
        return True
    if status is not None:
        return False
    message = str(exc).casefold()
    return any(token in message for token in (
        "timeout", "timed out", "temporarily unavailable",
        "connection reset", "connection aborted", "rate limit",
        "resource exhausted", "server error",
    ))


def _generate_research_with_retry(
    client: Any, *, model: str, prompt: str, config: Any,
    sleep: Any = time.sleep,
) -> Any:
    """Bounded exponential retry for transient Gemini/transport errors."""
    for attempt in range(1, RESEARCH_API_MAX_ATTEMPTS + 1):
        try:
            return client.models.generate_content(
                model=model, contents=prompt, config=config
            )
        except Exception as exc:
            if attempt >= RESEARCH_API_MAX_ATTEMPTS or not _is_retryable_research_error(exc):
                raise
            sleep(min(2 ** (attempt - 1), 4))


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
            country = value["country"].strip()
            if country in set(MARKET_ALIASES.values()):
                return country
    except Exception as exc:
        # This is an optional read with a safe default; report locally only.
        # Do not write to the database from this fallback path.
        report_error(
            exc, module="global_lead_research", operation="read_research_market",
            severity="warning",
        )
    return DEFAULT_MARKET


def set_research_market(
    db: Any, country: str, *, auth_session: dict[str, str] | None = None
) -> str:
    """Persist the active market without changing email permissions."""
    enforced = get_enforced_user_supabase(
        auth_session, "settings.write", allowed_roles={"admin"}
    )
    if enforced is not None:
        db, _ = enforced
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


def _research_quality(item: dict[str, Any]) -> tuple[str, int | None, list[str]]:
    """Conservatively downgrade scores when public evidence is thin."""
    evidence = item.get("fit_evidence")
    if not isinstance(evidence, list):
        evidence = [str(evidence)] if evidence else []
    evidence = [str(value).strip()[:220] for value in evidence[:5] if str(value).strip()]
    confidence = str(item.get("research_confidence") or "low").casefold()
    if confidence not in {"high", "medium", "low"}:
        confidence = "low"
    try:
        score = max(0, min(100, int(float(item.get("business_fit_score")))))
    except (TypeError, ValueError, OverflowError):
        score = None
    if len(evidence) == 0:
        confidence = "low"
        score = min(score, 40) if score is not None else None
    elif len(evidence) == 1 and confidence == "high":
        confidence = "medium"
        score = min(score, 70) if score is not None else None
    if not str(item.get("potential_fit") or "").strip():
        confidence = "low"
        score = min(score, 50) if score is not None else None
    return confidence, score, evidence


def research_global_companies(
    db: Any, request: str, client: Any | None = None,
    max_results: int = MAX_RESULTS, market_country: str | None = None,
    *, auth_session: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Find public business entities worldwide and save unapproved company-only leads.

    Search results are treated as untrusted. Only entries tied to a Google Search
    grounding source are accepted. No personal emails are collected and every
    inserted record has approved_to_contact=False.
    """
    enforced = get_enforced_user_supabase(
        auth_session, "leads.write", allowed_roles={"admin", "operator"}
    )
    if enforced is not None:
        db, _ = enforced

    market_country = get_research_market(db) if market_country is None else market_country
    if not isinstance(market_country, str) or market_country not in set(MARKET_ALIASES.values()):
        raise ValueError("Nem támogatott vagy nem ismert célország.")

    client = client or get_gemini_client()
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
        "\"source_url\":\"URL of a Google Search source supporting this company\","
        "\"company_facts\":[{\"category\":\"business_model|products_services|customer_segments|markets|growth_signal|technology_signal|operational_process|leadership|public_news\",\"fact\":\"concise public business fact\",\"source_url\":\"grounded source URL\"}],"
        "\"decision_maker\":{\"name\":\"publicly identified leader name or empty\",\"role\":\"business role\",\"professional_background\":\"public professional background only\",\"source_url\":\"grounded professional source URL\"}}]}. "
        "Assess fit separately from website quality: business_fit_score is a provisional 0-100 estimate of fit for AI/automation services, "
        "not purchase intent, financial capacity, or consent. Base it only on explicit public evidence; use a low score or low confidence when evidence is weak. "
        "Name the evidence behind every score, and never treat absence of evidence as a negative fact. High confidence requires at least two distinct concrete fit-evidence items; one item permits at most medium confidence; no fit evidence or no specific fit explanation requires low confidence and a capped score. "
        "Prefer detailed official-company pages, products, workflows, scale indicators and credible public case studies. "
        "Do not invent companies, domains or facts. "
        "Do not collect private contact details, personal email addresses, phone numbers or sensitive/private data. A leader's name and background may be included ONLY when explicitly published in a relevant professional/business context and tied to a grounded source URL. "
        "A public business contact address is not consent to marketing. Do not infer consent. "
        "User's business/prospecting brief: " + str(request)[:2000]
    )
    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
    )
    response = _generate_research_with_retry(
        client, model=get_model_name(), prompt=prompt, config=config
    )
    companies = _parse_companies(_field(response, "text", "") or "")
    grounded_urls = _grounded_sources(response)
    grounded_domains = {_domain(url) for url in grounded_urls if _valid_http_url(url)}
    if not grounded_domains:
        raise RuntimeError("A Google Search nem adott ellenőrizhető forráshivatkozásokat; lead nem került mentésre.")

    known_names, known_sites = _load_existing_company_keys(db)
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
        confidence, fit_score, fit_evidence = _research_quality(item)
        business_need = str(item.get("business_need") or "A nyilvános forrásokból nem állapítható meg.")[:500]
        next_step = str(item.get("recommended_next_step") or "További nyilvános cégkutatás; kapcsolatfelvétel nélkül.")[:400]
        dossier = stamp_company_dossier(build_company_dossier(item, grounded_domains))
        dossier_text = render_company_dossier(dossier)
        base_notes = (
            f"Leadkutatás; célpiac: {market_country}; tényleges ország: {country}; iparág: {industry}; "
            f"kutatási módszer: Google Search grounding + hivatalos weboldal és forrás-keresztellenőrzés. "
            f"Cégprofil: {summary} Lehetséges illeszkedés: {fit} "
            f"AI üzleti illeszkedési becslés: {fit_score if fit_score is not None else 'nincs adat'}/100; "
            f"bizonyosság: {confidence}; megfigyelhető üzleti igény: {business_need}; "
            f"alátámasztó jelek: {'; '.join(fit_evidence)}; javasolt kutatási lépés: {next_step} "
            f"Forrás: {source_url}"
        )[:2200]
        notes = (base_notes + (f" Részletes cégdosszié: {dossier_text}" if dossier_text else ""))[:3500]
        # No email, no permission, no outreach status: discovery is not consent.
        # Audit the write before inserting; a research record is still a durable
        # business-data side effect even though it cannot trigger outreach.
        insert_operation_id = str(uuid4())
        if not audit_event(
            db,
            module="global_lead_research",
            action="save_researched_company",
            status="pending",
            operation_id=insert_operation_id,
            result={"company_domain": site_domain, "source_domain": source_domain},
        ):
            raise RuntimeError("A kutatási lead mentése leállítva: a pending auditbejegyzés nem menthető.")
        try:
            identity_result = upsert_company_lead(
                db,
                company_name=name,
                website=website,
                notes=notes,
                source=f"{SOURCE_TAG}:{source_domain}"[:200],
            )
            # Reuse only source-grounded dossier facts as Lead evidence.
            # Model-written summary/fit prose is not promoted to a source excerpt.
            lead_evidence = [
                {
                    "source_url": fact["source_url"],
                    "excerpt": fact["fact"][:1200],
                    "source_kind": "lead_research_note",
                    "evidence_type": "supporting",
                    "observed_at": dossier.get("researched_at", "undated"),
                    "captured_at": dossier.get("researched_at", "undated"),
                }
                for fact in dossier.get("facts", [])
                if isinstance(fact, dict) and fact.get("source_url") and fact.get("fact")
            ][:12]
            db.table("leads").update({
                "research_evidence": lead_evidence,
            }).eq("id", identity_result["lead_id"]).execute()
        except Exception as exc:
            audit_event(
                db,
                module="global_lead_research",
                action="save_researched_company",
                status="unknown",
                operation_id=insert_operation_id,
                error=exc,
                result={"company_domain": site_domain, "source_domain": source_domain},
                level="error",
            )
            raise
        if not audit_event(
            db,
            module="global_lead_research",
            action="save_researched_company",
            status="success",
            operation_id=insert_operation_id,
            result={
                "company_domain": site_domain,
                "source_domain": source_domain,
                "lead_id": identity_result["lead_id"],
                "outcome": identity_result["outcome"],
            },
        ):
            raise RuntimeError("A kutatási lead mentése megtörtént, de a záró auditbejegyzés nem menthető.")
        # Persist the complete, immutable dossier version separately from the mutable lead notes.
        if not audit_event(
            db,
            module="global_lead_research",
            action="company_research_snapshot",
            status="pending",
            operation_id=dossier["snapshot_id"],
            result={"company_domain": site_domain, "lead_id": identity_result["lead_id"]},
        ):
            raise RuntimeError("A cégkutatási snapshot mentése leállítva: a pending audit nem menthető.")
        try:
            save_company_research_snapshot(
                db,
                lead_id=identity_result["lead_id"],
                company_domain=site_domain,
                dossier=dossier,
            )
        except Exception as exc:
            audit_event(
                db,
                module="global_lead_research",
                action="company_research_snapshot",
                status="failed",
                operation_id=dossier["snapshot_id"],
                error=exc,
                result={"company_domain": site_domain, "lead_id": identity_result["lead_id"]},
                level="error",
            )
            raise
        if not audit_event(
            db,
            module="global_lead_research",
            action="company_research_snapshot",
            status="success",
            operation_id=dossier["snapshot_id"],
            result={
                "snapshot_id": dossier["snapshot_id"],
                "schema_version": dossier["schema_version"],
                "researched_at": dossier["researched_at"],
                "content_sha256": dossier["content_sha256"],
                "company_domain": site_domain,
                "fact_count": len(dossier["facts"]),
                "decision_maker_profiled": bool(dossier["decision_maker"]),
            },
        ):
            raise RuntimeError("A cégdosszié mentése megtörtént, de a snapshot-audit nem menthető.")
        known_names.add(name.casefold())
        known_sites.add(site_domain)
        if identity_result["outcome"] == "existing":
            skipped += 1
            continue
        inserted.append({"company_name": name, "website": website, "country": country,
                         "industry": industry, "business_summary": summary, "potential_fit": fit,
                         "business_fit_score": fit_score, "fit_evidence": fit_evidence,
                         "business_need": business_need, "recommended_next_step": next_step,
                         "research_confidence": confidence, "source_url": source_url,
                         "company_dossier": dossier})
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
    audit_event(
        db,
        module="global_lead_research",
        action="research_companies",
        status="success",
        operation_id=str(uuid4()),
        result={
            "market": market_country,
            "saved_count": len(inserted),
            "skipped_count": skipped,
            "contact_permission_granted": False,
            "email_sending": "disabled",
        },
    )
    log_event(db, "global_lead_research",
              f"Leadkutatás ({market_country}): {len(inserted)} új céges lead, {skipped} kihagyva; e-mail-küldés tiltva.")
    return result
