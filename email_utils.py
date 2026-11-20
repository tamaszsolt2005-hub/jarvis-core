"""SMTP delivery helper with a disabled-by-default safety gate."""
from __future__ import annotations

import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from jarvis_common import env_bool, get_secret, required_secret

# Must be explicitly enabled in the server-side environment/secrets.
EMAIL_DELIVERY_ENABLED = env_bool("EMAIL_DELIVERY_ENABLED", False)


def send_email(recipient: str, subject: str, body: str) -> str:
    if not EMAIL_DELIVERY_ENABLED:
        raise RuntimeError("E-mail-küldés letiltva (kódszinten le van tiltva) biztonsági okból.")
    sender = required_secret("EMAIL_USER")
    password = required_secret("EMAIL_PASSWORD")
    from_name = get_secret("EMAIL_FROM_NAME", "JARVIS") or "JARVIS"
    host = get_secret("SMTP_HOST", "smtp.gmail.com") or "smtp.gmail.com"
    port = int(get_secret("SMTP_PORT", "587") or "587")

    message = EmailMessage()
    message["From"] = formataddr((from_name, sender))
    message["To"] = recipient
    message["Reply-To"] = sender
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(sender, password)
        server.send_message(message)
    return str(message.get("Message-ID") or "")
