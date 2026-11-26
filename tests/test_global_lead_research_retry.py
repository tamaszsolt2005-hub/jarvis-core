from types import SimpleNamespace

import pytest

import global_lead_research as research


class TransientError(Exception):
    status_code = 503


class AuthError(Exception):
    status_code = 401


def _client(outcomes):
    calls = []

    def generate_content(**kwargs):
        calls.append(kwargs)
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)), calls


def test_research_retries_transient_error_then_succeeds():
    expected = object()
    client, calls = _client([TransientError("upstream unavailable"), expected])
    sleeps = []

    result = research._generate_research_with_retry(
        client, model="test-model", prompt="research", config={},
        sleep=sleeps.append,
    )

    assert result is expected
    assert len(calls) == 2
    assert sleeps == [1]


def test_research_does_not_retry_authentication_errors():
    client, calls = _client([AuthError("invalid API key"), object()])
    sleeps = []

    with pytest.raises(AuthError):
        research._generate_research_with_retry(
            client, model="test-model", prompt="research", config={},
            sleep=sleeps.append,
        )

    assert len(calls) == 1
    assert sleeps == []


def test_research_stops_after_bounded_transient_retries():
    client, calls = _client([
        TransientError("server unavailable"),
        TransientError("server unavailable"),
        TransientError("server unavailable"),
        object(),
    ])
    sleeps = []

    with pytest.raises(TransientError):
        research._generate_research_with_retry(
            client, model="test-model", prompt="research", config={},
            sleep=sleeps.append,
        )

    assert len(calls) == research.RESEARCH_API_MAX_ATTEMPTS == 3
    assert sleeps == [1, 2]


@pytest.mark.parametrize("status", [408, 425, 429, 500, 502, 503, 504])
def test_known_transient_status_codes_are_retryable(status):
    error = RuntimeError("upstream")
    error.status_code = status
    assert research._is_retryable_research_error(error)


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_client_and_permission_errors_are_not_retryable(status):
    error = RuntimeError("request rejected")
    error.status_code = status
    assert not research._is_retryable_research_error(error)
