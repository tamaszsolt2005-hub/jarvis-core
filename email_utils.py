"""Email delivery adapter. All outbound delivery is hard-disabled pending review."""
from __future__ import annotations

import re
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

import requests

from jarvis_common import get_secret, required_secret, get_enforced_user_supabase
from jarvis_errors import report_error

# Deliberately not environment-controlled: no outbound provider can be enabled by config.
EMAIL_DELIVERY_ENABLED = False
_EMAIL_ADDRESS_RE = re.compile(r"^[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+$")


class EmailDeliveryOutcomeUnknown(RuntimeError):
    """The provider may have accepted the message, but confirmation was not received.

    Callers must not automatically retry this outcome. Provider idempotency keys
    reduce duplicate risk, but do not replace reconciliation of an unknown send.
    """


def _send_via_resend(
    recipient: str, subject: str, body: str, *,
    sender: str, from_name: str, idempotency_key: str,
) -> str:
    if not isinstance(idempotency_key, str) or not idempotency_key.strip() or len(idempotency_key) > 256:
        raise ValueError("A Resend küldéshez érvényes idempotenciakulcs szükséges.")
    if not _EMAIL_ADDRESS_RE.fullmatch(sender):
        raise ValueError("Az EMAIL_USER nem érvényes feladó e-mail-cím.")
    if "\r" in from_name or "\n" in from_name:
        raise ValueError("Érvénytelen feladó név.")

    api_key = required_secret("RESEND_API_KEY")
    payload = {
        "from": formataddr((from_name, sender)),
        "to": [recipient],
        "subject": subject,
        "text": body,
        "reply_to": sender,
    }
    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
            },
            json=payload,
            timeout=(5, 20),
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        report_error(
            exc, module="email_utils", operation="resend_delivery",
            severity="critical",
        )
        raise EmailDeliveryOutcomeUnknown(
            "A Resend API kérésének kimenetele bizonytalan; automatikus újraküldés tilos."
        ) from exc

    # Resend documents 409 for an in-flight or payload-mismatched idempotent
    # request. A 429/5xx can also be ambiguous, so none is retried automatically.
    if response.status_code == 409 or response.status_code == 429 or response.status_code >= 500:
        error = RuntimeError(f"Resend returned an ambiguous HTTP status: {response.status_code}")
        report_error(
            error, module="email_utils", operation="resend_delivery",
            severity="critical",
        )
        raise EmailDeliveryOutcomeUnknown(
            "A Resend API válasza bizonytalan; automatikus újraküldés tilos."
        ) from error

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        report_error(
            exc, module="email_utils", operation="resend_delivery",
            severity="error",
        )
        raise
    if not 200 <= response.status_code < 300:
        raise RuntimeError(f"Unexpected Resend HTTP status: {response.status_code}")
    try:
        message_id = response.json().get("id")
    except (AttributeError, ValueError, TypeError) as exc:
        message_id = None
        parse_error = exc
    else:
        parse_error = None
    if not isinstance(message_id, str) or not message_id.strip():
        error = parse_error or RuntimeError("Resend response did not contain a message id")
        report_error(
            error, module="email_utils", operation="resend_delivery",
            severity="critical",
        )
        raise EmailDeliveryOutcomeUnknown(
            "A Resend elfogadhatta a levelet, de a message ID nem olvasható; automatikus újraküldés tilos."
        ) from error
    return message_id


def send_email(
    recipient: str, subject: str, body: str, idempotency_key: str | None = None, *,
    auth_session: dict[str, str] | None = None, approved: bool = False,
) -> str:
    # Fail before auth/database/secret access: no runtime flag or approval can enable delivery.
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

    provider = (get_secret("EMAIL_PROVIDER", "smtp") or "smtp").strip().lower()
    if provider == "resend":
        sender = required_secret("EMAIL_USER")
        from_name = get_secret("EMAIL_FROM_NAME", "JARVIS") or "JARVIS"
        return _send_via_resend(
            recipient, subject, body, sender=sender, from_name=from_name,
            idempotency_key=idempotency_key or "",
        )
    if provider != "smtp":
        raise ValueError("EMAIL_PROVIDER csak 'smtp' vagy 'resend' lehet.")

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
