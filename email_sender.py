"""Send consent-checked first-contact and bounded follow-up emails."""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from email_utils import EMAIL_DELIVERY_ENABLED, send_email
from jarvis_common import env_bool, env_int, generate_text, get_secret, get_service_supabase, log_event, audit_event
from jarvis_errors import report_error
from lead_scoring import score_lead
from web_auditor import audit_company_website

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
FOLLOW_UP_STATUSES = {"sent", "follow_up_sent"}


def _valid_consent(lead: dict) -> bool:
    if (
        lead.get("consent_basis") != "consent"
        or lead.get("approved_to_contact") is not True
        or lead.get("opted_out") is not False
    ):
        return False
    try:
        confirmed_at = datetime.fromisoformat(
            str(lead.get("consent_confirmed_at")).replace("Z", "+00:00")
        )
        return (
            confirmed_at.tzinfo is not None
            and confirmed_at.utcoffset() is not None
            and confirmed_at <= datetime.now(timezone.utc)
        )
    except (TypeError, ValueError):
        return False


def _draft(lead: dict, follow_up: bool = False) -> tuple[str, str]:
    if follow_up:
        prompt = (
            "Írj rövid, udvarias, nem sürgető magyar B2B utánkövető e-mailt. "
            "Ne állítsd, hogy az ügyfél érdeklődött vagy válaszolt. Ne találj ki tényeket. "
            "Egyetlen könnyű következő lépést ajánlj fel. Tartalmazzon egyszerű leiratkozási lehetőséget.\n"
            f"Cég: {lead.get('company_name')}\nElső levél dátuma: {lead.get('first_sent_at')}\n"
            f"Korábbi utánkövetések: {lead.get('follow_up_count', 0)}\n"
            f"Ajánlatunk: {get_secret('OFFER_DESCRIPTION', 'üzleti automatizációs megoldás')}"
        )
    else:
        audit = audit_company_website(lead.get("website"))
        prompt = (
            "Írj rövid, tényszerű, magyar B2B bemutatkozó e-mailt. Ne találj ki tényeket. "
            "Legyen udvarias, átlátható, és tartalmazzon egyszerű leiratkozási lehetőséget. "
            f"Cég: {lead.get('company_name')}\nWeboldal audit: {audit}\n"
            f"Ajánlatunk: {get_secret('OFFER_DESCRIPTION', 'üzleti automatizációs megoldás')}"
        )
    generated = generate_text(prompt)
    lines = [line.strip() for line in generated.splitlines() if line.strip()]
    subject = lines[0].removeprefix("Tárgy:").strip()[:180] if lines else (
        "Rövid szakmai utánkövetés" if follow_up else "Rövid szakmai bemutatkozás"
    )
    body = "\n".join(lines[1:])[:5000] if len(lines) > 1 else generated[:5000]
    body = body.rstrip() + (
        "\n\nHa nem szeretne több megkeresést kapni, válaszoljon erre az e-mailre a LEIRATKOZOM szóval."
    )
    return subject, body


def _due_follow_up(lead: dict, now: datetime) -> bool:
    if (
        lead.get("status") not in FOLLOW_UP_STATUSES
        or lead.get("opted_out") is not False
        or lead.get("reply_category")
        or lead.get("last_inbound_message_id")
    ):
        return False
    try:
        due = datetime.fromisoformat(str(lead.get("next_follow_up_at")).replace("Z", "+00:00"))
        count = int(lead.get("follow_up_count") or 0)
        maximum = env_int("MAX_FOLLOW_UPS", 2, 0, 5)
        return (
            due.tzinfo is not None
            and due.utcoffset() is not None
            and due <= now
            and 0 <= count < maximum
        )
    except (TypeError, ValueError):
        return False


def _send_one(db, lead: dict, follow_up: bool, now: datetime) -> bool:
    current_status = str(lead.get("status") or "")
    allowed_statuses = FOLLOW_UP_STATUSES if follow_up else {"new"}
    if (
        current_status not in allowed_statuses
        or not _valid_consent(lead)
        or not EMAIL_RE.fullmatch(str(lead.get("email") or ""))
        or lead.get("reply_category")
        or lead.get("last_inbound_message_id")
    ):
        return False
    claim_status = "follow_up_sending" if follow_up else "sending"
    claim = (
        db.table("leads").update({"status": claim_status})
        .eq("id", lead["id"]).eq("status", current_status)
        .eq("opted_out", False).eq("approved_to_contact", True)
        .eq("consent_basis", "consent").select("id").execute()
    )
    if not claim.data:
        audit_event(
            db, module="email_sender", action="send_claim", status="blocked",
            result={"reason": "lead_claim_not_acquired"},
        )
        return False
    smtp_attempted = False
    try:
        subject, body = _draft(lead, follow_up=follow_up)
        # Recheck consent, opt-out and inbound replies immediately before SMTP delivery.
        fresh = (
            db.table("leads")
            .select("id,status,email,consent_basis,consent_confirmed_at,approved_to_contact,opted_out,reply_category,last_inbound_message_id")
            .eq("id", lead["id"]).limit(1).execute().data or []
        )
        if (
            not fresh or fresh[0].get("status") != claim_status
            or not _valid_consent(fresh[0])
            or fresh[0].get("reply_category")
            or fresh[0].get("last_inbound_message_id")
            or fresh[0].get("email") != lead.get("email")
        ):
            if fresh and fresh[0].get("status") == claim_status:
                db.table("leads").update({
                    "status": "send_blocked", "next_follow_up_at": None
                }).eq("id", lead["id"]).eq("status", claim_status).execute()
            log_event(db, "email_sender", f"Küldés megszakítva: a hozzájárulás vagy a válaszállapot megváltozott ({lead.get('company_name')}).", "warning")
            return False
        operation_id = str(uuid4())
        audit_fields = {
            "module": "email_sender",
            "action": "send_follow_up_email" if follow_up else "send_first_contact_email",
            "operation_id": operation_id,
            "recipient": str(lead["email"]),
            "subject": subject,
            "approved": True,
        }
        if not audit_event(db, status="pending", **audit_fields):
            raise RuntimeError("E-mailküldés leállítva: az auditnapló nem írható.")
        # The remote server may accept the message even if its final SMTP response is lost.
        # From this point onward the outcome is uncertain and automatic retry is forbidden.
        smtp_attempted = True
        message_id = send_email(str(lead["email"]), subject, body)
        if follow_up:
            count = int(lead.get("follow_up_count") or 0) + 1
            max_count = env_int("MAX_FOLLOW_UPS", 2, 0, 5)
            next_at = (
                now + timedelta(days=env_int("FOLLOW_UP_DAYS", 5, 2, 30))
            ).isoformat() if count < max_count else None
            values = {
                "status": "follow_up_sent", "follow_up_count": count,
                "followed_up_at": now.isoformat(), "next_follow_up_at": next_at,
                "last_message_id": message_id,
            }
            label = "Utánkövető levél elküldve"
        else:
            values = {
                "status": "sent", "first_sent_at": now.isoformat(),
                "next_follow_up_at": (
                    now + timedelta(days=env_int("FOLLOW_UP_DAYS", 5, 2, 30))
                ).isoformat(),
                "last_message_id": message_id,
            }
            label = "Első levél elküldve"
        db.table("leads").update(values).eq("id", lead["id"]).eq("status", claim_status).execute()
        if not audit_event(
            db, status="success", delivery_id=message_id or None,
            result={"smtp_accepted": True, "follow_up": follow_up},
            **audit_fields,
        ):
            raise RuntimeError("Az SMTP átvette a levelet, de a sikeres auditbejegyzés nem menthető.")
        log_event(db, "email_sender", f"{label}: {lead.get('company_name')}")
        return True
    except Exception as exc:
        if "audit_fields" in locals():
            audit_event(
                db, status="unknown" if smtp_attempted else "failed",
                error=exc, level="error",
                result={"smtp_attempted": smtp_attempted},
                **audit_fields,
            )
        report_error(
            exc, module="email_sender", operation="send_one", severity="error", db=db
        )
        try:
            db.table("leads").update({"status": "send_unknown" if smtp_attempted else "send_error", "next_follow_up_at": None if smtp_attempted else lead.get("next_follow_up_at")}).eq("id", lead["id"]).eq("status", claim_status).execute()
        except Exception as state_exc:
            report_error(
                state_exc, module="email_sender", operation="mark_send_unknown" if smtp_attempted else "mark_send_error",
                severity="critical", db=db,
            )
        return False


def _run() -> None:
    if (
        not EMAIL_DELIVERY_ENABLED
        or not env_bool("AUTO_SEND_ENABLED", False)
        or not env_bool("EMAIL_INBOX_MONITOR_ENABLED", False)
    ):
        print("Biztonsági mód: az SMTP-küldés, az automatikus küldés és a bejövő levélfigyelés mind szükséges; az e-mail nem kerül kiküldésre.")
        return
    db = get_service_supabase()
    now = datetime.now(timezone.utc)
    rows = db.table("leads").select("*").limit(1000).execute().data or []
    eligible = [
        row for row in rows
        if _valid_consent(row) and EMAIL_RE.fullmatch(str(row.get("email") or ""))
        and row.get("opted_out") is not True
        and (
            row.get("status") == "new"
            or _due_follow_up(row, now)
        )
    ]
    eligible.sort(key=lambda row: (row.get("status") != "new", -score_lead(row)))
    sent = 0
    for lead in eligible:
        if sent >= env_int("SEND_MAX_PER_RUN", 3, 1, 10):
            break
        is_follow_up = lead.get("status") in FOLLOW_UP_STATUSES
        if _send_one(db, lead, is_follow_up, now):
            sent += 1
            time.sleep(env_int("SEND_DELAY_SECONDS", 30, 10, 600))


def run() -> None:
    """Run the background sender, report unexpected failures, and fail the workflow."""
    try:
        _run()
    except Exception as exc:
        report_error(
            exc, module="email_sender", operation="run_sender", severity="critical"
        )
        raise


if __name__ == "__main__":
    run()
