"""Transparent, rule-based lead scoring from 1 to 100."""
from __future__ import annotations

from urllib.parse import urlparse

FREE_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "outlook.com",
    "hotmail.com", "live.com", "freemail.hu", "citromail.hu",
}


def score_lead(lead: dict) -> int:
    score = 35
    email = str(lead.get("email") or "").strip().lower()
    website = str(lead.get("website") or "").strip()
    company_name = str(lead.get("company_name") or "").strip()
    notes = str(lead.get("notes") or "").strip()

    if "@" in email:
        domain = email.rsplit("@", 1)[-1]
        score += 20 if domain not in FREE_EMAIL_DOMAINS else 5
    try:
        host = urlparse(website).hostname
        if host and "." in host:
            score += 20
    except ValueError:
        pass
    if len(company_name) >= 3:
        score += 10
    if len(notes) >= 40:
        score += 10
    if lead.get("source"):
        score += 5
    return max(1, min(score, 100))
