"""Read recent Gmail replies, classify them and stop future outreach.

This legacy IMAP worker is not scheduled or enabled by the chat application.
"""
from __future__ import annotations

import email
import imaplib
from email.header import decode_header
from email.utils import parseaddr

from jarvis_common import get_secret, get_supabase, log_event
from jarvis_errors import report_error
from reply_analyzer import classify_reply


def _decode(value):
    if not value:
        return ""
    out = []
    for part, encoding in decode_header(value):
        out.append(part.decode(encoding or "utf-8", errors="replace") if isinstance(part, bytes) else part)
    return " ".join(out)


def _body(msg):
    chunks = []
    parts = msg.walk() if msg.is_multipart() else [msg]
    for part in parts:
        if part.get_content_type() == "text/plain" and part.get_content_disposition() != "attachment":
            payload = part.get_payload(decode=True)
            if payload:
                chunks.append(payload.decode(part.get_content_charset() or "utf-8", errors="replace"))
    return "\n".join(chunks)[:10000]


def _pending_messages(messages, last_seen_message_id):
    """Return unseen (sequence_id, message) pairs, oldest first."""
    messages = list(messages or [])
    if not messages:
        return []
    if last_seen_message_id:
        marker_indexes = [
            index for index, (_sequence_id, message) in enumerate(messages)
            if message.get("Message-ID") == last_seen_message_id
        ]
        if marker_indexes:
            return messages[marker_indexes[-1] + 1:]
        return messages[-1:]
    return messages


def _run():
    user = get_secret("EMAIL_USER")
    password = get_secret("EMAIL_PASSWORD")
    if not user or not password:
        print("Inbox monitor kihagyva: hiányzik az EMAIL_USER vagy EMAIL_PASSWORD.")
        return

    db = get_supabase()
    leads = db.table("leads").select("*").in_("status", ["sent", "followed_up"]).limit(300).execute().data or []
    mail = imaplib.IMAP4_SSL(get_secret("IMAP_HOST", "imap.gmail.com"), int(get_secret("IMAP_PORT", "993")))
    try:
        mail.login(user, password)
        mail.select("INBOX")
        for lead in leads:
            address = str(lead.get("email") or "").replace('"', "").strip()
            if not address:
                continue
            status, data = mail.search(None, "FROM", f'"{address}"')
            if status != "OK" or not data or not data[0]:
                continue

            fetched = []
            for sequence_id in data[0].split()[-5:]:
                fetch_status, raw = mail.fetch(sequence_id, "(RFC822)")
                if fetch_status != "OK" or not raw or not isinstance(raw[0], tuple):
                    continue
                msg = email.message_from_bytes(raw[0][1])
                message_id = msg.get("Message-ID")
                sender = parseaddr(msg.get("From", ""))[1]
                if message_id and sender.lower() == address.lower():
                    fetched.append((sequence_id, msg))

            for _sequence_id, msg in _pending_messages(fetched, lead.get("last_inbound_message_id")):
                message_id = msg.get("Message-ID")
                category = classify_reply(_body(msg))
                opted_out = bool(lead.get("opted_out")) or category == "opt_out"
                effective_category = "opt_out" if opted_out else category
                update = {
                    "status": "opted_out" if opted_out else "replied",
                    "reply_category": effective_category,
                    "opted_out": opted_out,
                    "next_follow_up_at": None,
                    "last_inbound_message_id": message_id,
                }
                db.table("leads").update(update).eq("id", lead["id"]).execute()
                lead["opted_out"] = opted_out
                log_event(db, "inbox_monitor", f"Válasz feldolgozva ({category}): {lead.get('company_name')}")
    finally:
        try:
            mail.logout()
        except Exception as exc:
            report_error(
                exc,
                module="inbox_monitor",
                operation="close_imap_connection",
                severity="warning",
                db=db,
            )


def run():
    """Run the legacy IMAP worker, reporting failures without hiding them."""
    try:
        _run()
    except Exception as exc:
        report_error(
            exc,
            module="inbox_monitor",
            operation="process_inbox_monitor",
            severity="error",
        )
        raise


if __name__ == "__main__":
    run()
