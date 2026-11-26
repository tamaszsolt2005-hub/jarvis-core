"""Read-only planner for selecting stale, eligible company dossiers for refresh."""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any
from urllib.parse import urlparse

from company_dossier import is_company_dossier_stale
from company_research_policy import company_research_refresh_decision

_OUTREACH_STATUSES = {
    "contacted", "sent", "follow_up_sent", "followed_up", "followup_sent",
    "replied", "responded", "meeting_booked", "qualified", "no_response", "follow_up_due", "followup_due",
}


def _domain(lead: dict[str, Any]) -> str:
    explicit = str(lead.get("company_domain") or "").strip().casefold()
    website = str(lead.get("website") or "").strip()
    if explicit:
        host = explicit.removeprefix("www.")
    else:
        try:
            parsed = urlparse(website)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                return ""
            host = parsed.hostname.casefold().removeprefix("www.")
        except ValueError:
            return ""
    if (
        len(host) > 253
        or not re.fullmatch(r"[a-z0-9.-]+", host)
        or host.startswith(".")
        or host.endswith(".")
        or ".." in host
        or host in {"localhost", "localhost.localdomain"}
        or host.endswith(".local")
    ):
        return ""
    return host


def _dossier_value(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    if "dossier" in value:
        nested = value.get("dossier")
        return nested if isinstance(nested, dict) else {}
    return value


def _is_uncontacted(lead: dict[str, Any]) -> bool:
    status = str(lead.get("status") or "").strip().casefold()
    if status in _OUTREACH_STATUSES or lead.get("reply_category") or lead.get("last_inbound_message_id"):
        return False
    if any(lead.get(field) for field in (
        "first_contacted_at", "last_outbound_at", "last_contacted_at",
        "last_outbound_message_id",
    )):
        return False
    try:
        count = int(lead.get("follow_up_count") or 0)
    except (TypeError, ValueError, OverflowError):
        count = 0
    return count <= 0


def _age_seconds(dossier: dict[str, Any], now: datetime) -> float:
    raw = dossier.get("researched_at")
    if not isinstance(raw, str) or not raw.strip():
        return float("inf")
    try:
        researched_at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if researched_at.tzinfo is None:
            return float("inf")
        age = (now - researched_at.astimezone(timezone.utc)).total_seconds()
    except (TypeError, ValueError, OverflowError):
        return float("inf")
    return age if age >= 0 else float("inf")


def plan_company_research_refresh_candidates(
    leads: list[dict[str, Any]],
    latest_dossiers: dict[str, Any],
    *,
    now: datetime | None = None,
    max_age_days: int = 30,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return stale, eligible leads in priority order; no DB access or outreach.

    latest_dossiers maps lead UUIDs to a dossier or a snapshot row containing
    a dossier object. Missing or invalid snapshots are treated as stale.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a positive integer")
    if isinstance(max_age_days, bool) or not isinstance(max_age_days, int) or max_age_days < 0:
        raise ValueError("max_age_days must be a non-negative integer")
    reference_time = now or datetime.now(timezone.utc)
    if reference_time.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    reference_time = reference_time.astimezone(timezone.utc)

    candidates: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    seen_leads: set[str] = set()
    for lead in leads:
        if not isinstance(lead, dict):
            continue
        lead_id = str(lead.get("id") or lead.get("lead_id") or "").strip()
        if not lead_id or lead_id in seen_leads:
            continue
        domain = _domain(lead)
        if not domain:
            continue
        seen_leads.add(lead_id)

        decision = company_research_refresh_decision(lead)
        if not decision["eligible"]:
            continue
        dossier = _dossier_value(latest_dossiers.get(lead_id))
        if not is_company_dossier_stale(dossier, max_age_days=max_age_days, now=reference_time):
            continue

        uncontacted = _is_uncontacted(lead)
        age = _age_seconds(dossier, reference_time)
        reason = "missing_dossier" if not dossier else "dossier_stale"
        candidate = {
            "lead_id": lead_id,
            "company_name": str(lead.get("company_name") or "").strip(),
            "company_domain": domain,
            "priority": "uncontacted" if uncontacted else "existing_relationship",
            "reason": reason,
            "follow_up_count": decision["follow_up_count"],
            "researched_at": dossier.get("researched_at"),
        }
        sort_key = (0 if uncontacted else 1, -age, candidate["company_name"].casefold(), lead_id)
        candidates.append((sort_key, candidate))

    candidates.sort(key=lambda item: item[0])
    return [candidate for _, candidate in candidates[:limit]]
