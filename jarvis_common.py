"""Shared configuration, Supabase, Gemini and logging helpers."""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from jarvis_errors import report_error, sanitize_log_text

from google import genai
from google.genai import types
from supabase import Client, create_client

LOGGER = logging.getLogger("jarvis")


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
    if len(text) > 900 or sum(text.count(marker) for marker in multi_part_markers) >= 2:
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
    """Write a sanitized application event to the existing Supabase logs table."""
    safe_level = level.lower().strip()
    if safe_level not in {"debug", "info", "warning", "error", "critical"}:
        safe_level = "info"
    try:
        supabase.table("logs").insert({
            "module": sanitize_log_text(module, max_length=80),
            "level": safe_level,
            "message": sanitize_log_text(message, max_length=4000),
        }).execute()
    except Exception as exc:
        report_error(
            exc,
            module="jarvis_common",
            operation="write_application_log",
            severity="error",
        )



def audit_event(
    supabase: Client,
    *,
    module: str,
    action: str,
    status: str,
    operation_id: str | None = None,
    result: Any | None = None,
    error: BaseException | str | None = None,
    approved: bool | None = None,
    recipient: str | None = None,
    subject: str | None = None,
    delivery_id: str | None = None,
    level: str = "info",
) -> bool:
    """Append a structured, secret-safe audit event to the existing logs table.

    Returns False on persistence failure. Callers performing sensitive external
    actions must fail closed when the required audit record cannot be persisted.
    Email bodies and arbitrary payloads are intentionally not accepted.
    """
    safe_status = str(status or "").strip().lower()
    if safe_status not in {"pending", "success", "failed", "blocked", "unknown"}:
        safe_status = "unknown"
    safe_level = str(level or "info").strip().lower()
    if safe_level not in {"debug", "info", "warning", "error", "critical"}:
        safe_level = "info"
    try:
        op_id = str(uuid.UUID(operation_id)) if operation_id else str(uuid.uuid4())
    except (TypeError, ValueError, AttributeError):
        LOGGER.warning("Invalid audit operation id supplied; generated a new id")
        op_id = str(uuid.uuid4())

    safe_module = sanitize_log_text(module, max_length=80) or "unknown"
    safe_action = sanitize_log_text(action, max_length=120) or "unspecified"
    safe_recipient = sanitize_log_text(recipient, max_length=254) if recipient else None
    safe_subject = sanitize_log_text(subject, max_length=300) if subject else None
    safe_delivery_id = sanitize_log_text(delivery_id, max_length=250) if delivery_id else None
    safe_error = sanitize_log_text(
        f"{type(error).__name__}: {error}" if isinstance(error, BaseException) else error,
        max_length=1500,
    ) if error else None
    def sanitize_result(value: Any, depth: int = 0) -> Any:
        if depth > 4:
            return "[DEPTH_LIMIT]"
        if isinstance(value, str):
            return sanitize_log_text(value, max_length=500)
        if isinstance(value, dict):
            cleaned = {}
            for key, item in list(value.items())[:50]:
                safe_key = sanitize_log_text(str(key), max_length=80)
                key_upper = safe_key.upper()
                if any(marker in key_upper for marker in ("KEY", "TOKEN", "PASSWORD", "SECRET")):
                    cleaned[safe_key] = "[REDACTED]"
                else:
                    cleaned[safe_key] = sanitize_result(item, depth + 1)
            return cleaned
        if isinstance(value, (list, tuple)):
            return [sanitize_result(item, depth + 1) for item in value[:50]]
        if value is None or isinstance(value, (bool, int, float)):
            return value
        return sanitize_log_text(str(value), max_length=500)

    try:
        safe_result = sanitize_result(result) if result is not None else None
        if safe_result is not None and len(json.dumps(safe_result, ensure_ascii=False, default=str)) > 2000:
            safe_result = {"truncated": True}
    except (TypeError, ValueError):
        safe_result = None

    row = {
        "module": safe_module,
        "level": safe_level,
        "message": f"audit:{safe_action}|status={safe_status}",
        "operation_id": op_id,
        "action": safe_action,
        "status": safe_status,
        "result": safe_result,
        "error": safe_error,
        "approved": approved,
        "recipient": safe_recipient,
        "subject": safe_subject,
        "delivery_id": safe_delivery_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        supabase.table("logs").insert(row).execute()
        return True
    except Exception as exc:
        LOGGER.error(
            "[jarvis_common] Audit persistence failed for %s/%s: %s",
            safe_module, safe_action,
            sanitize_log_text(f"{type(exc).__name__}: {exc}", max_length=500),
        )
        return False



def get_audit_events(
    supabase: Client,
    *,
    limit: int = 100,
    module: str | None = None,
    action: str | None = None,
    status: str | None = None,
    operation_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return newest structured audit events from the existing logs table."""
    safe_limit = max(1, min(int(limit), 1000))
    query = (
        supabase.table("logs")
        .select(
            "id,operation_id,created_at,module,action,status,result,error,"
            "approved,recipient,subject,delivery_id,level"
        )
        .not_.is_("action", "null")
        .order("created_at", desc=True)
        .limit(safe_limit)
    )
    for field, value in (
        ("module", module), ("action", action),
        ("status", status), ("operation_id", operation_id),
    ):
        if value:
            query = query.eq(field, value)
    try:
        return query.execute().data or []
    except Exception as exc:
        report_error(
            exc, module="jarvis_common", operation="query_audit_events",
            severity="warning", db=supabase,
        )
        return []



def get_setting(supabase: Client, key: str, default: Any = None) -> Any:
    try:
        result = supabase.table("settings").select("value").eq("key", key).limit(1).execute()
        if result.data:
            return result.data[0].get("value", default)
    except Exception as exc:
        report_error(
            exc,
            module="jarvis_common",
            operation=f"read_setting:{sanitize_log_text(key, max_length=80)}",
            severity="warning",
            db=supabase,
        )
    return default


def set_setting(supabase: Client, key: str, value: Any) -> None:
    supabase.table("settings").upsert({"key": key, "value": value}).execute()
