"""Shared configuration, Supabase, Gemini and logging helpers."""
from __future__ import annotations

import os
import time
from typing import Any

from google import genai
from google.genai import types
from supabase import Client, create_client


def get_secret(name: str, default: str | None = None) -> str | None:
    """Read Streamlit secrets first, then environment variables."""
    try:
        import streamlit as st
        value = st.secrets.get(name)
        if value not in (None, ""):
            return str(value)
    except Exception:
        pass
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def required_secret(name: str) -> str:
    value = get_secret(name)
    if not value:
        raise RuntimeError(
            f"Hiányzó beállítás: {name}. Add hozzá GitHub Actions Secretként "
            "vagy a Codespace Streamlit secrets konfigurációjához."
        )
    return value


def env_bool(name: str, default: bool = False) -> bool:
    value = get_secret(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}


def env_int(name: str, default: int, minimum: int = 0, maximum: int = 100000) -> int:
    raw = get_secret(name)
    try:
        value = int(raw) if raw is not None else default
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def get_supabase() -> Client:
    """Use the server-side service role key; never expose it in client-side code."""
    url = required_secret("SUPABASE_URL")
    key = get_secret("SUPABASE_SERVICE_ROLE_KEY") or required_secret("SUPABASE_KEY")
    return create_client(url, key)


def get_gemini_client() -> genai.Client:
    return genai.Client(api_key=required_secret("GEMINI_API_KEY"))


def get_model_name() -> str:
    configured = (get_secret("GEMINI_MODEL", "gemini-3.5-flash") or "gemini-3.5-flash").strip()
    if configured in {"gemini-2.5-flash", "gemini-2.5-pro"}:
        return "gemini-3.5-flash"
    return configured


def format_conversation_history(messages: list[tuple[str, str]], max_chars: int = 10000, max_message_chars: int = 3000) -> str:
    """Keep the newest useful turns while enforcing strict prompt-size bounds."""
    if max_chars <= 0 or max_message_chars <= 0:
        return ""
    selected: list[str] = []
    used = 0
    for role, message in reversed(messages):
        if role not in {"user", "assistant"}:
            continue
        value = str(message or '').strip()
        if not value:
            continue
        truncation_marker = "… [üzenet rövidítve]"
        if len(value) > max_message_chars:
            keep = max(0, max_message_chars - len(truncation_marker))
            value = value[:keep].rstrip() + truncation_marker
        line = f"{role}: {value}"
        remaining = max_chars - used
        if remaining <= 0:
            break
        if len(line) > remaining:
            if not selected:
                selected.append(line[:remaining].rstrip())
            break
        selected.append(line)
        used += len(line) + 1
    return "\n".join(reversed(selected))

def generate_text(prompt: str, client: genai.Client | None = None) -> str:
    """Generate a response with bounded retries for temporary Gemini overloads.

    Retries only transient rate-limit / availability failures. Configuration,
    authentication and malformed-request errors are raised immediately.
    """
    client = client or get_gemini_client()
    model = get_model_name()
    max_attempts = env_int("GEMINI_RETRY_ATTEMPTS", 3, minimum=1, maximum=5)
    last_error: Exception | None = None

    for attempt in range(max_attempts):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.35,
                    top_p=0.9,
                    max_output_tokens=4096,
                ),
            )
            text = (getattr(response, "text", None) or "").strip()
            if not text:
                raise RuntimeError("A Gemini API üres választ adott vissza.")
            return text
        except Exception as exc:
            last_error = exc
            code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
            status = str(getattr(exc, "status", "") or "").upper()
            message = str(exc).upper()
            transient = (
                code in (429, 500, 502, 503, 504)
                or status in {"UNAVAILABLE", "RESOURCE_EXHAUSTED", "INTERNAL", "DEADLINE_EXCEEDED"}
                or any(marker in message for marker in (
                    "429", "500", "502", "503", "504", "UNAVAILABLE",
                    "RESOURCE_EXHAUSTED", "INTERNAL", "DEADLINE_EXCEEDED",
                ))
            )
            if not transient or attempt >= max_attempts - 1:
                raise
            # Short exponential backoff: 1s, 2s, 4s (bounded by 5 attempts).
            time.sleep(min(2 ** attempt, 8))

    if last_error is not None:
        raise last_error
    raise RuntimeError("A Gemini kérés nem fejeződött be.")


def log_event(supabase: Client, module: str, message: str, level: str = "info") -> None:
    try:
        supabase.table("logs").insert({
            "module": module[:80],
            "level": level[:20],
            "message": message[:4000],
        }).execute()
    except Exception as exc:
        print(f"[{module}] Naplózási hiba: {type(exc).__name__}: {exc}")


def get_setting(supabase: Client, key: str, default: Any = None) -> Any:
    try:
        result = supabase.table("settings").select("value").eq("key", key).limit(1).execute()
        if result.data:
            return result.data[0].get("value", default)
    except Exception as exc:
        print(f"Beállítás olvasási hiba ({key}): {type(exc).__name__}: {exc}")
    return default


def set_setting(supabase: Client, key: str, value: Any) -> None:
    supabase.table("settings").upsert({"key": key, "value": value}).execute()
