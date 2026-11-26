"""Provider-neutral, source-grounded company research execution.

No provider client, database client, scheduler, or outreach side effect is created
here. The Gemini SDK adapter is imported lazily; its client and model are injected.
"""
from __future__ import annotations

import ipaddress
import json
import re
import time
from threading import Event, Thread
from typing import Any, Callable, Protocol
from urllib.parse import urlparse

from company_dossier import build_company_dossier, stamp_company_dossier
from company_research_admission import estimate_research_cost_microusd


class CompanyResearchProvider(Protocol):
    """Minimal adapter contract for a grounded research provider."""

    def research_company(
        self, *, prompt: str, heartbeat: Any
    ) -> dict[str, Any]:
        """Return structured research and provider-supplied grounding URLs."""



class GeminiGoogleSearchCompanyResearchProvider:
    """Google Gemini adapter using Search grounding; client and model are injected."""

    def __init__(self, *, client: Any, model: str, max_attempts: int = 3, heartbeat_interval_seconds: float = 30.0, sleep: Callable[[float], None] = time.sleep) -> None:
        if client is None or not callable(getattr(getattr(client, "models", None), "generate_content", None)):
            raise CompanyResearchExecutionError("invalid_gemini_client")
        if not isinstance(model, str) or not model.strip() or len(model) > 120:
            raise CompanyResearchExecutionError("invalid_gemini_model")
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or not 1 <= max_attempts <= 3:
            raise CompanyResearchExecutionError("invalid_provider_attempt_limit")
        self._client = client
        self._model = model.strip()
        if not callable(sleep):
            raise CompanyResearchExecutionError("invalid_provider_sleep_callback")
        if isinstance(heartbeat_interval_seconds, bool) or not isinstance(heartbeat_interval_seconds, (int, float)) or heartbeat_interval_seconds <= 0:
            raise CompanyResearchExecutionError("invalid_heartbeat_interval")
        self._max_attempts = max_attempts
        self._heartbeat_interval_seconds = float(heartbeat_interval_seconds)
        self._sleep = sleep

    def research_company(self, *, prompt: str, heartbeat: Any) -> dict[str, Any]:
        from google.genai import types

        config = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
        stop_heartbeat = Event()
        lease_lost = Event()
        heartbeat_thread: Thread | None = None

        if heartbeat is not None:
            if not callable(heartbeat):
                raise CompanyResearchExecutionError("invalid_heartbeat_callback")

            def renew_lease() -> None:
                while not stop_heartbeat.wait(self._heartbeat_interval_seconds):
                    try:
                        if not heartbeat():
                            lease_lost.set()
                            return
                    except Exception:
                        lease_lost.set()
                        return

            heartbeat_thread = Thread(target=renew_lease, name="company-research-lease-heartbeat", daemon=True)
            heartbeat_thread.start()

        try:
            for attempt in range(1, self._max_attempts + 1):
                if lease_lost.is_set():
                    raise CompanyResearchLeaseLost("Research job lease was lost during provider execution.")
                try:
                    response = self._client.models.generate_content(model=self._model, contents=prompt, config=config)
                    break
                except Exception as exc:
                    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
                    try:
                        status = int(status)
                    except (TypeError, ValueError):
                        status = None
                    retryable = status in {408, 425, 429, 500, 502, 503, 504}
                    if status is None:
                        message = str(exc).casefold()
                        retryable = any(token in message for token in ("timeout", "timed out", "temporarily unavailable", "connection reset", "connection aborted", "rate limit", "resource exhausted", "server error"))
                    if not retryable or attempt >= self._max_attempts:
                        raise
                    self._sleep(min(2 ** (attempt - 1), 4))
        finally:
            stop_heartbeat.set()
            if heartbeat_thread is not None:
                heartbeat_thread.join(timeout=max(1.0, self._heartbeat_interval_seconds * 2))
        if lease_lost.is_set():
            raise CompanyResearchLeaseLost("Research job lease was lost during provider execution.")
        grounded_sources: list[str] = []
        for candidate in getattr(response, "candidates", None) or []:
            metadata = getattr(candidate, "grounding_metadata", None)
            for chunk in getattr(metadata, "grounding_chunks", None) or []:
                uri = getattr(getattr(chunk, "web", None), "uri", None)
                if isinstance(uri, str):
                    grounded_sources.append(uri)
        usage_metadata = getattr(response, "usage_metadata", None)
        usage: dict[str, int] = {}
        for source_name, target_name in (("prompt_token_count", "prompt_tokens"), ("candidates_token_count", "output_tokens"), ("total_token_count", "total_tokens")):
            value = getattr(usage_metadata, source_name, None)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                usage[target_name] = value
        return {"research": getattr(response, "text", None), "grounded_sources": grounded_sources, "provider_usage": usage}


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
    normalized = re.sub(r"\s+", " ", value).strip()
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
        ):
            return None
        return _normalize_domain(parsed.hostname)
    except (ValueError, UnicodeError):
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
    if heartbeat is not None and not heartbeat():
        raise CompanyResearchLeaseLost("Research job lease was lost during provider execution.")
    if not isinstance(response, dict):
        raise CompanyResearchExecutionError("invalid_provider_response")

    raw_research = response.get("research")
    if isinstance(raw_research, str):
        cleaned_research = raw_research.strip()
        cleaned_research = re.sub(
            r"^\x60{3}(?:json)?\s*|\s*\x60{3}$", "", cleaned_research, flags=re.I
        )
        try:
            raw_research = json.loads(cleaned_research)
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
        "provider_usage": response.get("provider_usage", {}) if isinstance(response.get("provider_usage", {}), dict) else {},
    }



def make_company_research_handler(provider: CompanyResearchProvider):
    """Adapt an injected provider to the worker's (payload, heartbeat) handler API."""
    if provider is None or not callable(getattr(provider, "research_company", None)):
        raise CompanyResearchExecutionError("invalid_research_provider")

    def handler(payload: dict[str, Any], heartbeat: Any) -> dict[str, Any]:
        return execute_company_research(payload, provider=provider, heartbeat=heartbeat)

    return handler



def make_gemini_actual_cost_extractor(
    *,
    input_price_microusd_per_million_tokens: int,
    output_price_microusd_per_million_tokens: int,
):
    """Build a pricing-configured extractor; missing provider usage keeps estimate reserved."""
    estimate_research_cost_microusd(
        input_tokens=0,
        output_tokens=0,
        input_price_microusd_per_million_tokens=input_price_microusd_per_million_tokens,
        output_price_microusd_per_million_tokens=output_price_microusd_per_million_tokens,
    )

    def extract(result: dict[str, Any]) -> int | None:
        usage = result.get("provider_usage")
        if not isinstance(usage, dict):
            return None
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("output_tokens")
        if input_tokens is None or output_tokens is None:
            return None
        return estimate_research_cost_microusd(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_price_microusd_per_million_tokens=input_price_microusd_per_million_tokens,
            output_price_microusd_per_million_tokens=output_price_microusd_per_million_tokens,
        )
    return extract
