"""Resend provider contract tests; all HTTP traffic is mocked."""
import requests
import pytest

import email_utils


def _enable_resend(monkeypatch, post):
    monkeypatch.setattr(email_utils, "EMAIL_DELIVERY_ENABLED", True)
    monkeypatch.setattr(email_utils, "get_enforced_user_supabase", lambda *_a, **_k: None)
    monkeypatch.setattr(email_utils, "get_secret", lambda name, default=None: {
        "EMAIL_PROVIDER": "resend",
        "EMAIL_FROM_NAME": "JARVIS",
    }.get(name, default))
    monkeypatch.setattr(email_utils, "required_secret", lambda name: {
        "EMAIL_USER": "sender@example.test",
        "RESEND_API_KEY": "test-api-key",
    }[name])
    monkeypatch.setattr(email_utils.requests, "post", post)
    monkeypatch.setattr(email_utils, "report_error", lambda *_a, **_k: None)


def test_resend_receives_stable_idempotency_key_and_returns_provider_id(monkeypatch):
    calls = []

    class Response:
        status_code = 200
        def raise_for_status(self):
            return None
        def json(self):
            return {"id": "re_test_message"}

    def post(*args, **kwargs):
        calls.append((args, kwargs))
        return Response()

    _enable_resend(monkeypatch, post)
    result = email_utils.send_email(
        "recipient@example.test", "Subject", "Body", "stable-operation-id", approved=True
    )

    assert result == "re_test_message"
    assert calls[0][0][0] == "https://api.resend.com/emails"
    assert calls[0][1]["headers"]["Idempotency-Key"] == "stable-operation-id"
    assert calls[0][1]["headers"]["Authorization"] == "Bearer test-api-key"
    assert calls[0][1]["json"]["to"] == ["recipient@example.test"]
    assert calls[0][1]["json"]["text"] == "Body"
    assert calls[0][1]["allow_redirects"] is False


@pytest.mark.parametrize("status_code", [409, 429, 500, 503])
def test_resend_ambiguous_status_is_not_reported_as_known_failure(monkeypatch, status_code):
    class Response:
        def __init__(self):
            self.status_code = status_code
        def raise_for_status(self):
            raise requests.HTTPError(f"HTTP {status_code}")

    _enable_resend(monkeypatch, lambda *_a, **_k: Response())
    with pytest.raises(email_utils.EmailDeliveryOutcomeUnknown):
        email_utils.send_email(
            "recipient@example.test", "Subject", "Body", "stable-operation-id", approved=True
        )


def test_resend_network_timeout_is_unknown_and_not_retried(monkeypatch):
    def post(*_args, **_kwargs):
        raise requests.Timeout("read timed out after request body")

    _enable_resend(monkeypatch, post)
    with pytest.raises(email_utils.EmailDeliveryOutcomeUnknown):
        email_utils.send_email(
            "recipient@example.test", "Subject", "Body", "stable-operation-id", approved=True
        )


def test_resend_rejects_missing_idempotency_key_before_network(monkeypatch):
    calls = []
    _enable_resend(monkeypatch, lambda *_a, **_k: calls.append(True))
    with pytest.raises(ValueError):
        email_utils.send_email("recipient@example.test", "Subject", "Body", approved=True)
    assert calls == []


def test_resend_4xx_rejection_is_known_non_delivery(monkeypatch):
    class Response:
        status_code = 422
        def raise_for_status(self):
            raise requests.HTTPError("invalid sender")
    _enable_resend(monkeypatch, lambda *_a, **_k: Response())
    with pytest.raises(requests.HTTPError):
        email_utils.send_email(
            "recipient@example.test", "Subject", "Body", "stable-operation-id", approved=True
        )
