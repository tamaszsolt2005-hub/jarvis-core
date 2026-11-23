"""Daily GitHub Actions entry point for global company research."""
from __future__ import annotations

import json
import uuid

from global_lead_research import get_research_market, research_global_companies
from jarvis_common import audit_event, get_supabase
from jarvis_errors import report_error


def main() -> None:
    db = None
    operation_id = str(uuid.uuid4())
    research_started = False
    try:
        db = get_supabase()
        if not audit_event(
            db,
            module="global_lead_research_job",
            action="daily_global_research",
            status="pending",
            operation_id=operation_id,
            result={"max_results": 15, "contact_permission": "never_granted_by_research"},
        ):
            raise RuntimeError("Kutatási automatizmus leállítva: a pending audit nem menthető.")
        market = get_research_market(db)
        research_started = True
        result = research_global_companies(
            db,
            "Globális, iparág- és cégméret-független üzleti lehetőségkutatás. "
            "Keress változatos országokból és szektorokból valós, működő vállalkozásokat. "
            "A szolgáltatás üzleti automatizálási és AI-megoldásokat kínál. "
            "Csak céges adatokat rögzíts; személyes elérhetőséget és hozzájárulást ne következtess ki.",
            max_results=15,
            market_country=market,
        )
        if not audit_event(
            db,
            module="global_lead_research_job",
            action="daily_global_research",
            status="success",
            operation_id=operation_id,
            result={
                "saved_count": int(result.get("saved_count", 0)),
                "skipped_count": int(result.get("skipped_count", 0)),
                "email_sending": bool(result.get("email_sending", False)),
                "contact_permission": result.get("contact_permission"),
            },
        ):
            raise RuntimeError("A kutatás befejeződött, de a záró audit nem menthető.")
        print(json.dumps({
            "scope": result["scope"],
            "saved_count": result["saved_count"],
            "skipped_count": result["skipped_count"],
            "email_sending": result["email_sending"],
            "contact_permission": result["contact_permission"],
            "companies": result["companies"],
        }, ensure_ascii=False))
    except Exception as exc:
        if db is not None:
            audit_event(
                db,
                module="global_lead_research_job",
                action="daily_global_research",
                status="unknown" if research_started else "failed",
                operation_id=operation_id,
                error=exc,
                level="critical",
            )
        report_error(
            exc,
            module="global_lead_research_job",
            operation="run_daily_global_research",
            severity="critical",
            db=db,
        )
        raise


if __name__ == "__main__":
    main()
