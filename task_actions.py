"""Explicit, approval-gated task actions for the JARVIS chat."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo
from uuid import uuid4

from jarvis_common import audit_event
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
        parts = [part.strip() for part in payload.split(";") if part.strip()]
        if not parts:
            return {"error": "A feladat címét add meg."}
        fields: dict[str, str] = {"title": parts[0]}
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
            fields[normalized] = value.strip()
        if not fields["title"] or len(fields["title"]) > 180:
            return {"error": "A feladat címe 1–180 karakter lehet."}
        priority = fields.get("priority", "normal").casefold()
        if priority not in _PRIORITIES:
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
        for part in payload.split(";"):
            if "=" not in part:
                return {"error": f"Nem értelmezhető mező: {part.strip()}."}
            key, value = part.split("=", 1)
            key, value = key.strip().casefold(), value.strip()
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


def _execute_task_action(db: Any, action: dict[str, Any]) -> str:
    """Execute a previously parsed action only after the chat approval gate."""
    kind = action.get("type")
    operation_id = str(uuid4())
    audit_action = "task_" + str(kind or "unknown")
    if not audit_event(
        db, module="task_actions", action=audit_action, status="pending",
        operation_id=operation_id, approved=True,
        result={"task_id": action.get("id"), "title": action.get("title")},
    ):
        raise RuntimeError("A feladatműveletet nem hajtottam végre: az auditnapló nem írható.")
    if kind == "create":
        payload = {
            "title": action["title"], "priority": action["priority"],
            "due_at": action.get("due_at"), "notes": action.get("notes") or None,
            "status": "open",
        }
        result = db.table("tasks").insert(payload).execute()
        row = (result.data or [{}])[0]
        audit_event(db, module="task_actions", action=audit_action, status="success", operation_id=operation_id, approved=True, result={"task_id": row.get("id")})
        return f"Feladat létrehozva: **{action['title']}** (azonosító: {row.get('id', 'a rendszer visszaigazolása szerint')})."

    task_id = action.get("id")
    existing = db.table("tasks").select("id,title,status").eq("id", task_id).limit(1).execute().data or []
    if not existing:
        audit_event(db, module="task_actions", action=audit_action, status="blocked", operation_id=operation_id, approved=True, result={"reason": "not_found"})
        return "A feladat nem található; nem történt módosítás."
    if str(existing[0].get("status") or "").casefold() != "open":
        audit_event(db, module="task_actions", action=audit_action, status="blocked", operation_id=operation_id, approved=True, result={"reason": "not_open"})
        return "A feladat már nem nyitott; az előkészített műveletet nem hajtottam végre."
    title = existing[0].get("title") or task_id
    if kind == "close":
        now = datetime.now(timezone.utc).isoformat()
        result = db.table("tasks").update({
            "status": "done", "completed_at": now, "updated_at": now,
        }).eq("id", task_id).eq("status", "open").select("id").execute()
        if not result.data:
            audit_event(db, module="task_actions", action=audit_action, status="blocked", operation_id=operation_id, approved=True, result={"reason": "concurrent_change"})
            return "A feladat állapota időközben megváltozott; nem történt lezárás."
        audit_event(db, module="task_actions", action=audit_action, status="success", operation_id=operation_id, approved=True, result={"task_id": task_id})
        return f"Feladat lezárva: **{title}**."
    if kind == "update":
        payload = dict(action["updates"])
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        result = db.table("tasks").update(payload).eq("id", task_id).eq("status", "open").select("id").execute()
        if not result.data:
            audit_event(db, module="task_actions", action=audit_action, status="blocked", operation_id=operation_id, approved=True, result={"reason": "concurrent_change"})
            return "A feladat állapota időközben megváltozott; nem történt módosítás."
        audit_event(db, module="task_actions", action=audit_action, status="success", operation_id=operation_id, approved=True, result={"task_id": task_id, "updated_fields": sorted(action["updates"])})
        return f"Feladat módosítva: **{title}**."
    return "Ismeretlen feladatművelet; nem történt módosítás."



def execute_task_action(db: Any, action: dict[str, Any]) -> str:
    """Centrally report task-action failures without bypassing audit or approval gates."""
    try:
        return _execute_task_action(db, action)
    except Exception as exc:
        report_error(
            exc, module="task_actions", operation=f"execute:{action.get('type', 'unknown')}",
            severity="critical", db=db,
        )
        raise
