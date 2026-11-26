"""Explicit composition root for one company-research worker invocation.

Nothing runs at import time. Repository, provider, worker identity and pricing
are supplied by the caller; this module creates no credentials or clients.
"""
from __future__ import annotations

from typing import Any

from company_research_execution import (
    CompanyResearchProvider,
    make_company_research_handler,
    make_gemini_actual_cost_extractor,
)
from company_research_job_repository import CompanyResearchJobRepository
from company_research_worker import run_one_company_research_job


def run_company_research_worker_once(
    repository: CompanyResearchJobRepository,
    *,
    provider: CompanyResearchProvider,
    worker_id: str,
    input_price_microusd_per_million_tokens: int,
    output_price_microusd_per_million_tokens: int,
    **worker_options: Any,
) -> dict[str, Any]:
    """Run at most one explicitly claimed job with grounded Gemini and cost settlement."""
    handler = make_company_research_handler(provider)
    cost_extractor = make_gemini_actual_cost_extractor(
        input_price_microusd_per_million_tokens=input_price_microusd_per_million_tokens,
        output_price_microusd_per_million_tokens=output_price_microusd_per_million_tokens,
    )
    return run_one_company_research_job(
        repository,
        worker_id=worker_id,
        handler=handler,
        actual_cost_extractor=cost_extractor,
        **worker_options,
    )
