"""Fast, isolated failure-path tests for external integrations.

All external clients are replaced with mocks. No live credentials, SMTP/IMAP
connections, Supabase writes, or production records are used.
"""
import pytest

import email_inbox
import email_utils
import jarvis_common


def test_missing_gemini_key_fails_before_client_creation(monkeypatch):
    monkeypatch.setattr(jarvis_common, "get_secret", lambda _name, default=None: default)
    monkeypatch.setattr(
        jarvis_common.genai, "Client",
        lambda **_kwargs: pytest.fail("Gemini client must not be created without a key"),
    )

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        jarvis_common.get_gemini_client()


def test_missing_supabase_url_fails_before_network_client_creation(monkeypatch):
    monkeypatch.setattr(jarvis_common, "get_secret", lambda _name, default=None: default)
    monkeypatch.setattr(
        jarvis_common, "create_client",
        lambda *_args, **_kwargs: pytest.fail("Supabase client must not be created without URL"),
    )

    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        jarvis_common.get_supabase()


def test_missing_smtp_credentials_fail_before_opening_smtp(monkeypatch):
    monkeypatch.setattr(email_utils, "EMAIL_DELIVERY_ENABLED", True)
    monkeypatch.setattr(
        email_utils, "required_secret",
        lambda name: (_ for _ in ()).throw(RuntimeError(f"missing {name}")),
    )
    monkeypatch.setattr(
        email_utils.smtplib, "SMTP",
        lambda *_args, **_kwargs: pytest.fail("SMTP connection must not be opened"),
    )

    with pytest.raises(RuntimeError, match="EMAIL_USER"):
        email_utils.send_email("recipient@example.test", "Subject", "Body")


def test_disabled_inbox_monitor_does_not_read_secrets_or_connect(monkeypatch, capsys):
    monkeypatch.setattr(email_inbox, "env_bool", lambda _name, default=False: default)
    monkeypatch.setattr(
        email_inbox, "get_secret",
        lambda *_args, **_kwargs: pytest.fail("Disabled inbox must not read IMAP settings"),
    )
    monkeypatch.setattr(
        email_inbox, "required_secret",
        lambda *_args, **_kwargs: pytest.fail("Disabled inbox must not read credentials"),
    )
    monkeypatch.setattr(
        email_inbox.imaplib, "IMAP4_SSL",
        lambda *_args, **_kwargs: pytest.fail("Disabled inbox must not connect to IMAP"),
    )
    monkeypatch.setattr(
        email_inbox, "get_supabase",
        lambda: pytest.fail("Disabled inbox must not access Supabase"),
    )

    assert email_inbox._run() == 0
    assert "kihagyva" in capsys.readouterr().out


def test_invalid_boolean_configuration_uses_safe_false_value(monkeypatch):
    monkeypatch.setattr(jarvis_common, "get_secret", lambda _name: "definitely")
    assert jarvis_common.env_bool("EMAIL_DELIVERY_ENABLED", False) is False


def test_invalid_integer_configuration_uses_bounded_default(monkeypatch):
    monkeypatch.setattr(jarvis_common, "get_secret", lambda _name: "not-an-integer")
    assert jarvis_common.env_int("SEND_MAX_PER_RUN", 3, minimum=1, maximum=10) == 3


def test_supabase_read_failure_does_not_break_local_configuration_helpers(monkeypatch):
    class BrokenDatabase:
        def table(self, _name):
            raise ConnectionError("mocked Supabase outage")

    reports = []
    monkeypatch.setattr(
        jarvis_common, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )

    assert jarvis_common.get_setting(BrokenDatabase(), "ui_theme", default="light") == "light"
    # Local parsing remains usable while the remote dependency is unavailable.
    monkeypatch.setattr(jarvis_common, "get_secret", lambda _name: "7")
    assert jarvis_common.env_int("LOCAL_LIMIT", 1, minimum=1, maximum=10) == 7
    assert len(reports) == 1
    assert reports[0][1]["module"] == "jarvis_common"
