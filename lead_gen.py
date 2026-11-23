"""Import manually reviewed CSV records; never invent prospect identities."""
from __future__ import annotations

import csv
import re
from datetime import datetime, timezone
import uuid

from jarvis_common import audit_event, get_service_supabase, log_event
from jarvis_errors import report_error

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _truth(value):
    return str(value).strip().lower() in {"true", "1", "yes", "igen"}


def _validated_import_row(row):
    company = str(row.get("company_name") or "").strip()
    address = str(row.get("email") or "").strip().lower()
    basis = str(row.get("consent_basis") or "").strip().lower()
    approved = _truth(row.get("approved_to_contact", ""))
    confirmed = str(row.get("consent_confirmed_at") or "").strip()
    try:
        parsed = datetime.fromisoformat(confirmed.replace("Z", "+00:00"))
        timestamp_is_aware = (
            parsed.tzinfo is not None
            and parsed.utcoffset() is not None
            and parsed <= datetime.now(timezone.utc)
        )
    except (TypeError, ValueError):
        timestamp_is_aware = False

    if (
        not company
        or len(company) > 250
        or len(address) > 254
        or not EMAIL_RE.fullmatch(address)
        or basis != "consent"
        or not approved
        or not timestamp_is_aware
        or _truth(row.get("opted_out", ""))
        or bool(str(row.get("reply_category") or "").strip())
        or bool(str(row.get("last_inbound_message_id") or "").strip())
    ):
        return None

    return {
        "company_name": company, "email": address,
        "website": str(row.get("website") or "").strip()[:2048] or None,
        "notes": str(row.get("notes") or "").strip()[:4000] or None,
        "source": str(row.get("source") or "reviewed_csv").strip()[:120],
        "consent_basis": "consent", "approved_to_contact": True,
        "consent_confirmed_at": parsed.isoformat(), "opted_out": False, "status": "new",
    }


def run(path="data/leads.csv"):
    db = None
    side_effect_started = False
    lead_operation_id = None
    lead_write_attempted = False
    try:
        db = get_service_supabase()
        imported = skipped = 0
        operation_id = str(uuid.uuid4())
        if not audit_event(
            db,
            module="lead_gen",
            action="import_reviewed_csv",
            status="pending",
            operation_id=operation_id,
            result={"source_type": "reviewed_csv"},
        ):
            raise RuntimeError("CSV-import leállítva: a pending auditbejegyzés nem menthető.")
        with open(path, newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                record = _validated_import_row(row)
                if record is None:
                    skipped += 1
                    continue
                exists = db.table("leads").select("id").ilike("email", record["email"]).limit(1).execute().data
                if exists:
                    skipped += 1
                    continue
                lead_operation_id = str(uuid.uuid4())
                lead_write_attempted = False
                if not audit_event(
                    db,
                    module="lead_gen",
                    action="create_reviewed_lead",
                    status="pending",
                    operation_id=lead_operation_id,
                    result={"source_type": "reviewed_csv"},
                ):
                    raise RuntimeError("Lead mentése leállítva: a pending auditbejegyzés nem menthető.")
                side_effect_started = True
                lead_write_attempted = True
                inserted = db.table("leads").insert(record).execute()
                inserted_rows = getattr(inserted, "data", None) or []
                lead_id = inserted_rows[0].get("id") if inserted_rows and isinstance(inserted_rows[0], dict) else None
                if not audit_event(
                    db,
                    module="lead_gen",
                    action="create_reviewed_lead",
                    status="success",
                    operation_id=lead_operation_id,
                    result={"lead_id": str(lead_id) if lead_id is not None else None},
                ):
                    raise RuntimeError("A lead mentése megtörtént, de a záró auditbejegyzés nem menthető.")
                lead_operation_id = None
                lead_write_attempted = False
                imported += 1
        if not audit_event(
            db,
            module="lead_gen",
            action="import_reviewed_csv",
            status="success",
            operation_id=operation_id,
            result={"imported": imported, "skipped": skipped},
        ):
            raise RuntimeError("A CSV-import befejeződött, de a záró auditbejegyzés nem menthető.")
        log_event(db, "lead_gen", f"CSV import: {imported} új lead, {skipped} kihagyva.")
        print(f"Import kész: {imported} új, {skipped} kihagyott rekord.")
    except Exception as exc:
        if db is not None and lead_operation_id:
            audit_event(
                db,
                module="lead_gen",
                action="create_reviewed_lead",
                status="unknown" if lead_write_attempted else "failed",
                operation_id=lead_operation_id,
                error=exc,
                level="error",
            )
        if db is not None and "operation_id" in locals():
            audit_event(
                db,
                module="lead_gen",
                action="import_reviewed_csv",
                status="unknown" if side_effect_started else "failed",
                operation_id=operation_id,
                error=exc,
                result={"imported": imported, "skipped": skipped},
                level="error",
            )
        report_error(
            exc, module="lead_gen", operation="import_reviewed_csv",
            severity="error", db=db,
        )
        raise


if __name__ == "__main__":
    run()
