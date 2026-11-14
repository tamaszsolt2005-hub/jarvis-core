"""Import manually reviewed CSV records; never invent prospect identities."""
from __future__ import annotations
import csv,re
from datetime import datetime
from jarvis_common import get_supabase,log_event
EMAIL_RE=re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
def _truth(value): return str(value).strip().lower() in {"true","1","yes","igen"}
def run(path="data/leads.csv"):
    db=get_supabase(); imported=skipped=0
    with open(path,newline="",encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            company=(row.get("company_name") or "").strip()
            address=(row.get("email") or "").strip().lower()
            basis=(row.get("consent_basis") or "").strip().lower()
            approved=_truth(row.get("approved_to_contact",""))
            confirmed=(row.get("consent_confirmed_at") or "").strip()
            try: datetime.fromisoformat(confirmed.replace("Z","+00:00")); valid_time=True
            except ValueError: valid_time=False
            if not company or not EMAIL_RE.fullmatch(address) or basis!="consent" or not approved or not valid_time:
                skipped+=1; continue
            exists=db.table("leads").select("id").eq("email",address).limit(1).execute().data
            if exists: skipped+=1; continue
            db.table("leads").insert({"company_name":company,"email":address,"website":(row.get("website") or "").strip(),
                "notes":(row.get("notes") or "").strip(),"source":(row.get("source") or "reviewed_csv").strip(),
                "consent_basis":"consent","approved_to_contact":True,"consent_confirmed_at":confirmed,
                "opted_out":False,"status":"new"}).execute()
            imported+=1
    log_event(db,"lead_gen",f"CSV import: {imported} új lead, {skipped} kihagyva.")
    print(f"Import kész: {imported} új, {skipped} kihagyott rekord.")
if __name__=="__main__": run()
