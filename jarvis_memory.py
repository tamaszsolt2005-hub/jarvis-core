"""JARVIS long-term, user-directed business memory.

Only explicit remember/forget commands can change memory. Records are scoped to
business preferences, decisions and operating instructions; secrets and sensitive
personal data are rejected. Reads are bounded and best-effort.
"""
from __future__ import annotations

import re
from typing import Any

SAVE_PREFIXES = (
    "jegyezd meg", "emlékezz arra", "emlékezz rá", "mentsd el emlékként",
    "tartsd észben", "rögzítsd a tanulságot", "jegyezd meg a döntést",
    "mentsd el a tapasztalatot",
)
LIST_TERMS = ("mutasd a memóri", "mit jegyeztél meg", "mire emlékszel", "memória áttekint")
FORGET_PREFIXES = ("felejtsd el", "töröld a memóriából", "töröld az emléket", "felejts el mindent")

_SENSITIVE = re.compile(
    r"(?i)(api[_ -]?key|service[_ -]?role|password|jelszó|token|secret|"
    r"@|\b\+?\d[\d ()-]{7,}\b|bankszámla|bankkártya|egészségügyi|"
    r"diagnózis|gyógyszer|politikai nézet|vallás)"
)


def memory_command(message: str) -> tuple[str, str]:
    """Return (save|list|forget|none, payload)."""
    text = (message or "").strip()
    q = text.casefold()
    if any(term in q for term in LIST_TERMS):
        return "list", ""
    for prefix in FORGET_PREFIXES:
        if q.startswith(prefix):
            payload = text[len(prefix):].strip(" :,-")
            if not payload or payload.casefold() in {"mindent", "az összes emléket", "minden emléket", "az összeset"}:
                return "forget", ""
            return "forget", payload
    for prefix in sorted(SAVE_PREFIXES, key=len, reverse=True):
        if q.startswith(prefix):
            payload = text[len(prefix):].lstrip(" :,-")
            for leading in ("a döntést", "a tanulságot", "a tapasztalatot", "hogy ", "azt, hogy ", "azt "):
                if payload.casefold().startswith(leading):
                    payload = payload[len(leading):].lstrip(" :,-")
                    break
            category = "lesson" if prefix == "rögzítsd a tanulságot" else (
                "decision" if prefix == "jegyezd meg a döntést" else (
                    "outcome" if prefix == "mentsd el a tapasztalatot" else "business_preference"
                )
            )
            return ("save:" + category, payload) if payload else ("none", "")
    return "none", ""


def _valid_memory(content: str) -> bool:
    return bool(content and len(content) <= 700 and not _SENSITIVE.search(content))


def save_memory(db: Any, content: str, category: str = "business_preference") -> bool:
    if not _valid_memory(content):
        return False
    if category not in {"business_preference", "decision", "outcome", "lesson"}:
        category = "business_preference"
    db.table("jarvis_memory").insert({
        "category": category,
        "content": content.strip(),
        "source": "explicit_user_instruction",
        "active": True,
    }).execute()
    return True


def get_memories(db: Any, question: str = "", limit: int = 100) -> list[dict]:
    rows = db.table("jarvis_memory").select("id,category,content,created_at").eq(
        "active", True
    ).order("created_at", desc=True).limit(min(max(limit, 1), 100)).execute().data or []
    terms = {x for x in re.findall(r"[\wáéíóöőúüű-]{3,}", (question or "").casefold())}
    if not terms:
        return rows[:20]
    scored = []
    for row in rows:
        content = str(row.get("content") or "")
        content_terms = set(re.findall(r"[\wáéíóöőúüű-]{3,}", content.casefold()))
        overlap = len(terms & content_terms)
        if overlap:
            relevance = overlap / max(1, len(terms | content_terms) ** 0.5)
            scored.append((relevance, overlap, row))
    scored.sort(key=lambda item: (item[0], item[1], str(item[2].get("created_at") or "")), reverse=True)
    return [row for _, _, row in scored[:20]]


def forget_memories(db: Any, phrase: str) -> int:
    """Deactivate matching records; an empty phrase means all active memories."""
    query = db.table("jarvis_memory").update({"active": False}).eq("active", True)
    if phrase.strip():
        rows = get_memories(db, phrase, limit=100)
        ids = [row["id"] for row in rows if phrase.casefold() in str(row.get("content", "")).casefold()]
        if not ids:
            return 0
        # Use individual id updates for broad PostgREST compatibility.
        for memory_id in ids:
            db.table("jarvis_memory").update({"active": False}).eq("id", memory_id).execute()
        return len(ids)
    result = query.execute()
    return len(result.data or [])
