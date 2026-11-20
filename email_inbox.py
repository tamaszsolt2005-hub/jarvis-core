"""Stop automated follow-ups when a recipient replies or opts out."""
from __future__ import annotations

import imaplib
from email import message_from_bytes
from email.header import decode_header
from email.utils import parseaddr

from jarvis_common import env_bool, get_secret, get_supabase, log_event, required_secret

OPTOUT_TERMS = (
    "leiratkozom", "leiratkozás", "leiratkozas", "unsubscribe", "remove me", "stop emailing",
    "ne keressen", "ne keressetek", "töröljenek", "toroljenek",
)


def _decode(value: str | None) -> str:
    if not value:
        return ""
    parts = []
    for chunk, encoding in decode_header(value):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(encoding or "utf-8", errors="replace"))
        else:
            parts.append(chunk)
    return " ".join(parts)


def _body(message) -> str:
    chunks = []
    parts = message.walk() if message.is_multipart() else [message]
    for part in parts:
        if part.get_content_type() != "text/plain" or part.get_content_disposition() == "attachment":
            continue
        payload = part.get_payload(decode=True) or b""
        charset = part.get_content_charset() or "utf-8"
        chunks.append(payload.decode(charset, errors="replace"))
    return "\n".join(chunks)[:12000]


def _is_optout(subject: str, body: str) -> bool:
    text = f"{subject}\n{body}".casefold()
    return any(term in text for term in OPTOUT_TERMS)



def _uids_to_process(uids: list[bytes], checkpoint: dict, uidvalidity: str) -> list[bytes]:
    """Process the initial 200 messages, then every new UID since the last successful run."""
    if not checkpoint or str(checkpoint.get("uidvalidity")) != str(uidvalidity):
        return uids[-200:]
    try:
        last_uid = int(checkpoint.get("last_uid") or 0)
    except (TypeError, ValueError):
        last_uid = 0
    return [uid for uid in uids if int(uid) > last_uid]


def _load_checkpoint(db) -> dict:
    rows = (
        db.table("settings").select("value")
        .eq("key", "email_inbox_uid_checkpoint").limit(1).execute().data or []
    )
    value = rows[0].get("value") if rows else {}
    return value if isinstance(value, dict) else {}


def _save_checkpoint(db, uidvalidity: str, last_uid: int) -> None:
    db.table("settings").upsert({
        "key": "email_inbox_uid_checkpoint",
        "value": {"uidvalidity": str(uidvalidity), "last_uid": int(last_uid)},
    }).execute()

def run() -> int:
    if not env_bool("EMAIL_INBOX_MONITOR_ENABLED", False):
        print("Inbox-ellenőrzés kihagyva: EMAIL_INBOX_MONITOR_ENABLED nincs engedélyezve.")
        return 0
    host = get_secret("IMAP_HOST", "imap.gmail.com") or "imap.gmail.com"
    port = int(get_secret("IMAP_PORT", "993") or "993")
    username = required_secret("EMAIL_USER")
    password = required_secret("EMAIL_PASSWORD")
    db = get_supabase()
    processed = 0

    with imaplib.IMAP4_SSL(host, port) as mailbox:
        mailbox.login(username, password)
        mailbox.select("INBOX", readonly=True)
        status, data = mailbox.uid("search", None, "ALL")
        if status != "OK":
            raise RuntimeError("Az IMAP INBOX keresése sikertelen.")
        uids = (data[0] or b"").split()
        uidvalidity_response = mailbox.response("UIDVALIDITY")
        uidvalidity_data = (uidvalidity_response[1] or []) if uidvalidity_response else []
        uidvalidity = uidvalidity_data[0].decode(errors="replace") if uidvalidity_data else "unknown"
        checkpoint = _load_checkpoint(db)
        pending_uids = _uids_to_process(uids, checkpoint, uidvalidity)
        leads = db.table("leads").select(
            "id,email,status,opted_out,last_inbound_message_id"
        ).not_.is_("email", "null").limit(5000).execute().data or []
        by_email = {str(row.get("email") or "").casefold(): row for row in leads}
        for uid in pending_uids:
            status, fetched = mailbox.uid("fetch", uid, "(RFC822)")
            if status != "OK" or not fetched or not isinstance(fetched[0], tuple):
                raise RuntimeError("Egy új IMAP üzenet lekérése sikertelen; a UID checkpoint nem lépett tovább.")
            message = message_from_bytes(fetched[0][1])
            sender = parseaddr(message.get("From", ""))[1].casefold()
            lead = by_email.get(sender)
            if not lead or lead.get("opted_out") is True:
                continue
            message_id = _decode(message.get("Message-ID"))[:250] or f"imap-uid-{uid.decode(errors='ignore')}"
            if message_id == lead.get("last_inbound_message_id"):
                continue
            subject = _decode(message.get("Subject"))
            body = _body(message)
            opted_out = _is_optout(subject, body)
            values = {
                "last_inbound_message_id": message_id,
                "next_follow_up_at": None,
                "status": "opted_out" if opted_out else "replied",
                "opted_out": bool(opted_out),
                "reply_category": "opt_out" if opted_out else "reply",
            }
            db.table("leads").update(values).eq("id", lead["id"]).execute()
            lead["last_inbound_message_id"] = message_id
            lead["opted_out"] = bool(opted_out)
            log_event(
                db, "email_inbox",
                f"{'Leiratkozás' if opted_out else 'Válasz'} észlelve; utánkövetés leállítva (lead azonosító: {lead['id']})."
            )
            processed += 1
        if uids:
            _save_checkpoint(db, uidvalidity, int(uids[-1]))
    return processed


if __name__ == "__main__":
    print(f"Feldolgozott bejövő válaszok: {run()}")
