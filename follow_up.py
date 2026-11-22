"""One due follow-up maximum per lead; stop after any reply or opt-out."""
from __future__ import annotations
import time
from datetime import datetime,timezone
from email_utils import EMAIL_DELIVERY_ENABLED, send_email
from jarvis_common import env_bool,env_int,generate_text,get_supabase,log_event
from jarvis_errors import report_error

def _run() -> None:
    if not EMAIL_DELIVERY_ENABLED or not env_bool("AUTO_SEND_ENABLED",False):
        print("Biztonsági mód: AUTO_SEND_ENABLED nem true, follow-up nem kerül kiküldésre."); return
    db=get_supabase(); now=datetime.now(timezone.utc)
    rows=db.table("leads").select("*").eq("status","sent").limit(100).execute().data or []
    due=[]
    for lead in rows:
        if lead.get("opted_out") or lead.get("reply_category"): continue
        try: due_at=datetime.fromisoformat(str(lead.get("next_follow_up_at")).replace("Z","+00:00"))
        except (TypeError,ValueError): continue
        try:
            follow_up_count = int(lead.get("follow_up_count") or 0)
        except (TypeError, ValueError):
            continue
        if due_at<=now and follow_up_count<1: due.append(lead)
    for lead in due[:env_int("FOLLOW_UP_MAX_PER_RUN",3,1,10)]:
        try:
            body=generate_text("Írj rövid, udvarias, nem sürgető magyar utánkövető e-mailt. Ne találj ki tényt; legyen benne leiratkozási lehetőség. Cég: "+str(lead.get("company_name")))[:4500]
            claim=db.table("leads").update({"status":"followup_sending"}).eq("id",lead["id"]).eq("status","sent").select("id").execute()
            if not claim.data: continue
            send_email(lead["email"],"Rövid visszajelzéskérés",body)
            db.table("leads").update({"status":"followed_up","follow_up_count":1,"followed_up_at":now.isoformat(),"next_follow_up_at":None}).eq("id",lead["id"]).execute()
            log_event(db,"follow_up",f"Follow-up elküldve: {lead.get('company_name')}")
            time.sleep(env_int("SEND_DELAY_SECONDS",30,10,600))
        except Exception as exc:
            report_error(
                exc,
                module="follow_up",
                operation="send_follow_up",
                severity="error",
                db=db,
            )
            try:
                db.table("leads").update({"status":"sent"}).eq("id",lead["id"]).eq("status","followup_sending").execute()
            except Exception as recovery_exc:
                report_error(
                    recovery_exc,
                    module="follow_up",
                    operation="restore_lead_after_follow_up_failure",
                    severity="critical",
                    db=db,
                )


def run() -> None:
    """Run follow-ups and centrally report failures outside per-lead handling."""
    try:
        _run()
    except Exception as exc:
        report_error(
            exc,
            module="follow_up",
            operation="run_follow_up_batch",
            severity="critical",
        )
        raise


if __name__=="__main__": run()
