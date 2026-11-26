"""Explicit, approval-gated task actions for the JARVIS chat."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo
from uuid import uuid4

from jarvis_common import get_enforced_user_supabase
from jarvis_errors import report_error


_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.I)
_PRIORITIES = {"normal", "high", "urgent"}
_LOCAL_TZ = ZoneInfo("Europe/Budapest")


def _deadline_iso(value: str) -> str:
    day = datetime.strptime(value, "%Y-%m-%d").date()
    return datetime(day.year, day.month, day.day, 23, 59, tzinfo=_LOCAL_TZ).isoformat()


def parse_task_command(message: str) -> dict[str, Any] | None:
    """Parse only explicit, structured task commands; never infer an action."""
    text = (message or "").strip()
    lower = text.casefold()

    if lower.startswith(("hozz létre feladat:", "hozz letre feladat:", "új feladat:", "uj feladat:")):
        payload = text.split(":", 1)[1].strip()
        if not payload:
            return {"error": "A feladat címét add meg."}
        raw_parts = payload.split(";")
        if any(not part.strip() for part in raw_parts):
            return {"error": "A parancs üres mezőt tartalmaz; távolítsd el a felesleges pontosvesszőt."}
        parts = [part.strip() for part in raw_parts]
        if not parts:
            return {"error": "A feladat címét add meg."}
        fields: dict[str, str] = {"title": parts[0]}
        explicit_fields: set[str] = set()
        aliases = {
            "cím": "title", "cim": "title", "határidő": "due_date",
            "hatarido": "due_date", "prioritás": "priority", "prioritas": "priority",
            "leírás": "notes", "leiras": "notes",
        }
        for part in parts[1:]:
            if "=" not in part:
                return {"error": f"Nem értelmezhető mező: {part}. Használj mező=érték formátumot."}
            key, value = part.split("=", 1)
            normalized = aliases.get(key.strip().casefold())
            if not normalized or not value.strip():
                return {"error": f"Ismeretlen vagy üres mező: {key.strip()}."}
            if normalized in explicit_fields:
                return {"error": f"A(z) {key.strip()} mező többször szerepel."}
            explicit_fields.add(normalized)
            fields[normalized] = value.strip()
        if not fields["title"] or len(fields["title"]) > 180:
            return {"error": "A feladat címe 1–180 karakter lehet."}
        priority = fields.get("priority", "normal").casefold()
        if not isinstance(priority, str) or priority not in _PRIORITIES:
            return {"error": "A prioritás csak normal, high vagy urgent lehet."}
        due_date = fields.get("due_date")
        if due_date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", due_date):
            return {"error": "A határidő formátuma ÉÉÉÉ-HH-NN legyen."}
        if due_date:
            try:
                datetime.strptime(due_date, "%Y-%m-%d")
            except ValueError:
                return {"error": "A megadott határidő nem érvényes dátum."}
        return {"type": "create", "title": fields["title"], "priority": priority,
                "due_at": _deadline_iso(due_date) if due_date else None,
                "notes": fields.get("notes", "")[:1000]}

    close_match = re.match(
        r"^(?:zárd le|zard le|fejezd be) (?:a )?feladat(?:ot)?:?\s*([0-9a-f-]{36})$",
        text, re.I,
    )
    if close_match:
        task_id = close_match.group(1)
        return {"type": "close", "id": task_id} if _UUID.fullmatch(task_id) else {"error": "Érvénytelen feladatazonosító."}

    update_match = re.match(r"^(?:módosítsd|modositsd) (?:a )?feladat(?:ot)?:\s*([0-9a-f-]{36})\s*;(.+)$", text, re.I)
    if update_match:
        task_id, payload = update_match.groups()
        if not _UUID.fullmatch(task_id):
            return {"error": "Érvénytelen feladatazonosító."}
        updates: dict[str, Any] = {}
        update_parts = payload.split(";")
        if any(not part.strip() for part in update_parts):
            return {"error": "A módosítás üres mezőt tartalmaz; távolítsd el a felesleges pontosvesszőt."}
        for part in update_parts:
            if "=" not in part:
                return {"error": f"Nem értelmezhető mező: {part.strip()}."}
            key, value = part.split("=", 1)
            key, value = key.strip().casefold(), value.strip()
            normalized_key = (
                "priority" if key in {"prioritás", "prioritas"}
                else "due_at" if key in {"határidő", "hatarido"}
                else "title" if key in {"cím", "cim"}
                else None
            )
            if normalized_key and normalized_key in updates:
                return {"error": f"A(z) {key} mező többször szerepel."}
            if key in {"prioritás", "prioritas"} and value.casefold() in _PRIORITIES:
                updates["priority"] = value.casefold()
            elif key in {"határidő", "hatarido"} and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                try:
                    datetime.strptime(value, "%Y-%m-%d")
                except ValueError:
                    return {"error": "A megadott határidő nem érvényes dátum."}
                updates["due_at"] = _deadline_iso(value)
            elif key in {"cím", "cim"} and value and len(value) <= 180:
                updates["title"] = value
            else:
                return {"error": f"Nem engedélyezett vagy érvénytelen mező: {key}."}
        return {"type": "update", "id": task_id, "updates": updates} if updates else {"error": "Nem adtál meg módosítandó mezőt."}
    return None



def _validate_action(action: Any) -> None:
    """Validate the complete task payload before any audit or database access."""
    if not isinstance(action, dict):
        raise ValueError("Érvénytelen feladatművelet.")

    kind = action.get("type")
    if not isinstance(kind, str):
        raise ValueError("Ismeretlen feladatművelet.")
    if kind == "create":
        if set(action) - {"type", "title", "priority", "due_at", "notes", "lead_id", "operation_id"}:
            raise ValueError("A létrehozási művelet nem támogatott mezőt tartalmaz.")
        title = action.get("title")
        priority = action.get("priority")
        notes = action.get("notes", "")
        if not isinstance(title, str) or not title.strip() or len(title) > 180:
            raise ValueError("A feladat címe 1–180 karakter lehet.")
        if not isinstance(priority, str) or priority not in _PRIORITIES:
            raise ValueError("Érvénytelen feladatprioritás.")
        if not isinstance(notes, str) or len(notes) > 1000:
            raise ValueError("A feladat leírása legfeljebb 1000 karakter lehet.")
        operation_id = action.get("operation_id")
        if not isinstance(operation_id, str) or not _UUID.fullmatch(operation_id):
            raise ValueError("Érvénytelen műveletazonosító.")
        if "lead_id" in action and (
            not isinstance(action["lead_id"], str) or not _UUID.fullmatch(action["lead_id"])
        ):
            raise ValueError("Érvénytelen kapcsolódó leadazonosító.")
        due_at = action.get("due_at")
        if due_at is not None:
            if not isinstance(due_at, str):
                raise ValueError("Érvénytelen feladat-határidő.")
            try:
                parsed_due = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("Érvénytelen feladat-határidő.") from exc
            if parsed_due.tzinfo is None or parsed_due.utcoffset() is None:
                raise ValueError("A feladat-határidőnek időzónát kell tartalmaznia.")
        return

    if kind in {"close", "update"}:
        if set(action) - ({"type", "id", "operation_id"} if kind == "close" else {"type", "id", "updates", "operation_id"}):
            raise ValueError("A feladatművelet nem támogatott mezőt tartalmaz.")
        operation_id = action.get("operation_id")
        if not isinstance(operation_id, str) or not _UUID.fullmatch(operation_id):
            raise ValueError("Érvénytelen műveletazonosító.")
        task_id = action.get("id")
        if not isinstance(task_id, str) or not _UUID.fullmatch(task_id):
            raise ValueError("Érvénytelen feladatazonosító.")
        if kind == "close":
            return
        updates = action.get("updates")
        if not isinstance(updates, dict) or not updates:
            raise ValueError("Nem adtál meg módosítandó mezőt.")
        if set(updates) - {"title", "priority", "due_at"}:
            raise ValueError("A feladatmódosítás nem engedélyezett mezőt tartalmaz.")
        if "title" in updates and (
            not isinstance(updates["title"], str)
            or not updates["title"].strip()
            or len(updates["title"]) > 180
        ):
            raise ValueError("A feladat címe 1–180 karakter lehet.")
        if "priority" in updates and (
            not isinstance(updates["priority"], str)
            or updates["priority"] not in _PRIORITIES
        ):
            raise ValueError("Érvénytelen feladatprioritás.")
        if "due_at" in updates:
            due_at = updates["due_at"]
            if not isinstance(due_at, str):
                raise ValueError("Érvénytelen feladat-határidő.")
            try:
                parsed_due = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("Érvénytelen feladat-határidő.") from exc
            if parsed_due.tzinfo is None or parsed_due.utcoffset() is None:
                raise ValueError("A feladat-határidőnek időzónát kell tartalmaznia.")
        return

    raise ValueError("Ismeretlen feladatművelet.")


def execute_task_action(
    db: Any,
    action: dict[str, Any],
    *,
    approved: bool = False,
    approval: dict[str, str] | None = None,
    auth_session: dict[str, str] | None = None,
) -> str:
    """Execute a task through one database transaction that consumes approval,
    appends audit events and stores an idempotent operation result.
    """
    if approved is not True:
        raise PermissionError("A feladatművelethez külön felhasználói jóváhagyás szükséges.")
    _validate_action(action)

    if not isinstance(approval, dict):
        raise PermissionError("A feladatművelethez adatbázisban rögzített jóváhagyás szükséges.")
    token = approval.get("token")
    principal = approval.get("principal")
    if not isinstance(token, str) or len(token) < 32:
        raise PermissionError("A jóváhagyási token hiányzik vagy érvénytelen.")
    if not isinstance(principal, str) or not principal.strip() or len(principal) > 100:
        raise PermissionError("A jóváhagyás felhasználói kötése hiányzik vagy érvénytelen.")

    # The enforcement helper swaps the legacy service client for a verified
    # user-JWT client whenever Auth/RBAC enforcement is enabled.
    enforced = get_enforced_user_supabase(
        auth_session, "tasks.write", allowed_roles={"admin", "operator"}
    )
    if enforced is not None:
        db, _refreshed_session = enforced

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    operation_id = action["operation_id"]
    try:
        response = db.rpc(
            "execute_approved_task_action",
            {
                "p_token_hash": token_hash,
                "p_principal": principal,
                "p_operation_id": operation_id,
                "p_action": action,
            },
        ).execute()
        result = response.data
        if isinstance(result, list) and len(result) == 1:
            result = result[0]
        if not isinstance(result, dict) or not isinstance(result.get("message"), str):
            raise RuntimeError("A feladatművelet adatbázis-visszaigazolása érvénytelen.")
        return result["message"]
    except Exception as exc:
        report_error(
            exc,
            module="task_actions",
            operation=f"execute_atomic:{action.get('type', 'unknown')}",
            severity="critical",
            db=db,
        )
        raise
