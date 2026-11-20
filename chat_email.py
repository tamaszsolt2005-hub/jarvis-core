"""Explicit chat-originated email drafts requiring a separate approval."""
from __future__ import annotations

import re
from typing import Callable

EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w.-])", re.I)
EMAIL_INTENT = re.compile(r"(?:e-?mail\w*|lev[eé]l\w*)", re.I)
SEND_INTENT = re.compile(r"(?:küld\w*|kuld\w*|ír\w*|ir\w*|fogalmaz\w*)", re.I)


def is_chat_email_request(text: str) -> bool:
    value = str(text or "")
    return bool(EMAIL_INTENT.search(value) and SEND_INTENT.search(value))


def extract_explicit_recipient(text: str) -> str | None:
    match = EMAIL_RE.search(str(text or ""))
    return match.group(0).lower() if match else None


def build_chat_email_draft(request: str, generate: Callable[..., str]) -> tuple[str, str]:
    prompt = (
        "Készíts egyetlen magyar nyelvű, udvarias e-mail-tervezetet a felhasználó kéréséhez. "
        "Ne küldd el, ne találj ki címzettet, személyes adatot, tényt vagy ígéretet. "
        "Ha hiányzik információ, fogalmazz általánosan, ne találj ki adatot. "
        "A kimenet pontos formátuma: első sor 'Tárgy: ...', utána üres sor, majd a teljes levélszöveg. "
        "Ne adj magyarázatot vagy alternatívákat.\n\n"
        f"Felhasználó kérése: {str(request)[:3000]}"
    )
    result = str(generate(prompt, max_output_tokens=1200) or "").strip()
    lines = result.splitlines()
    subject = " ".join(lines[0].split(":", 1)[1:]).strip() if lines and lines[0].casefold().startswith("tárgy:") else ""
    if not subject:
        subject = " ".join(lines[0:2]).strip()[:180] or "E-mail"
        body_lines = lines[2:] if len(lines) > 2 else lines[1:]
    else:
        body_lines = lines[1:]
    body = "\n".join(body_lines).strip()[:8000]
    if not body:
        raise ValueError("A generált e-mail-tervezet üres; nem készítettem elő küldést.")
    return subject[:180], body
