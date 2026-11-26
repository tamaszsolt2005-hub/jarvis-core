"""Provider-neutral, source-grounded company research execution.

No provider SDK, network client, database client, scheduler, or outreach side effect
is created here. A concrete provider is injected by the caller.
"""
from __future__ import annotations

import ipaddress
import json
import re
from typing import Any, Protocol
from urllib.parse import urlparse

from company_dossier import build_company_dossier, stamp_company_dossier


class CompanyResearchProvider(Protocol):
    """Minimal adapter contract for a grounded research provider."""

    def research_company(
        self, *, prompt: str, heartbeat: Any
    ) -> dict[str, Any]:
        """Return structured research and provider-supplied grounding URLs."""


class CompanyResearchExecutionError(ValueError):
    """Non-retryable research input or provider response contract error."""

    retryable = False


class CompanyResearchLeaseLost(RuntimeError):
    """Raised when the worker no longer owns the job lease."""

    retryable = False
    code = "research_lease_lost"


def _bounded_text(value: Any, *, field: str, limit: int) -> str:
    if not isinstance(value, str):
        raise CompanyResearchExecutionError(f"invalid_{field}")
    normalized = re.sub(r"\\s+", " ", value).strip()
    if not normalized or len(normalized) > limit:
        raise CompanyResearchExecutionError(f"invalid_{field}")
    return normalized


def _normalize_domain(value: Any) -> str:
    raw = _bounded_text(value, field="company_domain", limit=253).casefold().rstrip(".")
    if "://" in raw or "/" in raw or "@" in raw or ":" in raw:
        raise CompanyResearchExecutionError("invalid_company_domain")
    try:
        domain = raw.encode("idna").decode("ascii")
        ipaddress.ip_address(domain.strip("[]"))
    except UnicodeError as exc:
        raise CompanyResearchExecutionError("invalid_company_domain") from exc
    except ValueError:
        pass
    else:
        raise CompanyResearchExecutionError("ip_address_not_allowed")
    labels = domain.split(".")
    if (
        len(labels) < 2
        or len(domain) > 253
        or any(
            not label or len(label) > 63
            or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label)
            for label in labels
        )
        or labels[-1] in {"localhost", "local", "internal", "test", "invalid"}
    ):
        raise CompanyResearchExecutionError("invalid_company_domain")
    return domain.removeprefix("www.")


def _grounded_domain(url: Any) -> str | None:
    if not isinstance(url, str) or len(url) > 2048:
        return None
    try:
        parsed = urlparse(url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.hostname.casefold() in {"localhost", "localhost.localdomain"}
        ):
            return None
        host = parsed.hostname.encode("idna").decode("ascii").casefold().removeprefix("www.")
        ipaddress.ip_address(host)
        return None
    except ValueError:
        return host if "host" in locals() else None
    except (UnicodeError, TypeError):
        return None


def build_company_research_prompt(
    *, company_name: str, company_domain: str, market: str
) -> str:
    """Create a bounded, structured prompt; treat company identifiers as data."""
    company_name_json = json.dumps(company_name, ensure_ascii=False)
    company_domain_json = json.dumps(company_domain, ensure_ascii=False)
    market_json = json.dumps(market, ensure_ascii=False)
    return f"""Research this company using public, business-relevant information only.

Company name (JSON string): {company_name_json}
Company website domain (JSON string): {company_domain_json}
Target market (JSON string): {market_json}

Return one JSON object with:
- company_facts: an array of objects with category, fact, source_url
- decision_maker: an object with name, role, professional_background, source_url
Use only these fact categories: business_model, products_services, customer_segments,
markets, growth_signal, technology_signal, operational_process, leadership, public_news.
Every factual statement must have a direct source_url that appears in the provider's
grounding metadata. Do not infer private contact details, personal information,
email addresses, phone numbers, consent, or permission to contact. If a fact or
professional detail cannot be supported by a grounded source, omit it. Return JSON only."""


def execute_company_research(
    payload: dict[str, Any],
    *,
    provider: CompanyResearchProvider,
    heartbeat: Any = None,
) -> dict[str, Any]:
    """Run one injected grounded provider request and return a validated dossier."""
    if not isinstance(payload, dict):
        raise CompanyResearchExecutionError("invalid_job_payload")
    if provider is None or not callable(getattr(provider, "research_company", None)):
        raise CompanyResearchExecutionError("invalid_research_provider")

    company_name = _bounded_text(payload.get("company_name"), field="company_name", limit=180)
    company_domain = _normalize_domain(payload.get("company_domain"))
    market = _bounded_text(payload.get("market", "Hungary"), field="market", limit=100)

    if heartbeat is not None:
        if not callable(heartbeat):
            raise CompanyResearchExecutionError("invalid_heartbeat_callback")
        if not heartbeat():
            raise CompanyResearchLeaseLost("Research job lease was lost before provider execution.")

    prompt = build_company_research_prompt(
        company_name=company_name, company_domain=company_domain, market=market
    )
    response = provider.research_company(prompt=prompt, heartbeat=heartbeat)
    if not isinstance(response, dict):
        raise CompanyResearchExecutionError("invalid_provider_response")

    raw_research = response.get("research")
    if isinstance(raw_research, str):
        try:
            raw_research = json.loads(raw_research)
        except (TypeError, ValueError) as exc:
            raise CompanyResearchExecutionError("invalid_provider_json") from exc
    if not isinstance(raw_research, dict):
        raise CompanyResearchExecutionError("invalid_provider_research_object")

    grounded_sources = response.get("grounded_sources")
    if not isinstance(grounded_sources, list):
        raise CompanyResearchExecutionError("missing_grounding_metadata")
    grounded_domains = {
        domain for domain in (_grounded_domain(url) for url in grounded_sources) if domain
    }
    dossier = build_company_dossier(raw_research, grounded_domains)
    if not dossier["facts"] and not dossier["decision_maker"]:
        raise CompanyResearchExecutionError("no_grounded_company_research")

    stamped = stamp_company_dossier(dossier)
    return {
        "company_name": company_name,
        "company_domain": company_domain,
        "market": market,
        "company_dossier": stamped,
        "grounded_source_count": len(grounded_sources),
        "accepted_fact_count": len(stamped["facts"]),
    }



def make_company_research_handler(provider: CompanyResearchProvider):
    """Adapt an injected provider to the worker's (payload, heartbeat) handler API."""
    if provider is None or not callable(getattr(provider, "research_company", None)):
        raise CompanyResearchExecutionError("invalid_research_provider")

    def handler(payload: dict[str, Any], heartbeat: Any) -> dict[str, Any]:
        return execute_company_research(payload, provider=provider, heartbeat=heartbeat)

    return handler
