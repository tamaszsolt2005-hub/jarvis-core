"""SMTP delivery helper. Outbound delivery is hard-disabled pending security review."""
from __future__ import annotations

import smtplib
import re
from email.message import EmailMessage
from email.utils import formataddr

from jarvis_common import get_secret, required_secret, get_enforced_user_supabase
from jarvis_errors import report_error

# Deliberately not environment-controlled: enabling SMTP requires a reviewed code change.
EMAIL_DELIVERY_ENABLED = False
_EMAIL_ADDRESS_RE = re.compile(r"^[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+$")


class EmailDeliveryOutcomeUnknown(RuntimeError):
    """SMTP may have accepted the message, but the client did not receive confirmation.

    Callers must not automatically retry this outcome because doing so could send
    a duplicate message. Failures before send_message remain known non-deliveries.
    """


def send_email(
    recipient: str, subject: str, body: str, *,
    auth_session: dict[str, str] | None = None, approved: bool = False,
) -> str:
    # Fail before auth/database/secret access: no runtime flag or approval can enable SMTP.
    if not EMAIL_DELIVERY_ENABLED:
        raise RuntimeError("Kimenő e-mailküldés kódszinten letiltva; külön felülvizsgált kódmódosítás szükséges.")

    enforced = get_enforced_user_supabase(
        auth_session, "email.send", allowed_roles={"admin", "operator"}
    )
    if enforced is not None and approved is not True:
        raise PermissionError("E-mail-küldéshez külön, explicit jóváhagyás szükséges.")
    if (
        not isinstance(recipient, str)
        or recipient.strip() != recipient
        or not _EMAIL_ADDRESS_RE.fullmatch(recipient)
    ):
        raise ValueError("Érvénytelen vagy nem egyetlen címzettet tartalmazó e-mail-cím.")
    if (
        not isinstance(subject, str)
        or not subject.strip()
        or "\r" in subject
        or "\n" in subject
        or len(subject) > 200
    ):
        raise ValueError("Érvénytelen e-mail tárgy.")
    if not isinstance(body, str) or len(body) > 50000:
        raise ValueError("Érvénytelen e-mail törzs.")

    sender = required_secret("EMAIL_USER")
    password = required_secret("EMAIL_PASSWORD")
    if not _EMAIL_ADDRESS_RE.fullmatch(sender):
        raise ValueError("Az EMAIL_USER nem érvényes e-mail-cím.")
    from_name = get_secret("EMAIL_FROM_NAME", "JARVIS") or "JARVIS"
    if "\r" in from_name or "\n" in from_name:
        raise ValueError("Érvénytelen feladó név.")
    host = get_secret("SMTP_HOST", "smtp.gmail.com") or "smtp.gmail.com"
    port = int(get_secret("SMTP_PORT", "587") or "587")
    if not 1 <= port <= 65535:
        raise ValueError("SMTP_PORT must be between 1 and 65535.")

    message = EmailMessage()
    message["From"] = formataddr((from_name, sender))
    message["To"] = recipient
    message["Reply-To"] = sender
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender, password)
            try:
                server.send_message(message)
            except Exception as exc:
                # The server may have accepted DATA before the connection failed.
                raise EmailDeliveryOutcomeUnknown(
                    "Az SMTP-kézbesítés kimenetele bizonytalan; automatikus újraküldés tilos."
                ) from exc
    except Exception as exc:
        report_error(
            exc, module="email_utils", operation="smtp_delivery",
            severity="critical",
        )
        raise
    return str(message.get("Message-ID") or "")
