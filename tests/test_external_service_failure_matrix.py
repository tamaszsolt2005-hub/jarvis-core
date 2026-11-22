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


@pytest.mark.parametrize("missing_name", ["EMAIL_USER", "EMAIL_PASSWORD"])
def test_missing_smtp_credentials_fail_before_opening_smtp(monkeypatch, missing_name):
    monkeypatch.setattr(email_utils, "EMAIL_DELIVERY_ENABLED", True)
    monkeypatch.setattr(
        email_utils, "required_secret",
        lambda name: (_ for _ in ()).throw(RuntimeError(f"missing {name}")) if name == missing_name else "mock-value",
    )
    monkeypatch.setattr(
        email_utils.smtplib, "SMTP",
        lambda *_args, **_kwargs: pytest.fail("SMTP connection must not be opened"),
    )

    with pytest.raises(RuntimeError, match=missing_name):
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


@pytest.mark.parametrize("bad_port", ["not-a-port", "0", "-1", "70000"])
def test_invalid_smtp_port_fails_before_network_connection(monkeypatch, bad_port):
    monkeypatch.setattr(email_utils, "EMAIL_DELIVERY_ENABLED", True)
    monkeypatch.setattr(
        email_utils, "required_secret",
        lambda name: "sender@example.test" if name == "EMAIL_USER" else "test-password",
    )
    monkeypatch.setattr(
        email_utils, "get_secret",
        lambda name, default=None: bad_port if name == "SMTP_PORT" else default,
    )
    monkeypatch.setattr(
        email_utils.smtplib, "SMTP",
        lambda *_args, **_kwargs: pytest.fail("Invalid SMTP configuration must fail before connecting"),
    )

    with pytest.raises(ValueError):
        email_utils.send_email("recipient@example.test", "Subject", "Body")


@pytest.mark.parametrize("bad_port", ["not-a-port", "0", "-1", "70000"])
def test_invalid_imap_port_fails_before_network_or_database_access(monkeypatch, bad_port):
    monkeypatch.setattr(email_inbox, "env_bool", lambda _name, default=False: True)
    monkeypatch.setattr(
        email_inbox, "get_secret",
        lambda name, default=None: bad_port if name == "IMAP_PORT" else default,
    )
    monkeypatch.setattr(email_inbox, "required_secret", lambda _name: "test-credential")
    monkeypatch.setattr(
        email_inbox.imaplib, "IMAP4_SSL",
        lambda *_args, **_kwargs: pytest.fail("Invalid IMAP port must fail before connecting"),
    )
    monkeypatch.setattr(
        email_inbox, "get_supabase",
        lambda: pytest.fail("Invalid IMAP port must fail before database access"),
    )

    with pytest.raises(ValueError):
        email_inbox._run()


def test_smtp_transport_outage_is_propagated_without_real_network(monkeypatch):
    monkeypatch.setattr(email_utils, "EMAIL_DELIVERY_ENABLED", True)
    monkeypatch.setattr(
        email_utils, "required_secret",
        lambda name: "sender@example.test" if name == "EMAIL_USER" else "mock-password",
    )
    monkeypatch.setattr(email_utils, "get_secret", lambda _name, default=None: default)

    class OfflineSMTP:
        def __enter__(self):
            raise OSError("mock SMTP unavailable")

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(email_utils.smtplib, "SMTP", lambda *_args, **_kwargs: OfflineSMTP())

    with pytest.raises(OSError, match="mock SMTP unavailable"):
        email_utils.send_email("recipient@example.test", "Subject", "Body")


def test_gemini_overload_uses_mocked_fallback_model(monkeypatch):
    calls = []

    class Overloaded(Exception):
        code = 503

    class Models:
        def generate_content(self, *, model, contents, config):
            calls.append((model, contents, config.max_output_tokens))
            if model == "configured-primary":
                raise Overloaded("temporary overload")
            return type("Response", (), {"text": "mocked fallback answer"})()

    client = type("Client", (), {"models": Models()})()
    monkeypatch.setattr(jarvis_common, "get_model_name", lambda: "configured-primary")
    monkeypatch.setattr(jarvis_common, "env_int", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(jarvis_common.time, "sleep", lambda *_args: None)

    assert jarvis_common.generate_text("test prompt", client=client) == "mocked fallback answer"
    assert [call[0] for call in calls] == ["configured-primary", "gemini-3.8-flash"]


@pytest.mark.parametrize("raw", ["", "abc", "1.5", "999999999999999999999999"])
def test_integer_configuration_never_crashes_local_helpers(monkeypatch, raw):
    monkeypatch.setattr(jarvis_common, "get_secret", lambda _name: raw)
    expected = 10 if raw.isdigit() and int(raw) > 10 else 4
    assert jarvis_common.env_int("LOCAL_LIMIT", 4, minimum=1, maximum=10) == expected


def test_missing_supabase_api_key_fails_before_client_creation(monkeypatch):
    monkeypatch.setattr(
        jarvis_common, "get_secret",
        lambda name, default=None: "https://example.supabase.test" if name == "SUPABASE_URL" else default,
    )
    monkeypatch.setattr(
        jarvis_common, "create_client",
        lambda *_args, **_kwargs: pytest.fail("Supabase client must not be created without an API key"),
    )

    with pytest.raises(RuntimeError, match="SUPABASE_KEY"):
        jarvis_common.get_supabase()


@pytest.mark.parametrize("missing_name", ["EMAIL_USER", "EMAIL_PASSWORD"])
def test_missing_imap_credentials_fail_before_connecting_or_database_access(monkeypatch, missing_name):
    monkeypatch.setattr(email_inbox, "env_bool", lambda _name, default=False: True)
    monkeypatch.setattr(email_inbox, "get_secret", lambda _name, default=None: default)
    monkeypatch.setattr(
        email_inbox, "required_secret",
        lambda name: (_ for _ in ()).throw(RuntimeError(f"missing {name}")) if name == missing_name else "mock-value",
    )
    monkeypatch.setattr(
        email_inbox.imaplib, "IMAP4_SSL",
        lambda *_args, **_kwargs: pytest.fail("IMAP must not connect without credentials"),
    )
    monkeypatch.setattr(
        email_inbox, "get_supabase",
        lambda: pytest.fail("Supabase must not be initialized without IMAP credentials"),
    )

    with pytest.raises(RuntimeError, match=missing_name):
        email_inbox._run()


def test_invalid_email_subject_is_rejected_before_smtp_connection(monkeypatch):
    monkeypatch.setattr(email_utils, "EMAIL_DELIVERY_ENABLED", True)
    monkeypatch.setattr(
        email_utils, "required_secret",
        lambda name: "sender@example.test" if name == "EMAIL_USER" else "mock-password",
    )
    monkeypatch.setattr(email_utils, "get_secret", lambda _name, default=None: default)
    monkeypatch.setattr(
        email_utils.smtplib, "SMTP",
        lambda *_args, **_kwargs: pytest.fail("Invalid header input must fail before SMTP connection"),
    )

    with pytest.raises(ValueError):
        email_utils.send_email("recipient@example.test", "Subject\r\nBcc: attacker@example.test", "Body")


def test_imap_transport_outage_is_reported_and_propagated(monkeypatch):
    monkeypatch.setattr(email_inbox, "env_bool", lambda _name, default=False: True)
    monkeypatch.setattr(email_inbox, "get_secret", lambda _name, default=None: default)
    monkeypatch.setattr(email_inbox, "required_secret", lambda _name: "mock-credential")
    monkeypatch.setattr(email_inbox, "get_supabase", lambda: object())
    monkeypatch.setattr(
        email_inbox.imaplib, "IMAP4_SSL",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("mock IMAP unavailable")),
    )
    reports = []
    monkeypatch.setattr(
        email_inbox, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )

    with pytest.raises(OSError, match="mock IMAP unavailable"):
        email_inbox.run()
    assert len(reports) == 1
    assert reports[0][1]["module"] == "email_inbox"
    assert reports[0][1]["operation"] == "process_inbox"
