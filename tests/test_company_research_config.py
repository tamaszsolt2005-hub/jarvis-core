from types import SimpleNamespace

import pytest

from company_research_config import (
    CompanyResearchRuntimeConfig,
    TokenBoundedGeminiProvider,
    enqueue_company_research_refreshes_with_config,
    run_company_research_worker_with_config,
)


def config(**overrides):
    values = {
        "input_price_microusd_per_million_tokens": 2_000_000,
        "output_price_microusd_per_million_tokens": 4_000_000,
        "pricing_model": "gemini-test",
        "max_daily_cost_microusd": 900_000,
        "max_jobs_per_hour": 12,
        "max_jobs_per_domain_per_day": 2,
        "max_concurrent_jobs": 3,
        "max_input_tokens_per_attempt": 777,
        "max_output_tokens_per_attempt": 555,
        "max_attempts": 1,
        "max_age_days": 14,
        "batch_limit": 9,
    }
    values.update(overrides)
    return CompanyResearchRuntimeConfig(**values)


def test_environment_requires_explicit_prices_and_budget_limits():
    with pytest.raises(ValueError, match="INPUT_PRICE"):
        CompanyResearchRuntimeConfig.from_env({})


def test_environment_loads_one_explicit_shared_configuration():
    env = {
        "JARVIS_COMPANY_RESEARCH_INPUT_PRICE_MICROUSD_PER_MILLION_TOKENS": "2000000",
        "JARVIS_COMPANY_RESEARCH_OUTPUT_PRICE_MICROUSD_PER_MILLION_TOKENS": "4000000",
        "JARVIS_COMPANY_RESEARCH_PRICING_MODEL": "gemini-test",
        "JARVIS_COMPANY_RESEARCH_MAX_DAILY_COST_MICROUSD": "900000",
        "JARVIS_COMPANY_RESEARCH_MAX_JOBS_PER_HOUR": "12",
        "JARVIS_COMPANY_RESEARCH_MAX_JOBS_PER_DOMAIN_PER_DAY": "2",
        "JARVIS_COMPANY_RESEARCH_MAX_CONCURRENT_JOBS": "3",
        "JARVIS_COMPANY_RESEARCH_MAX_INPUT_TOKENS": "777",
        "JARVIS_COMPANY_RESEARCH_MAX_OUTPUT_TOKENS": "555",
        "JARVIS_COMPANY_RESEARCH_MAX_PROVIDER_ATTEMPTS": "1",
    }
    loaded = CompanyResearchRuntimeConfig.from_env(env)
    assert loaded.input_price_microusd_per_million_tokens == 2_000_000
    assert loaded.output_price_microusd_per_million_tokens == 4_000_000
    assert loaded.max_input_tokens_per_attempt == 777
    assert loaded.max_output_tokens_per_attempt == 555
    assert loaded.max_attempts == 1
    assert loaded.limits == {
        "max_daily_cost_microusd": 900_000,
        "max_jobs_per_hour": 12,
        "max_jobs_per_domain_per_day": 2,
        "max_concurrent_jobs": 3,
    }


@pytest.mark.parametrize("kwargs", [
    {"input_price_microusd_per_million_tokens": 0},
    {"max_daily_cost_microusd": 0},
    {"max_attempts": 2},
    {"max_output_tokens_per_attempt": 4097},
    {"max_age_days": True},
])
def test_config_rejects_unsafe_limits(kwargs):
    with pytest.raises(ValueError):
        config(**kwargs)


def test_queue_adapter_passes_exact_provider_cost_limits(monkeypatch):
    captured = {}

    def enqueue(_repository, _leads, _dossiers, **kwargs):
        captured.update(kwargs)
        return [{"operation_id": "queued"}]

    monkeypatch.setattr("company_research_refresh_queue.enqueue_company_research_refreshes", enqueue)
    cfg = config()
    result = enqueue_company_research_refreshes_with_config(
        object(), [], {}, config=cfg
    )
    assert result == [{"operation_id": "queued"}]
    assert captured["limits"] == cfg.limits
    assert captured["input_price_microusd_per_million_tokens"] == cfg.input_price_microusd_per_million_tokens
    assert captured["output_price_microusd_per_million_tokens"] == cfg.output_price_microusd_per_million_tokens
    assert captured["max_input_tokens_per_attempt"] == cfg.max_input_tokens_per_attempt
    assert captured["max_output_tokens_per_attempt"] == cfg.max_output_tokens_per_attempt
    assert captured["max_attempts"] == cfg.max_attempts
    assert captured["max_age_days"] == cfg.max_age_days
    assert captured["limit"] == cfg.batch_limit


def test_token_bounded_provider_rejects_over_limit_before_generate(monkeypatch):
    from company_research_execution import GeminiGoogleSearchCompanyResearchProvider

    generated = []

    class FakeProvider:
        def __init__(self, **kwargs):
            generated.append(("init", kwargs))

        def research_company(self, **kwargs):
            generated.append(("generate", kwargs))
            return {"ok": True}

    monkeypatch.setattr(
        "company_research_execution.GeminiGoogleSearchCompanyResearchProvider",
        FakeProvider,
    )
    models = SimpleNamespace(
        count_tokens=lambda **_kwargs: SimpleNamespace(total_tokens=778)
    )
    client = SimpleNamespace(models=models)
    provider = TokenBoundedGeminiProvider(client=client, model="gemini-test", config=config())
    with pytest.raises(ValueError, match="provider_input_token_limit_exceeded"):
        provider.research_company(prompt="prompt", heartbeat=None)
    assert [item[0] for item in generated] == ["init"]


def test_token_bounded_provider_passes_within_limit_and_uses_same_attempt_caps(monkeypatch):
    from company_research_execution import GeminiGoogleSearchCompanyResearchProvider

    captured = {}

    class FakeProvider:
        def __init__(self, **kwargs):
            captured["provider"] = kwargs

        def research_company(self, **kwargs):
            captured["request"] = kwargs
            return {"ok": True}

    monkeypatch.setattr(
        "company_research_execution.GeminiGoogleSearchCompanyResearchProvider",
        FakeProvider,
    )
    client = SimpleNamespace(models=SimpleNamespace(
        count_tokens=lambda **_kwargs: SimpleNamespace(total_tokens=777)
    ))
    cfg = config()
    provider = TokenBoundedGeminiProvider(client=client, model="gemini-test", config=cfg)
    assert provider.research_company(prompt="prompt", heartbeat=None) == {"ok": True}
    assert captured["provider"]["max_attempts"] == cfg.max_attempts
    assert captured["provider"]["max_output_tokens"] == cfg.max_output_tokens_per_attempt


def test_worker_adapter_uses_shared_pricing_and_concurrency(monkeypatch):
    captured = {}

    def run(repository, **kwargs):
        captured.update(kwargs)
        return {"status": "idle"}

    monkeypatch.setattr("company_research_runtime.run_company_research_worker_once", run)
    cfg = config()
    result = run_company_research_worker_with_config(
        object(), client=SimpleNamespace(models=SimpleNamespace(
            count_tokens=lambda **_: SimpleNamespace(total_tokens=1),
            generate_content=lambda **_: None,
        )),
        model="gemini-test", snapshot_db=object(), worker_id="worker-a", config=cfg,
    )
    assert result == {"status": "idle"}
    assert captured["input_price_microusd_per_million_tokens"] == cfg.input_price_microusd_per_million_tokens
    assert captured["output_price_microusd_per_million_tokens"] == cfg.output_price_microusd_per_million_tokens
    assert captured["max_concurrent_jobs"] == cfg.max_concurrent_jobs
    assert captured["max_attempts"] == 1
    assert isinstance(captured["provider"], TokenBoundedGeminiProvider)


def test_worker_adapter_rejects_unmeasured_job_retries(monkeypatch):
    cfg = config()
    client = SimpleNamespace(models=SimpleNamespace(
        count_tokens=lambda **_: SimpleNamespace(total_tokens=1)
    ))
    with pytest.raises(ValueError, match="worker max_attempts"):
        run_company_research_worker_with_config(
            object(), client=client, model="gemini-test", snapshot_db=object(),
            worker_id="worker-a", config=cfg, max_attempts=2,
        )


def test_worker_adapter_rejects_runtime_limit_override(monkeypatch):
    cfg = config()
    client = SimpleNamespace(models=SimpleNamespace(
        count_tokens=lambda **_: SimpleNamespace(total_tokens=1),
        generate_content=lambda **_: None,
    ))
    with pytest.raises(ValueError, match="max_concurrent_jobs"):
        run_company_research_worker_with_config(
            object(), client=client, model="gemini-test", snapshot_db=object(),
            worker_id="worker-a", config=cfg, max_concurrent_jobs=99,
        )


def test_runtime_rejects_model_that_does_not_match_pricing_schedule(monkeypatch):
    cfg = config()
    client = SimpleNamespace(models=SimpleNamespace(
        count_tokens=lambda **_: SimpleNamespace(total_tokens=1),
        generate_content=lambda **_: None,
    ))
    with pytest.raises(ValueError, match="does not match"):
        run_company_research_worker_with_config(
            object(), client=client, model="different-model", snapshot_db=object(),
            worker_id="worker-a", config=cfg,
        )
