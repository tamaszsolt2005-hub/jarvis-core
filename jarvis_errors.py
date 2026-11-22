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

_SECRET_PATTERNS = (
    # Assignment-style credentials, including quoted JSON/YAML values.
    re.compile(r"""(?i)(["']?\\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|token|password|passwd|secret|service[_-]?role[_-]?key|client[_-]?secret)["']?\\s*[:=]\\s*["']?)([^"'\\s,;}&]+)"""),
    re.compile(r"(?i)(authorization\\s*[:=]\\s*bearer\\s+)[^\\s,;]+"),
    re.compile(r"(?i)(\\bBearer\\s+)[A-Za-z0-9._~+/=-]{4,}"),
    re.compile(r"(?i)(://[^:/\\s]+:)[^@/\\s]+(@)"),
    re.compile(r"(?i)([?&](?:key|token|api_key|access_token|password|client_secret)=)[^&#\\s]+"),
    # Common cloud/API key prefixes even when the error omits a field name.
    re.compile(r"\\b(?:sk-[A-Za-z0-9_-]{12,}|AIza[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9_]{20,})\\b"),
)
_SECRET_ENV_MARKERS = ("KEY", "TOKEN", "PASSWORD", "PASSWD", "SECRET", "CREDENTIAL", "AUTH")


def sanitize_log_text(value: Any, *, max_length: int = 4000) -> str:
    """Redact credential fields, URL credentials, known env secrets, and common key formats."""
    text = str(value if value is not None else "")
    for index, pattern in enumerate(_SECRET_PATTERNS):
        if index == 3:
            text = pattern.sub(lambda match: match.group(1) + "[REDACTED]" + match.group(2), text)
        elif index == 5:
            text = pattern.sub("[REDACTED]", text)
        else:
            text = pattern.sub(lambda match: match.group(1) + "[REDACTED]", text)

    # Redact configured secrets even when short; do not expose their values in diagnostics.
    # Ignore empty values and avoid replacing ubiquitous one-character environment values.
    for name, secret in os.environ.items():
        if any(marker in name.upper() for marker in _SECRET_ENV_MARKERS) and secret:
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

    Database logging is best-effort and never changes the caller's control flow.
    """
    level = severity.lower().strip()
    if level not in _ALLOWED_LEVELS:
        level = "error"
    timestamp = datetime.now(timezone.utc).isoformat()
    safe_module = sanitize_log_text(module, max_length=80) or "unknown"
    safe_operation = sanitize_log_text(operation, max_length=120) or "unspecified"
    safe_detail = sanitize_log_text(f"{type(error).__name__}: {error}", max_length=2500)
    message = f"timestamp={timestamp} operation={safe_operation} {safe_detail}"

    LOGGER.log(
        _LEVELS[level],
        "[%s] %s",
        safe_module,
        message,
    )

    if db is not None:
        try:
            db.table("logs").insert({
                "module": safe_module,
                "level": level,
                "message": message,
            }).execute()
        except Exception as log_exc:
            # Do not recursively report a failure of the logging backend.
            fallback = sanitize_log_text(f"{type(log_exc).__name__}: {log_exc}", max_length=500)
            LOGGER.error("[jarvis_errors] Supabase error logging failed: %s", fallback)
    return message
