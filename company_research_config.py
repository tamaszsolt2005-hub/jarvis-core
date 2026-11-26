"""Single source of truth for bounded company-research admission and execution.

Prices and budget limits are required from deployment configuration. This
module never guesses provider pricing or creates clients at import time.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class CompanyResearchRuntimeConfig:
    input_price_microusd_per_million_tokens: int
    output_price_microusd_per_million_tokens: int
    pricing_model: str
    max_daily_cost_microusd: int
    max_jobs_per_hour: int
    max_jobs_per_domain_per_day: int
    max_concurrent_jobs: int
    max_input_tokens_per_attempt: int = 12000
    max_output_tokens_per_attempt: int = 2048
    max_attempts: int = 1
    max_age_days: int = 30
    batch_limit: int = 50

    def __post_init__(self) -> None:
        if not isinstance(self.pricing_model, str) or not self.pricing_model.strip() or len(self.pricing_model.strip()) > 120:
            raise ValueError("pricing_model must be a non-empty model identifier")
        positive = (
            "input_price_microusd_per_million_tokens",
            "output_price_microusd_per_million_tokens",
            "max_daily_cost_microusd",
            "max_jobs_per_hour",
            "max_jobs_per_domain_per_day",
            "max_concurrent_jobs",
            "max_input_tokens_per_attempt",
            "max_output_tokens_per_attempt",
            "max_attempts",
            "batch_limit",
        )
        for name in positive:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.max_output_tokens_per_attempt < 128 or self.max_output_tokens_per_attempt > 4096:
            raise ValueError("max_output_tokens_per_attempt must be between 128 and 4096")
        # Failed provider attempts do not currently expose measurable usage.
        # Allowing retries would under-report billable cost at settlement.
        if self.max_attempts != 1:
            raise ValueError("max_attempts must be 1 until every provider attempt is billable-measured")
        if isinstance(self.max_age_days, bool) or not isinstance(self.max_age_days, int) or self.max_age_days < 0:
            raise ValueError("max_age_days must be a non-negative integer")

    def validate_model(self, model: str) -> None:
        if not isinstance(model, str) or model.strip() != self.pricing_model.strip():
            raise ValueError("configured Gemini model does not match the model used for pricing")

    @property
    def limits(self) -> dict[str, int]:
        return {
            "max_daily_cost_microusd": self.max_daily_cost_microusd,
            "max_jobs_per_hour": self.max_jobs_per_hour,
            "max_jobs_per_domain_per_day": self.max_jobs_per_domain_per_day,
            "max_concurrent_jobs": self.max_concurrent_jobs,
        }

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "CompanyResearchRuntimeConfig":
        """Load explicit prices and budget; never supply implicit price defaults."""
        import os

        source = os.environ if environ is None else environ

        def integer(name: str, default: int | None = None) -> int:
            raw = source.get(name)
            if raw is None or not str(raw).strip():
                if default is None:
                    raise ValueError(f"Missing required company research setting: {name}")
                return default
            try:
                return int(str(raw).strip())
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{name} must be an integer") from exc

        return cls(
            input_price_microusd_per_million_tokens=integer("JARVIS_COMPANY_RESEARCH_INPUT_PRICE_MICROUSD_PER_MILLION_TOKENS"),
            output_price_microusd_per_million_tokens=integer("JARVIS_COMPANY_RESEARCH_OUTPUT_PRICE_MICROUSD_PER_MILLION_TOKENS"),
            pricing_model=str(source.get("JARVIS_COMPANY_RESEARCH_PRICING_MODEL") or "").strip(),
            max_daily_cost_microusd=integer("JARVIS_COMPANY_RESEARCH_MAX_DAILY_COST_MICROUSD"),
            max_jobs_per_hour=integer("JARVIS_COMPANY_RESEARCH_MAX_JOBS_PER_HOUR"),
            max_jobs_per_domain_per_day=integer("JARVIS_COMPANY_RESEARCH_MAX_JOBS_PER_DOMAIN_PER_DAY"),
            max_concurrent_jobs=integer("JARVIS_COMPANY_RESEARCH_MAX_CONCURRENT_JOBS"),
            max_input_tokens_per_attempt=integer("JARVIS_COMPANY_RESEARCH_MAX_INPUT_TOKENS", 12000),
            max_output_tokens_per_attempt=integer("JARVIS_COMPANY_RESEARCH_MAX_OUTPUT_TOKENS", 2048),
            max_attempts=integer("JARVIS_COMPANY_RESEARCH_MAX_PROVIDER_ATTEMPTS", 1),
            max_age_days=integer("JARVIS_COMPANY_RESEARCH_MAX_AGE_DAYS", 30),
            batch_limit=integer("JARVIS_COMPANY_RESEARCH_BATCH_LIMIT", 50),
        )


class TokenBoundedGeminiProvider:
    """Fail-closed input-token guard around the existing grounded Gemini adapter."""

    def __init__(self, *, client: Any, model: str, config: CompanyResearchRuntimeConfig):
        from company_research_execution import GeminiGoogleSearchCompanyResearchProvider

        models = getattr(client, "models", None)
        if not callable(getattr(models, "count_tokens", None)):
            raise ValueError("Gemini client must support count_tokens for hard input bounds")
        self._client = client
        self._model = model
        self._max_input_tokens = config.max_input_tokens_per_attempt
        self._provider = GeminiGoogleSearchCompanyResearchProvider(
            client=client,
            model=model,
            max_attempts=config.max_attempts,
            max_output_tokens=config.max_output_tokens_per_attempt,
        )

    def research_company(self, *, prompt: str, heartbeat: Any) -> dict[str, Any]:
        from company_research_execution import CompanyResearchExecutionError

        counted = self._client.models.count_tokens(model=self._model, contents=prompt)
        token_count = getattr(counted, "total_tokens", None)
        if isinstance(token_count, bool) or not isinstance(token_count, int) or token_count < 0:
            raise CompanyResearchExecutionError("invalid_prompt_token_count")
        if token_count > self._max_input_tokens:
            raise CompanyResearchExecutionError("provider_input_token_limit_exceeded")
        return self._provider.research_company(prompt=prompt, heartbeat=heartbeat)


def enqueue_company_research_refreshes_with_config(
    repository: Any,
    leads: list[dict[str, Any]],
    latest_dossiers: dict[str, Any],
    *,
    config: CompanyResearchRuntimeConfig,
    now: Any = None,
) -> list[dict[str, Any]]:
    """Enqueue with the exact same price/token/attempt settings used by worker."""
    from company_research_refresh_queue import enqueue_company_research_refreshes

    return enqueue_company_research_refreshes(
        repository,
        leads,
        latest_dossiers,
        limits=config.limits,
        input_price_microusd_per_million_tokens=config.input_price_microusd_per_million_tokens,
        output_price_microusd_per_million_tokens=config.output_price_microusd_per_million_tokens,
        max_input_tokens_per_attempt=config.max_input_tokens_per_attempt,
        max_output_tokens_per_attempt=config.max_output_tokens_per_attempt,
        max_attempts=config.max_attempts,
        now=now,
        max_age_days=config.max_age_days,
        limit=config.batch_limit,
    )


def run_company_research_worker_with_config(
    repository: Any,
    *,
    client: Any,
    model: str,
    snapshot_db: Any,
    worker_id: str,
    config: CompanyResearchRuntimeConfig,
    **worker_options: Any,
) -> dict[str, Any]:
    """Run one worker claim using the same immutable settings as queue admission."""
    from company_research_runtime import run_company_research_worker_once

    config.validate_model(model)
    if worker_options.get("max_attempts", 1) != 1:
        raise ValueError("worker max_attempts must be 1 while failed-attempt cost is not measurable")
    if worker_options.get("max_concurrent_jobs", config.max_concurrent_jobs) != config.max_concurrent_jobs:
        raise ValueError("max_concurrent_jobs must come from the shared runtime config")
    # Job-level retries would issue additional provider calls outside the
    # reservation's single measured attempt. Fail closed instead.
    worker_options["max_attempts"] = 1
    worker_options.pop("max_concurrent_jobs", None)
    provider = TokenBoundedGeminiProvider(client=client, model=model, config=config)
    return run_company_research_worker_once(
        repository,
        provider=provider,
        snapshot_db=snapshot_db,
        worker_id=worker_id,
        input_price_microusd_per_million_tokens=config.input_price_microusd_per_million_tokens,
        output_price_microusd_per_million_tokens=config.output_price_microusd_per_million_tokens,
        max_concurrent_jobs=config.max_concurrent_jobs,
        **worker_options,
    )
