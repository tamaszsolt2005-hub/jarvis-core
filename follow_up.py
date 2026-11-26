"""Consent-checked, single-attempt follow-up delivery."""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone

from email_utils import EMAIL_DELIVERY_ENABLED, EmailDeliveryOutcomeUnknown, send_email
from email_sender import email_idempotency_key
from jarvis_common import (
    audit_event, env_bool, env_int, generate_text, get_secret, get_service_supabase,
    log_event,
)
from jarvis_errors import report_error

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _has_timestamped_consent(lead: dict, now: datetime | None = None) -> bool:
    if lead.get("consent_basis") != "consent" or lead.get("approved_to_contact") is not True:
        return False
    try:
        confirmed_at = datetime.fromisoformat(
            str(lead.get("consent_confirmed_at")).replace("Z", "+00:00")
        )
        return (
            confirmed_at.tzinfo is not None
            and confirmed_at.utcoffset() is not None
            and (now is None or confirmed_at <= now)
        )
    except (TypeError, ValueError):
        return False


def _eligible_for_follow_up(lead: dict, now: datetime) -> bool:
    """Require explicit, timestamped consent and a due, unreplied, one-shot lead."""
    if (
        lead.get("status") != "sent"
        or not _has_timestamped_consent(lead, now)
        or lead.get("opted_out") is not False
        or lead.get("reply_category")
        or lead.get("last_inbound_message_id")
        or not EMAIL_RE.fullmatch(str(lead.get("email") or ""))
    ):
        return False
    try:
        due_at = datetime.fromisoformat(
            str(lead.get("next_follow_up_at")).replace("Z", "+00:00")
        )
        count = int(lead.get("follow_up_count") or 0)
        return (
            due_at.tzinfo is not None
            and due_at.utcoffset() is not None
            and 0 <= count < 1
            and due_at <= now
        )
    except (TypeError, ValueError):
        return False


def _run() -> None:
    if not EMAIL_DELIVERY_ENABLED or not env_bool("AUTO_SEND_ENABLED", False):
        print("Biztonsági mód: AUTO_SEND_ENABLED nem true, follow-up nem kerül kiküldésre.")
        return

    db = get_service_supabase()
    now = datetime.now(timezone.utc)
    rows = db.table("leads").select("*").eq("status", "sent").limit(100).execute().data or []
    due = [lead for lead in rows if _eligible_for_follow_up(lead, now)]

    for lead in due[:env_int("FOLLOW_UP_MAX_PER_RUN", 3, 1, 10)]:
        lead_id = lead["id"]
        claimed = False
        send_attempted = False
        audit_fields = None
        try:
            body = generate_text(
                "Írj rövid, udvarias, nem sürgető magyar utánkövető e-mailt. "
                "Ne találj ki tényt; legyen benne leiratkozási lehetőség. Cég: "
                + str(lead.get("company_name"))
            )[:4500]

            claim = (
                db.table("leads")
                .update({"status": "followup_sending"})
                .eq("id", lead_id)
                .eq("status", "sent")
                .eq("consent_basis", "consent")
                .eq("approved_to_contact", True)
                .eq("opted_out", False)
                .eq("follow_up_count", 0)
                .eq("next_follow_up_at", lead.get("next_follow_up_at"))
                .select("id")
                .execute()
            )
            if not claim.data:
                continue
            claimed = True

            fresh_rows = (
                db.table("leads")
                .select(
                    "id,status,email,consent_basis,consent_confirmed_at,"
                    "approved_to_contact,opted_out,reply_category,last_inbound_message_id,"
                    "next_follow_up_at,follow_up_count"
                )
                .eq("id", lead_id)
                .limit(1)
                .execute()
                .data or []
            )
            if (
                not fresh_rows
                or fresh_rows[0].get("status") != "followup_sending"
                or not _eligible_for_follow_up(
                    {**fresh_rows[0], "status": "sent"}, now
                )
                or fresh_rows[0].get("opted_out") is not False
                or fresh_rows[0].get("reply_category")
                or fresh_rows[0].get("last_inbound_message_id")
                or fresh_rows[0].get("email") != lead.get("email")
            ):
                db.table("leads").update({
                    "status": "followup_blocked",
                    "next_follow_up_at": None,
                }).eq("id", lead_id).eq("status", "followup_sending").execute()
                continue

            subject = "Rövid visszajelzéskérés"
            audit_fields = {
                "module": "follow_up",
                "action": "send_follow_up_email",
                "operation_id": email_idempotency_key(lead, follow_up=True),
                "recipient": str(lead["email"]),
                "subject": subject,
                "approved": True,
            }
            if not audit_event(db, status="pending", **audit_fields):
                raise RuntimeError("Follow-up leállítva: a pending auditbejegyzés nem menthető.")

            # Keep the same stable operation ID at the provider boundary. Only an
            # ambiguous provider result is marked unknown; a known rejection is safe
            # to retry later after the failure has been corrected.
            try:
                message_id = send_email(
                    str(lead["email"]), subject, body, audit_fields["operation_id"]
                )
            except EmailDeliveryOutcomeUnknown:
                send_attempted = True
                raise
            send_attempted = True

            updated = (
                db.table("leads")
                .update({
                    "status": "followed_up",
                    "follow_up_count": 1,
                    "followed_up_at": now.isoformat(),
                    "next_follow_up_at": None,
                })
                .eq("id", lead_id)
                .eq("status", "followup_sending")
                .select("id")
                .execute()
            )
            if not updated.data:
                raise RuntimeError(
                    "A küldési kísérlet után a lead állapota nem frissíthető; "
                    "a duplikált küldés elkerülése érdekében ellenőrzést igényel."
                )
            if not audit_event(
                db,
                status="success",
                delivery_id=message_id or None,
                result={"provider_accepted": True},
                **audit_fields,
            ):
                raise RuntimeError(
                    "A szolgáltató átvette a levelet, de a sikeres auditbejegyzés nem menthető."
                )

            log_event(db, "follow_up", f"Follow-up elküldve: {lead.get('company_name')}")
            time.sleep(env_int("SEND_DELAY_SECONDS", 30, 10, 600))
        except Exception as exc:
            if audit_fields is not None:
                audit_event(
                    db,
                    status="unknown" if send_attempted else "failed",
                    error=exc,
                    level="error",
                    result={"delivery_attempted": send_attempted},
                    **audit_fields,
                )
            report_error(
                exc,
                module="follow_up",
                operation="send_follow_up",
                severity="error",
                db=db,
            )
            if claimed:
                try:
                    recovery = (
                        {"status": "followup_unknown", "next_follow_up_at": None}
                        if send_attempted
                        else {"status": "sent"}
                    )
                    db.table("leads").update(recovery).eq("id", lead_id).eq(
                        "status", "followup_sending"
                    ).execute()
                except Exception as recovery_exc:
                    report_error(
                        recovery_exc,
                        module="follow_up",
                        operation="restore_lead_after_follow_up_failure",
                        severity="critical",
                        db=db,
                    )


def run() -> None:
    """Run follow-ups and centrally report failures outside per-lead handling."""
    try:
        _run()
    except Exception as exc:
        report_error(
            exc,
            module="follow_up",
            operation="run_follow_up_batch",
            severity="critical",
        )
        raise


if __name__ == "__main__":
    run()
