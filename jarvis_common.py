"""Shared configuration, Supabase, Gemini and logging helpers."""
from __future__ import annotations

import os
from typing import Any

from google import genai
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
    return get_secret("GEMINI_MODEL", "gemini-2.5-flash") or "gemini-2.5-flash"


def generate_text(prompt: str, client: genai.Client | None = None) -> str:
    client = client or get_gemini_client()
    response = client.models.generate_content(model=get_model_name(), contents=prompt)
    return (getattr(response, "text", None) or "").strip()


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
