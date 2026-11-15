"""Daily GitHub Actions entry point for global company research."""
from __future__ import annotations

import json

from global_lead_research import get_research_market, research_global_companies
from jarvis_common import get_supabase


def main() -> None:
    db = get_supabase()
    market = get_research_market(db)
    result = research_global_companies(
        db,
        "Globális, iparág- és cégméret-független üzleti lehetőségkutatás. "
        "Keress változatos országokból és szektorokból valós, működő vállalkozásokat. "
        "A szolgáltatás üzleti automatizálási és AI-megoldásokat kínál. "
        "Csak céges adatokat rögzíts; személyes elérhetőséget és hozzájárulást ne következtess ki.",
        max_results=15,
        market_country=market,
    )
    print(json.dumps({
        "scope": result["scope"],
        "saved_count": result["saved_count"],
        "skipped_count": result["skipped_count"],
        "email_sending": result["email_sending"],
        "contact_permission": result["contact_permission"],
        "companies": result["companies"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
