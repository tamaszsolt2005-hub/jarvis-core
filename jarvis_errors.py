"""Central, secret-safe error reporting for JARVIS."""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

LOGGER = logging.getLogger("jarvis")
_LEVELS = {"warning": logging.WARNING, "error": logging.ERROR, "critical": logging.CRITICAL}
_ALLOWED_LEVELS = {"warning", "error", "critical"}
_SECRET_ENV_MARKERS = ("KEY", "TOKEN", "PASSWORD", "PASSWD", "SECRET", "CREDENTIAL", "AUTH")
_REGISTERED_SECRET_VALUES: set[str] = set()
_MAX_REGISTERED_SECRETS = 256

_SECRET_PATTERNS = (
    # Assignment-style credentials, including quoted values containing spaces.
    re.compile(
        r"""(?i)(["']?\b(?:api[_-]?key|anon[_-]?key|service[_-]?role[_-]?key|access[_-]?token|refresh[_-]?token|token|password|passwd|secret|client[_-]?secret|credential|auth)["']?\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,;}&]+)"""
    ),
    # HTTP authentication headers, including Basic and custom schemes.
    re.compile(r"(?i)((?:authorization|proxy-authorization)\s*:\s*)[^\r\n]+"),
    re.compile(r"(?i)(\bBearer\s+)[^\s,;]+"),
    re.compile(r"(?i)(://[^:/\s]+:)[^@/\s]+(@)"),
    re.compile(r"(?i)([?&](?:key|api-key|api_key|token|access_token|password|client_secret)=)[^&#\s]+"),
    re.compile(r"\b(?:sk-[A-Za-z0-9_-]{12,}|AIza[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9_]{20,})\b"),
)


def _is_secret_name(name: str) -> bool:
    upper = str(name or "").upper()
    return any(marker in upper for marker in _SECRET_ENV_MARKERS)


def register_secret_value(value: Any, *, name: str | None = None) -> None:
    """Register a value only when its configuration name denotes a credential."""
    if value is None or (name is not None and not _is_secret_name(name)):
        return
    secret = str(value)
    if len(secret) < 2:
        return
    if secret not in _REGISTERED_SECRET_VALUES and len(_REGISTERED_SECRET_VALUES) >= _MAX_REGISTERED_SECRETS:
        # Bound process-lifetime retention; current environment secrets are also scanned below.
        _REGISTERED_SECRET_VALUES.pop()
    _REGISTERED_SECRET_VALUES.add(secret)


def sanitize_log_text(value: Any, *, max_length: int = 4000) -> str:
    """Redact credential assignments, auth headers, registered secrets and env secrets."""
    text = str(value if value is not None else "")
    for index, pattern in enumerate(_SECRET_PATTERNS):
        if index == 3:
            text = pattern.sub(lambda match: match.group(1) + "[REDACTED]" + match.group(2), text)
        elif index == 5:
            text = pattern.sub("[REDACTED]", text)
        else:
            text = pattern.sub(lambda match: match.group(1) + "[REDACTED]", text)

    for secret in sorted(_REGISTERED_SECRET_VALUES, key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    env_secrets = (
        secret for name, secret in os.environ.items()
        if _is_secret_name(name) and secret and len(secret) >= 2
    )
    for secret in sorted(env_secrets, key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    return text[:max(0, int(max_length))]


def report_error(
    error: BaseException,
    *,
    module: str,
    operation: str,
    severity: str = "error",
    db: Any | None = None,
) -> str:
    """Report a sanitized error locally and, when supplied, to the existing logs table.

    Supabase persistence is best-effort and never changes the caller's control flow.
    The logs table's existing error and created_at columns are populated explicitly;
    operation remains in message because no dedicated operation column exists.
    """
    level = str(severity or "error").lower().strip()
    if level not in _ALLOWED_LEVELS:
        level = "error"
    timestamp = datetime.now(timezone.utc).isoformat()
    safe_module = sanitize_log_text(module, max_length=80) or "unknown"
    safe_operation = sanitize_log_text(operation, max_length=120) or "unspecified"
    safe_detail = sanitize_log_text(f"{type(error).__name__}: {error}", max_length=2500)
    message = f"timestamp={timestamp} operation={safe_operation} {safe_detail}"

    LOGGER.log(_LEVELS[level], "[%s] %s", safe_module, message)

    if db is not None:
        try:
            db.table("logs").insert({
                "module": safe_module,
                "level": level,
                "message": message,
                "error": safe_detail,
                "created_at": timestamp,
            }).execute()
        except Exception as log_exc:
            # Do not recursively report a failure of the logging backend.
            fallback = sanitize_log_text(f"{type(log_exc).__name__}: {log_exc}", max_length=500)
            LOGGER.error("[jarvis_errors] Supabase error logging failed: %s", fallback)
    return message
