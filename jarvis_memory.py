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
_TOKEN_RE = re.compile(r"[\wáéíóöőúüű-]{3,}", re.UNICODE)
_STOPWORDS = {
    "hogy", "azt", "egy", "ami", "amit", "arra", "erre", "régi", "ezt",
    "az", "a", "és", "vagy", "mert", "már", "volt", "lesz", "legyen",
}


def _tokens(value: str) -> set[str]:
    return {token for token in _TOKEN_RE.findall((value or "").casefold()) if token not in _STOPWORDS}


def _matches_query(content: str, query_terms: set[str]) -> bool:
    """Match a specific phrase even when Hungarian suffixes differ slightly."""
    content_terms = _tokens(content)
    if not query_terms or not content_terms:
        return False
    matched = 0
    for term in query_terms:
        if any(
            candidate == term
            or (len(term) >= 5 and candidate.startswith(term[:5]))
            or (len(candidate) >= 5 and term.startswith(candidate[:5]))
            for candidate in content_terms
        ):
            matched += 1
    # Require every meaningful term for deletion; never broaden a partial match.
    return matched == len(query_terms)


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
            action = "save" if category == "business_preference" else "save:" + category
            return (action, payload) if payload else ("none", "")
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
    terms = _tokens(question)
    if not terms:
        return rows[:20]
    scored = []
    for row in rows:
        content = str(row.get("content") or "")
        content_terms = _tokens(content)
        matched = {
            term for term in terms
            if any(candidate == term or (len(term) >= 5 and candidate.startswith(term[:5]))
                   or (len(candidate) >= 5 and term.startswith(candidate[:5]))
                   for candidate in content_terms)
        }
        if matched:
            relevance = len(matched) / max(1, len(terms | content_terms) ** 0.5)
            scored.append((relevance, len(matched), row))
    scored.sort(key=lambda item: (item[0], item[1], str(item[2].get("created_at") or "")), reverse=True)
    return [row for _, _, row in scored[:20]]


def forget_memories(db: Any, phrase: str) -> int:
    """Deactivate exact or fully matching meaningful phrase terms; empty means all."""
    query = db.table("jarvis_memory").update({"active": False}).eq("active", True)
    if phrase.strip():
        terms = _tokens(phrase)
        if not terms:
            return 0
        rows = get_memories(db, phrase, limit=100)
        ids = [row["id"] for row in rows if row.get("id") is not None
               and _matches_query(str(row.get("content") or ""), terms)]
        # Use individual id updates for broad PostgREST compatibility.
        for memory_id in ids:
            db.table("jarvis_memory").update({"active": False}).eq("id", memory_id).execute()
        return len(ids)
    result = query.execute()
    return len(result.data or [])
