"""Print operational lead counts without exposing personal data."""
from jarvis_common import get_supabase


def run() -> None:
    db = get_supabase()
    rows = db.table("leads").select("status").limit(5000).execute().data or []
    counts = {}
    for row in rows:
        status = row.get("status") or "unknown"
        counts[status] = counts.get(status,0)+1
    print("JARVIS STATUS")
    for status,count in sorted(counts.items()):
        print(f"{status}: {count}")


if __name__ == "__main__":
    run()
