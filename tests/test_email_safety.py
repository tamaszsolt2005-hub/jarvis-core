"""Safety checks: outbound email is hard-disabled until a reviewed code change."""
import email_sender
import follow_up


def test_first_contact_job_is_disabled_by_default(monkeypatch, capsys):
    monkeypatch.setattr(email_sender, "env_bool", lambda name, default=False: default)
    monkeypatch.setattr(
        email_sender, "get_service_supabase",
        lambda: (_ for _ in ()).throw(AssertionError("Supabase must not be accessed")),
    )

    email_sender.run()

    assert "nem kerül kiküldésre" in capsys.readouterr().out


def test_follow_up_job_is_disabled_by_default(monkeypatch, capsys):
    monkeypatch.setattr(follow_up, "env_bool", lambda name, default=False: default)
    monkeypatch.setattr(
        follow_up, "get_service_supabase",
        lambda: (_ for _ in ()).throw(AssertionError("Supabase must not be accessed")),
    )

    follow_up.run()

    assert "nem kerül kiküldésre" in capsys.readouterr().out


def test_first_contact_requires_explicit_timestamped_consent():
    assert email_sender._valid_consent({
        "consent_basis": "consent",
        "approved_to_contact": True,
        "opted_out": False,
        "consent_confirmed_at": "2026-11-14T12:00:00+00:00",
    })
    assert not email_sender._valid_consent({
        "consent_basis": "consent",
        "approved_to_contact": True,
        "opted_out": False,
        "consent_confirmed_at": None,
    })
    assert not email_sender._valid_consent({
        "consent_basis": "consent",
        "approved_to_contact": True,
        "opted_out": True,
        "consent_confirmed_at": "2026-11-14T12:00:00+00:00",
    })


def test_first_contact_rejects_timezone_naive_consent_timestamp():
    assert not email_sender._valid_consent({
        "consent_basis": "consent",
        "approved_to_contact": True,
        "opted_out": False,
        "consent_confirmed_at": "2026-11-14T12:00:00",
    })


def test_email_jobs_remain_disabled_even_if_environment_flags_are_true(monkeypatch, capsys):
    monkeypatch.setattr(email_sender, "env_bool", lambda name, default=False: True)
    monkeypatch.setattr(follow_up, "env_bool", lambda name, default=False: True)
    monkeypatch.setattr(
        email_sender, "get_service_supabase",
        lambda: (_ for _ in ()).throw(AssertionError("SMTP job must not access Supabase")),
    )
    monkeypatch.setattr(
        follow_up, "get_service_supabase",
        lambda: (_ for _ in ()).throw(AssertionError("SMTP job must not access Supabase")),
    )
    email_sender.run()
    follow_up.run()
    output = capsys.readouterr().out
    assert "nem kerül kiküldésre" in output


def test_smtp_transport_is_hard_disabled_even_when_environment_flag_is_true(monkeypatch):
    import email_utils

    monkeypatch.setenv("EMAIL_DELIVERY_ENABLED", "true")
    monkeypatch.setattr(
        email_utils, "get_enforced_user_supabase",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Auth/database must not be accessed")),
    )
    monkeypatch.setattr(
        email_utils, "required_secret",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("SMTP credentials must not be read")),
    )
    monkeypatch.setattr(
        email_utils.smtplib, "SMTP",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("SMTP must not be opened")),
    )

    assert email_utils.EMAIL_DELIVERY_ENABLED is False
    try:
        email_utils.send_email("person@example.com", "Test", "Test", approved=True)
    except RuntimeError as exc:
        assert "kódszinten letiltva" in str(exc)
    else:
        raise AssertionError("Direct SMTP call must be blocked")


def test_smtp_data_submission_failure_is_classified_as_unknown(monkeypatch):
    import email_utils

    class FakeSMTP:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def ehlo(self):
            return None

        def starttls(self):
            return None

        def login(self, *_args):
            return None

        def send_message(self, _message):
            raise OSError("connection lost while waiting for SMTP DATA response")

    monkeypatch.setattr(email_utils, "EMAIL_DELIVERY_ENABLED", True)
    monkeypatch.setattr(email_utils, "get_enforced_user_supabase", lambda *_a, **_k: None)
    monkeypatch.setattr(email_utils, "required_secret", lambda name: {
        "EMAIL_USER": "sender@example.com", "EMAIL_PASSWORD": "not-a-real-secret"
    }[name])
    monkeypatch.setattr(email_utils, "get_secret", lambda name, default=None: default)
    monkeypatch.setattr(email_utils.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(email_utils, "report_error", lambda *_a, **_k: None)

    try:
        email_utils.send_email("person@example.com", "Subject", "Body", approved=True)
    except email_utils.EmailDeliveryOutcomeUnknown as exc:
        assert "automatikus újraküldés tilos" in str(exc)
    else:
        raise AssertionError("An uncertain SMTP DATA result must not look successful")


def test_smtp_connection_failure_is_not_misclassified_as_delivery_unknown(monkeypatch):
    import email_utils

    class FailingSMTP:
        def __init__(self, *_args, **_kwargs):
            raise OSError("connection refused before SMTP session")

    monkeypatch.setattr(email_utils, "EMAIL_DELIVERY_ENABLED", True)
    monkeypatch.setattr(email_utils, "get_enforced_user_supabase", lambda *_a, **_k: None)
    monkeypatch.setattr(email_utils, "required_secret", lambda name: {
        "EMAIL_USER": "sender@example.com", "EMAIL_PASSWORD": "not-a-real-secret"
    }[name])
    monkeypatch.setattr(email_utils, "get_secret", lambda name, default=None: default)
    monkeypatch.setattr(email_utils.smtplib, "SMTP", FailingSMTP)
    monkeypatch.setattr(email_utils, "report_error", lambda *_a, **_k: None)

    try:
        email_utils.send_email("person@example.com", "Subject", "Body", approved=True)
    except email_utils.EmailDeliveryOutcomeUnknown:
        raise AssertionError("A pre-session connection failure is a known non-delivery")
    except OSError as exc:
        assert "connection refused" in str(exc)
    else:
        raise AssertionError("The simulated SMTP connection must fail")
