"""Print operational lead counts without connecting to Supabase at import time."""
from jarvis_common import get_supabase


def print_jarvis_status() -> None:
    """Fetch and print a compact, privacy-conscious operational summary."""
    print("📊 JARVIS rendszerstatisztika és elemzés lekérése…")
    try:
        supabase = get_supabase()
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
            print(f"[{log.get('created_at')}] ({log.get('module')}/{log.get('level')}): {log.get('message')}")
    except Exception as exc:
        print(f"Statisztikai lekérdezési hiba: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    print_jarvis_status()
