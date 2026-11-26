"""Atomic company identity and consent-aware contact selection."""
from __future__ import annotations

from typing import Any


def upsert_company_lead(
    db: Any,
    *,
    company_name: str,
    website: str | None = None,
    email: str | None = None,
    notes: str | None = None,
    source: str | None = None,
    consent_basis: str | None = None,
    approved_to_contact: bool = False,
    consent_confirmed_at: str | None = None,
) -> dict[str, Any]:
    """Claim one company identity and optionally register a consented contact.

    The database RPC serializes name/domain aliases and chooses the highest
    priority eligible contact. The caller must never write directly to leads.
    """
    response = db.rpc(
        "upsert_company_lead",
        {
            "p_company_name": company_name,
            "p_website": website,
            "p_email": email,
            "p_notes": notes,
            "p_source": source,
            "p_consent_basis": consent_basis,
            "p_approved_to_contact": approved_to_contact,
            "p_consent_confirmed_at": consent_confirmed_at,
        },
    ).execute()
    rows = getattr(response, "data", None) or []
    if not rows or not isinstance(rows[0], dict):
        raise RuntimeError("A lead company RPC nem igazolta vissza a mentést.")
    lead_id = rows[0].get("lead_id")
    outcome = rows[0].get("outcome")
    if not lead_id or outcome not in {"created", "existing"}:
        raise RuntimeError("A lead company RPC hibás vagy hiányos választ adott.")
    return {
        "lead_id": str(lead_id),
        "outcome": outcome,
        "selected_email": rows[0].get("selected_email"),
    }
