"""Read recent Gmail replies, classify them and stop future outreach."""
from __future__ import annotations
import email,imaplib
from email.header import decode_header
from email.utils import parseaddr
from jarvis_common import get_secret,get_supabase,log_event
from reply_analyzer import classify_reply

def _decode(value):
    if not value: return ""
    out=[]
    for part,enc in decode_header(value):
        out.append(part.decode(enc or "utf-8",errors="replace") if isinstance(part,bytes) else part)
    return " ".join(out)

def _body(msg):
    chunks=[]
    for part in msg.walk() if msg.is_multipart() else [msg]:
        if part.get_content_type()=="text/plain" and part.get_content_disposition()!="attachment":
            payload=part.get_payload(decode=True)
            if payload: chunks.append(payload.decode(part.get_content_charset() or "utf-8",errors="replace"))
    return "\n".join(chunks)[:10000]

def run():
    user,password=get_secret("EMAIL_USER"),get_secret("EMAIL_PASSWORD")
    if not user or not password:
        print("Inbox monitor kihagyva: hiányzik az EMAIL_USER vagy EMAIL_PASSWORD."); return
    db=get_supabase()
    leads=db.table("leads").select("*").in_("status",["sent","followed_up"]).limit(300).execute().data or []
    mail=imaplib.IMAP4_SSL(get_secret("IMAP_HOST","imap.gmail.com"),int(get_secret("IMAP_PORT","993")))
    try:
        mail.login(user,password); mail.select("INBOX")
        for lead in leads:
            address=str(lead.get("email") or "").replace('"',"")
            if not address: continue
            status,data=mail.search(None,"FROM",f'"{address}"')
            if status!="OK" or not data or not data[0]: continue
            for msg_id in data[0].split()[-5:]:
                status,raw=mail.fetch(msg_id,"(RFC822)")
                if status!="OK" or not raw or not isinstance(raw[0],tuple): continue
                msg=email.message_from_bytes(raw[0][1])
                mid=msg.get("Message-ID")
                if mid and mid==lead.get("last_inbound_message_id"): continue
                if parseaddr(msg.get("From",""))[1].lower()!=address.lower(): continue
                category=classify_reply(_body(msg))
                db.table("leads").update({"status":"opted_out" if category=="opt_out" else "replied",
                    "reply_category":category,"last_inbound_message_id":mid,
                    "opted_out":category=="opt_out","next_follow_up_at":None}).eq("id",lead["id"]).execute()
                log_event(db,"inbox_monitor",f"Válasz feldolgozva ({category}): {lead.get('company_name')}")
                break
    finally:
        try: mail.logout()
        except Exception: pass

if __name__=="__main__": run()
