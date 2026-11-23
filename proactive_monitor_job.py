"""GitHub Actions entry point for the daily, read-only proactive monitor."""
from __future__ import annotations

from jarvis_common import get_supabase
from proactive_monitor import run_proactive_monitor


def main() -> None:
    """Run the monitor and print its report; failures remain non-zero for CI."""
    db = get_supabase()
    report = run_proactive_monitor(db)
    print(report, end="")


if __name__ == "__main__":
    main()
