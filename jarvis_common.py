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
            f"Hiányzó beállítás: {name}. Add hozzá Codespaces secretként (környezeti változóként) "
            "vagy a .streamlit/secrets.toml fájlban."
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
    default_model = "gemini-3.8-flash"
    configured = (get_secret("GEMINI_MODEL", default_model) or default_model).strip()
    if configured in {"gemini-2.5-flash", "gemini-2.5-pro"}:
        return default_model
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
        value = str(message or "").strip()
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


def estimate_response_tokens(question: str) -> int:
    """Estimate a sensible output-token budget locally, without an extra model call."""
    text = " ".join(str(question or "").casefold().split())
    if not text:
        return 512

    concise_markers = (
        "röviden", "roviden", "egy mondatban", "csak a választ",
        "tömören", "tomoren", "tl;dr",
    )
    detailed_markers = (
        "részletezd", "reszletezd", "részletesen", "reszletesen",
        "elemezd", "elemzést", "elemzest", "hasonlítsd össze", "hasonlitsd ossze",
        "lépésről lépésre", "lepesrol lepesre", "tervezz", "dolgozd ki",
        "stratégia", "strategia", "jelentés", "jelentes", "vezetői", "vezetoi",
        "audit", "értékeld", "ertekeld", "indokold meg", "mélyreható",
        "melyrehato", "pro és kontra", "pro es kontra",
    )
    multi_part_markers = (" és ", " továbbá ", "valamint", "illetve", "1.", "2.", "3.", "•", "\n-", "\n*")
    if any(marker in text for marker in concise_markers):
        return 384
    if any(marker in text for marker in detailed_markers):
        return 3072 if len(text) < 700 else 4096
    if len(text) > 900 or sum(text.count(marker) for marker in multi_part_markers) >= 3:
        return 2048
    if len(text) > 350 or any(marker in text for marker in multi_part_markers):
        return 1536
    if len(text) > 120:
        return 1024
    if len(text) < 45:
        return 512
    return 768


def generate_text(
    prompt: str,
    client: genai.Client | None = None,
    on_status: Any | None = None,
    max_output_tokens: int = 8192,
) -> str:
    """Generate with bounded retries and current fallback models for temporary overloads."""
    client = client or get_gemini_client()
    primary_model = get_model_name()
    fallback_models = ("gemini-3.8-flash", "gemini-3.5-flash-lite")
    max_attempts = env_int("GEMINI_RETRY_ATTEMPTS", 2, minimum=1, maximum=5)
    output_token_budget = max(128, min(int(max_output_tokens), 8192))

    def notify(message: str) -> None:
        if callable(on_status):
            try:
                on_status(message)
            except Exception:
                pass

    def request_model(model: str, attempts: int) -> tuple[str, Exception | None]:
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        **(
                            {"max_output_tokens": output_token_budget}
                            if model == "gemini-3.8-flash"
                            else {
                                "temperature": 0.35,
                                "top_p": 0.9,
                                "max_output_tokens": output_token_budget,
                            }
                        )
                    ),
                )
                answer = (getattr(response, "text", None) or "").strip()
                if not answer:
                    raise RuntimeError("A Gemini API üres választ adott vissza.")
                return answer, None
            except Exception as exc:
                last_error = exc
                code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
                status = str(getattr(exc, "status", "") or "").upper()
                message = str(exc).upper()
                is_overloaded = (
                    code in (429, 503)
                    or status in {"UNAVAILABLE", "RESOURCE_EXHAUSTED"}
                    or any(marker in message for marker in ("429", "503", "UNAVAILABLE", "RESOURCE_EXHAUSTED"))
                )
                transient = (
                    code in (408, 429, 500, 502, 503, 504)
                    or status in {"UNAVAILABLE", "RESOURCE_EXHAUSTED", "INTERNAL", "DEADLINE_EXCEEDED"}
                    or any(marker in message for marker in (
                        "408", "429", "500", "502", "503", "504", "UNAVAILABLE",
                        "RESOURCE_EXHAUSTED", "INTERNAL", "DEADLINE_EXCEEDED",
                    ))
                )
                if not transient or attempt >= attempts - 1:
                    if is_overloaded:
                        return "", exc
                    raise
                delay = min(2 ** attempt, 8)
                notify(f"Gemini átmenetileg túlterhelt; újrapróbálkozás {delay} másodperc múlva…")
                time.sleep(delay)
        return "", last_error

    notify(f"JARVIS válaszol · {primary_model}")
    answer, error = request_model(primary_model, max_attempts)
    if answer:
        return answer
    if error is not None and not (
        (getattr(error, "code", None) or getattr(error, "status_code", None)) in (429, 503)
        or str(getattr(error, "status", "")).upper() in {"UNAVAILABLE", "RESOURCE_EXHAUSTED"}
        or any(marker in str(error).upper() for marker in ("429", "503", "UNAVAILABLE", "RESOURCE_EXHAUSTED"))
    ):
        raise error

    tried = {primary_model}
    for fallback_model in fallback_models:
        if fallback_model in tried:
            continue
        tried.add(fallback_model)
        notify(f"A {primary_model} túlterhelt; tartalék modell kipróbálása: {fallback_model}…")
        answer, fallback_error = request_model(fallback_model, 1)
        if answer:
            notify(f"Válasz elkészült · {fallback_model}")
            return answer
        error = fallback_error or error
        if error is not None:
            code = getattr(error, "code", None) or getattr(error, "status_code", None)
            status = str(getattr(error, "status", "") or "").upper()
            message = str(error).upper()
            if not (code in (429, 503) or status in {"UNAVAILABLE", "RESOURCE_EXHAUSTED"}
                    or any(marker in message for marker in ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED"))):
                raise error

    if error is not None:
        raise error
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
