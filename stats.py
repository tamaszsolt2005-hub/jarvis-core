"""Print operational lead counts without connecting to Supabase at import time."""
from jarvis_common import get_service_supabase
from jarvis_errors import report_error, sanitize_log_text


def print_jarvis_status() -> None:
    """Fetch and print a compact, privacy-conscious operational summary."""
    print("📊 JARVIS rendszerstatisztika és elemzés lekérése…")
    supabase = None
    try:
        supabase = get_service_supabase()
        leads = supabase.table("leads").select("status").limit(5000).execute().data or []
        logs = (
            supabase.table("logs")
            .select("module,level,message,created_at")
            .order("created_at", desc=True)
            .limit(5)
            .execute()
            .data or []
        )
        counts = {}
        for lead in leads:
            status = lead.get("status") or "unknown"
            counts[status] = counts.get(status, 0) + 1

        print("\n=== JARVIS B2B MOTOR ===")
        print(f"Összes lead: {len(leads)}")
        for status, count in sorted(counts.items()):
            print(f"{status}: {count}")

        print("\n=== LEGFRISSEBB RENDSZERLOGOK ===")
        if not logs:
            print("Nincsenek még logbejegyzések.")
        for log in logs:
            print(sanitize_log_text(f"[{log.get('created_at')}] ({log.get('module')}/{log.get('level')}): {log.get('message')}"))
    except Exception as exc:
        report_error(
            exc,
            module="stats",
            operation="load_system_statistics",
            severity="error",
            db=supabase,
        )
        print(f"Statisztikai lekérdezési hiba: {type(exc).__name__}. A részletek biztonságosan naplózva.")


if __name__ == "__main__":
    print_jarvis_status()
