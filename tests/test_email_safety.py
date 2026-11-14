"""Safety checks: outreach jobs must remain inert unless explicitly enabled."""
import email_sender
import follow_up


def test_first_contact_job_is_disabled_by_default(monkeypatch, capsys):
    monkeypatch.setattr(email_sender, "env_bool", lambda name, default=False: default)
    monkeypatch.setattr(
        email_sender, "get_supabase",
        lambda: (_ for _ in ()).throw(AssertionError("Supabase must not be accessed")),
    )

    email_sender.run()

    assert "nem kerül kiküldésre" in capsys.readouterr().out


def test_follow_up_job_is_disabled_by_default(monkeypatch, capsys):
    monkeypatch.setattr(follow_up, "env_bool", lambda name, default=False: default)
    monkeypatch.setattr(
        follow_up, "get_supabase",
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
