"""Eligibility policy for scheduled company dossier refreshes."""
from __future__ import annotations

from typing import Any


DEFAULT_MAX_UNANSWERED_FOLLOWUPS = 2

_EXPLICIT_REJECTION_CATEGORIES = {
    "rejected",
    "not_interested",
    "negative",
    "opt_out",
    "unsubscribe",
    "do_not_contact",
}
_EXPLICIT_REJECTION_STATUSES = {
    "rejected",
    "not_interested",
    "opted_out",
    "do_not_contact",
    "closed_lost",
}
_OUTREACH_STATUSES = {
    "sent",
    "follow_up_sent",
    "followed_up",
    "followup_sent",
    "contacted",
    "no_response",
    "follow_up_due",
    "followup_due",
}


def company_research_refresh_decision(
    lead: dict[str, Any],
    *,
    max_unanswered_followups: int = DEFAULT_MAX_UNANSWERED_FOLLOWUPS,
) -> dict[str, Any]:
    """Return a fail-safe refresh decision without changing lead or contact state.

    Explicit rejection/opt-out suppresses refresh immediately. A company with no
    inbound reply is paused after the configured number of *sent* follow-ups.
    Uncontacted companies remain eligible. Any inbound reply not classified as
    an explicit rejection is kept eligible for human review, not mislabeled as
    silence or disinterest.
    """
    if (
        isinstance(max_unanswered_followups, bool)
        or not isinstance(max_unanswered_followups, int)
        or max_unanswered_followups < 1
    ):
        raise ValueError("max_unanswered_followups must be a positive integer")

    status = str(lead.get("status") or "").strip().casefold()
    reply_category = str(lead.get("reply_category") or "").strip().casefold()
    if lead.get("opted_out") is True or status in _EXPLICIT_REJECTION_STATUSES or reply_category in _EXPLICIT_REJECTION_CATEGORIES:
        return {
            "eligible": False,
            "reason": "explicit_rejection_or_opt_out",
            "follow_up_count": _safe_follow_up_count(lead.get("follow_up_count")),
        }

    follow_up_count = _safe_follow_up_count(lead.get("follow_up_count"))
    has_inbound_reply = bool(lead.get("last_inbound_message_id")) or bool(reply_category)
    if (
        status in _OUTREACH_STATUSES
        and not has_inbound_reply
        and follow_up_count >= max_unanswered_followups
    ):
        return {
            "eligible": False,
            "reason": "unanswered_follow_up_limit_reached",
            "follow_up_count": follow_up_count,
        }

    return {
        "eligible": True,
        "reason": "eligible_for_research_refresh",
        "follow_up_count": follow_up_count,
    }


def _safe_follow_up_count(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        count = int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0
    return max(0, count)
