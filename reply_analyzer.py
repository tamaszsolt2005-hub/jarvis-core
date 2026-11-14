"""Classify replies and detect opt-out language before any follow-up."""
from __future__ import annotations

from jarvis_common import generate_text

OPT_OUT_TERMS = (
    "leiratko", "iratkoztassanak le", "iratkoztasson le", "ne keress",
    "ne írj", "ne irj", "ne küldj", "ne kuldj", "unsubscribe",
    "remove me", "stop emailing", "do not contact",
)
NEGATIVE_TERMS = ("nem érdekel", "nem erdekel", "nem kérjük", "nem kerjuk", "no thanks", "not interested")
POSITIVE_TERMS = ("érdekel", "erdekel", "árajánlat", "arajanlat", "beszéljünk", "beszeljunk", "találkozó", "talalkozo", "pricing", "schedule a call")


def fallback_classification(body: str) -> str:
    text = (body or "").casefold()
    if any(term in text for term in OPT_OUT_TERMS):
        return "opt_out"
    if any(term in text for term in NEGATIVE_TERMS):
        return "rejected"
    if any(term in text for term in POSITIVE_TERMS):
        return "interested"
    if any(term in text for term in ("később", "kesobb", "jövő hónap", "jovo honap", "later", "not now")):
        return "later"
    return "unknown"


def classify_reply(body: str) -> str:
    fallback = fallback_classification(body)
    if fallback != "unknown":
        return fallback
    prompt = (
        "Classify this business email reply. Return exactly one label: "
        "interested, later, rejected, opt_out, unknown. "
        "An unsubscribe or do-not-contact request is always opt_out.\n\n"
        f"Email:\n{(body or '')[:5000]}"
    )
    try:
        label = generate_text(prompt).strip().lower().replace(".", "")
        return label if label in {"interested", "later", "rejected", "opt_out", "unknown"} else "unknown"
    except Exception:
        return "unknown"
