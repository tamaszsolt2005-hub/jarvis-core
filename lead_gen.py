import os
import random
from supabase import create_client, Client

# Supabase adatok behúzása a GitHub Secrets-ből
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(url, key)

def run_lead_generator():
    print("Lead-gyűjtő modul elindult...")
    
    # Példa cégek, amiket a háttérben gyűjthet a rendszer 
    # (Ezt majd később kiegészítjük Google Térkép vagy webes scraper logikával is)
    sample_leads = [
        {"company_name": "Építő Depot Kft.", "email": "kapcsolat@epitodepot.hu", "status": "new"},
        {"company_name": "Tüzép & Bau Bt.", "email": "info@tuzepbau.hu", "status": "new"},
        {"company_name": "Alpha Construct Kft.", "email": "iroda@alphaconstruct.hu", "status": "new"}
    ]
    
    added_count = 0
    for lead in sample_leads:
        try:
            # Megnézzük, hogy létezik-e már az adatbázisban ezzel a névvel
            existing = supabase.table("leads").select("*").eq("company_name", lead["company_name"]).execute()
            
            if not existing.data:
                # Ha még nincs benn, berakjuk az adatbázisba
                supabase.table("leads").insert(lead).execute()
                print(logger_msg := f"Új lead mentve: {lead['company_name']} ({lead['email']})")
                
                # Naplózzuk is a system logok közé
                supabase.table("logs").insert({
                    "module": "lead_gen", 
                    "message": f"Sikeresen mentve: {lead['company_name']}"
                }).execute()
                
                added_count += 1
            else:
                print(f"Már létezik a adatok között: {lead['company_name']}")
        except Exception as e:
            print(f"Hiba történt a lead rögzítésekor ({lead['company_name']}): {e}")
            
    print(f"Lead-gyűjtő lefutott. Új hozzáadott leidek száma: {added_count}")

if __name__ == "__main__":
    run_lead_generator()
