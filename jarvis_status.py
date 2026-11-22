"""Print operational lead counts without exposing personal data."""
from jarvis_common import get_supabase
from jarvis_errors import report_error


def run() -> None:
    db = None
    try:
        db = get_supabase()
        rows = db.table("leads").select("status").limit(5000).execute().data or []
    except Exception as exc:
        report_error(
            exc,
            module="jarvis_status",
            operation="load_lead_status_counts",
            severity="error",
            db=db,
        )
        print(f"JARVIS STATUS: az állapotadatok nem tölthetők be ({type(exc).__name__}).")
        return

    counts = {}
    for row in rows:
        status = row.get("status") or "unknown"
        counts[status] = counts.get(status, 0) + 1
    print("JARVIS STATUS")
    for status, count in sorted(counts.items()):
        print(f"{status}: {count}")


if __name__ == "__main__":
    run()
