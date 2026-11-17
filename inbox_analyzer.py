"""Compatibility wrapper for classifying incoming business replies."""
from __future__ import annotations

from google import genai

from jarvis_common import get_model_name


def analyze_incoming_reply(reply_text: str, gemini_api_key: str) -> str:
    """Classify a reply using the supported google-genai SDK."""
    if not reply_text:
        return "later"

    prompt = (
        "Elemezd az alábbi B2B partneri válaszlevelet, és válassz pontosan egy kategóriát: "
        "[INTERESTED], [LATER] vagy [REJECTED]. "
        "INTERESTED: árajánlatot, találkozót kér vagy érdeklődik. "
        "LATER: később keressük. REJECTED: nem kéri.\n\n"
        f"Levél szövege:\n{reply_text[:5000]}"
    )
    try:
        client = genai.Client(api_key=gemini_api_key)
        response = client.models.generate_content(
            model=get_model_name(),
            contents=prompt,
        )
        result = (getattr(response, "text", None) or "").strip().upper()
        if "INTERESTED" in result:
            return "interested"
        if "LATER" in result:
            return "later"
        return "rejected"
    except Exception:
        return "later"
