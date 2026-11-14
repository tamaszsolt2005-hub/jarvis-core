"""Send first-contact emails only for reviewed, timestamp-consented records."""
from __future__ import annotations
import re, time
from datetime import datetime, timedelta, timezone
from email_utils import send_email
from jarvis_common import env_bool, env_int, generate_text, get_secret, get_supabase, log_event
from lead_scoring import score_lead
from web_auditor import audit_company_website

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

def _valid_consent(lead: dict) -> bool:
    if lead.get("consent_basis") != "consent" or lead.get("approved_to_contact") is not True or lead.get("opted_out") is True:
        return False
    try:
        datetime.fromisoformat(str(lead.get("consent_confirmed_at")).replace("Z","+00:00"))
        return True
    except (TypeError,ValueError):
        return False

def _draft(lead: dict) -> tuple[str,str]:
    audit = audit_company_website(lead.get("website"))
    prompt = ("Írj rövid, tényszerű, magyar B2B bemutatkozó e-mailt. Ne találj ki tényeket. "
              "Legyen udvarias, átlátható, és tartalmazzon egyszerű leiratkozási lehetőséget. "
              f"Cég: {lead.get('company_name')}\nWeboldal audit: {audit}\n"
              f"Ajánlatunk: {get_secret('OFFER_DESCRIPTION','üzleti automatizációs megoldás')}")
    text = generate_text(prompt)
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    subject = lines[0].removeprefix("Tárgy:").strip()[:180] if lines else "Rövid szakmai bemutatkozás"
    body = "\n".join(lines[1:])[:5000] if len(lines)>1 else text[:5000]
    return subject,body

def run() -> None:
    if not env_bool("AUTO_SEND_ENABLED",False):
        print("Biztonsági mód: AUTO_SEND_ENABLED nem true, e-mail nem kerül kiküldésre."); return
    db=get_supabase()
    rows=db.table("leads").select("*").eq("status","new").limit(100).execute().data or []
    eligible=[x for x in rows if _valid_consent(x) and EMAIL_RE.fullmatch(str(x.get("email") or ""))]
    eligible.sort(key=score_lead,reverse=True)
    for lead in eligible[:env_int("SEND_MAX_PER_RUN",3,1,10)]:
        try:
            subject,body=_draft(lead)
            claim=db.table("leads").update({"status":"sending"}).eq("id",lead["id"]).eq("status","new").select("id").execute()
            if not claim.data: continue
            msgid=send_email(lead["email"],subject,body)
            now=datetime.now(timezone.utc)
            db.table("leads").update({"status":"sent","first_sent_at":now.isoformat(),
                "next_follow_up_at":(now+timedelta(days=env_int("FOLLOW_UP_DAYS",5,2,30))).isoformat(),
                "last_message_id":msgid}).eq("id",lead["id"]).execute()
            log_event(db,"email_sender",f"Első levél elküldve: {lead.get('company_name')}")
            time.sleep(env_int("SEND_DELAY_SECONDS",30,10,600))
        except Exception as exc:
            log_event(db,"email_sender",f"Küldési hiba ({lead.get('company_name')}): {type(exc).__name__}","error")
            try: db.table("leads").update({"status":"send_error"}).eq("id",lead["id"]).eq("status","sending").execute()
            except Exception: pass

if __name__=="__main__": run()
