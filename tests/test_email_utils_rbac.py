import pytest

import email_utils


def test_email_send_denies_missing_auth_session_before_smtp(monkeypatch):
    import jarvis_common

    monkeypatch.setattr(jarvis_common, "env_bool", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        jarvis_common, "get_user_supabase",
        lambda *_args, **_kwargs: pytest.fail("Missing session must be denied before SMTP"),
    )
    monkeypatch.setattr(email_utils, "EMAIL_DELIVERY_ENABLED", True)

    with pytest.raises(PermissionError, match="Auth-munkamenet"):
        email_utils.send_email("client@example.com", "Teszt", "Tartalom")


def test_email_send_requires_explicit_approval_in_enforced_mode(monkeypatch):
    monkeypatch.setattr(
        email_utils, "get_enforced_user_supabase",
        lambda *_args, **_kwargs: (object(), {"role": "operator"}),
    )
    monkeypatch.setattr(email_utils, "EMAIL_DELIVERY_ENABLED", True)

    with pytest.raises(PermissionError, match="explicit"):
        email_utils.send_email(
            "client@example.com", "Teszt", "Tartalom",
            auth_session={"access_token": "a"}, approved=False,
        )
