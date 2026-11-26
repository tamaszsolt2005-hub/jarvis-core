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

    # Prevent CR/LF and other control characters from forging additional log
    # records or corrupting structured audit fields.
    text = re.sub(r"[\x00-\x1f\x7f]", " ", text)
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
    The structured error column is populated when available; on a confirmed
    missing-column error, the event is retried using legacy logs columns.
    Operation remains in message because no dedicated operation column exists.
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
            # Older production schemas have only module/level/message/created_at.
            # Retry only for a positively identified missing-column/schema-cache
            # error; never hide connectivity, permission, or unknown DB failures.
            error_text = str(log_exc).lower()
            missing_error_column = (
                ("error" in error_text and "column" in error_text)
                or ("error" in error_text and "schema cache" in error_text)
                or ("pgrst204" in error_text and "error" in error_text)
                or ("42703" in error_text and "error" in error_text)
            )
            if missing_error_column:
                try:
                    db.table("logs").insert({
                        "module": safe_module,
                        "level": level,
                        "message": message,
                        "created_at": timestamp,
                    }).execute()
                    LOGGER.warning(
                        "[jarvis_errors] Structured error column unavailable; "
                        "persisted sanitized event using legacy logs columns."
                    )
                    return message
                except Exception as fallback_exc:
                    log_exc = fallback_exc

            # Do not recursively report a failure of the logging backend.
            fallback = sanitize_log_text(f"{type(log_exc).__name__}: {log_exc}", max_length=500)
            LOGGER.error("[jarvis_errors] Supabase error logging failed: %s", fallback)
    return message


_ERROR_HINTS = {
    "missing_configuration": "Hiányzik egy szükséges konfiguráció. Ellenőrizd a Beállítások oldalon jelzett elemeket, majd állítsd be őket a helyi secrets fájlban vagy a futtatási környezetben.",
    "invalid_configuration": "Egy konfigurációs érték hibás vagy nem támogatott. Ellenőrizd a változó nevét, formátumát és a szolgáltatás dokumentációját.",
    "permission_denied": "A művelethez nincs megfelelő jogosultság. Kérj hozzáférést az adminisztrátortól; a JARVIS nem kerüli meg a jogosultsági szabályokat.",
    "authentication_failed": "A hitelesítés sikertelen vagy lejárt. Jelentkezz be újra, és ellenőrizd a hozzáférési beállításokat.",
    "rate_limited": "A szolgáltatás API-korlátot jelzett. Várj, csökkentsd a kérések számát, vagy ellenőrizd a szolgáltatói kvótát és számlázást.",
    "network_error": "A hálózati kapcsolat nem érhető el. Ellenőrizd az internetkapcsolatot, DNS-t, tűzfalat és a szolgáltatás elérhetőségét.",
    "timeout": "A szolgáltatás nem válaszolt időben. Próbáld újra később; az ismétlés előtt ellenőrizd, hogy a művelet nem hajtódott-e már végre.",
    "service_unavailable": "A külső szolgáltatás átmenetileg nem elérhető. A JARVIS korlátozottan újrapróbálkozik; később próbáld újra.",
    "invalid_request": "A szolgáltatás elutasította a kérést. Ellenőrizd a bemeneti adatokat és a modell vagy API beállításait.",
    "audit_unavailable": "Az auditnapló nem írható, ezért a kimenő e-mail-küldést blokkoltam. Ellenőrizd az audit adatbázis-kapcsolatát; a biztonsági ellenőrzést ne kerüld meg.",
    "unknown": "Váratlan hiba történt. A JARVIS biztonságos hibajelzést naplózott; próbáld újra később, vagy add át a hibakódot az adminisztrátornak.",
}


def classify_error(error: BaseException) -> dict[str, Any]:
    """Map provider/network/auth/config exceptions to stable, secret-free categories."""
    name = type(error).__name__.casefold()
    message = str(error).casefold()
    raw_code = getattr(error, "code", None) or getattr(error, "status_code", None)
    raw_status = getattr(error, "status", None)
    status = str(raw_status or "").casefold()
    code_text = str(raw_code or "").casefold()
    text = f"{name} {message} {status} {code_text}"
    try:
        numeric_code = int(raw_code) if raw_code is not None else None
    except (TypeError, ValueError):
        numeric_code = None
    # Provider SDKs expose both numeric HTTP codes and symbolic status enums.
    # Only expose a constrained code in UI hints; never echo arbitrary SDK fields.
    safe_code = (
        str(raw_code)[:40]
        if raw_code is not None and re.fullmatch(r"(?:[0-9]{3}|[A-Za-z][A-Za-z0-9_]{0,39})", str(raw_code))
        else None
    )
    category = "unknown"
    retryable = False

    if "auditnapló nem írható" in text or "audit log is not writable" in text:
        category = "audit_unavailable"
    elif isinstance(error, PermissionError) or numeric_code == 403 or any(
        marker in text for marker in ("permission denied", "permission_denied", "forbidden", "insufficient permission", "rls")
    ):
        category = "permission_denied"
    elif numeric_code == 401 or any(marker in text for marker in (
        "unauthorized", "unauthenticated", "invalid credentials", "invalid api key",
        "api_key_invalid", "api key not valid", "api key is invalid",
    )):
        category = "authentication_failed"
    elif any(marker in text for marker in ("missing configuration", "hiányzó beállítás", "not configured", "required_secret")):
        category = "missing_configuration"
    elif any(marker in text for marker in ("invalid configuration", "invalid url", "malformed url", "unsupported scheme")):
        category = "invalid_configuration"
    elif numeric_code == 429 or any(marker in text for marker in ("resource_exhausted", "rate limit", "quota exceeded", "too many requests", "429")):
        category = "rate_limited"
        retryable = True
    elif numeric_code in (408, 504) or any(marker in text for marker in ("timeout", "timed out", "deadline_exceeded")):
        category = "timeout"
        retryable = True
    elif numeric_code in (500, 502, 503) or status.endswith(("internal", "unavailable")) or code_text in {"internal", "unavailable"} or any(marker in text for marker in ("internal server error", "service unavailable", "bad gateway", "500", "503")):
        category = "service_unavailable"
        retryable = True
    elif isinstance(error, (ConnectionError, OSError)) or any(
        marker in text for marker in (
            "connectionerror", "connecterror", "connection refused", "connection reset",
            "name or service not known", "temporary failure in name resolution", "dns",
            "network is unreachable",
        )
    ):
        category = "network_error"
        retryable = True
    elif numeric_code in (400, 422) or any(marker in text for marker in ("invalid argument", "invalid request", "bad request")):
        category = "invalid_request"

    return {
        "category": category,
        "retryable": retryable,
        "code": safe_code,
        "user_message": _ERROR_HINTS[category],
    }


def user_facing_error(error: BaseException) -> str:
    """Return a stable Hungarian hint without exposing provider response bodies."""
    result = classify_error(error)
    code = result.get("code")
    suffix = f" (hibakód: {code})" if code else ""
    return result["user_message"] + suffix
