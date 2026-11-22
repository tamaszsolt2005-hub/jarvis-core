"""Import manually reviewed CSV records; never invent prospect identities."""
from __future__ import annotations

import csv
import re
from datetime import datetime

from jarvis_common import get_supabase, log_event
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
        timestamp_is_aware = parsed.tzinfo is not None and parsed.utcoffset() is not None
    except (TypeError, ValueError):
        timestamp_is_aware = False

    if not company or len(company) > 250 or not EMAIL_RE.fullmatch(address) or basis != "consent" or not approved or not timestamp_is_aware:
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
    try:
        db = get_supabase()
        imported = skipped = 0
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
                db.table("leads").insert(record).execute()
                imported += 1
        log_event(db, "lead_gen", f"CSV import: {imported} új lead, {skipped} kihagyva.")
        print(f"Import kész: {imported} új, {skipped} kihagyott rekord.")
    except Exception as exc:
        report_error(
            exc, module="lead_gen", operation="import_reviewed_csv",
            severity="error", db=db,
        )
        raise


if __name__ == "__main__":
    run()
