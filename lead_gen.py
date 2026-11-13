import os
from supabase import create_client, Client

# Supabase adatok behúzása a GitHub Secrets-ből
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(url, key)

def run_debrecen_confectionery_scraper():
    print("Debreceni cukrászda kereső és lead-gyűjtő elindult...")
    
    # Célzott adatok: Debreceni cukrászdák listája (a rendszer ezen megy végig)
    target_leads = [
        {"company_name": "Mandula Cukrászda Debrecen", "email": "info@mandulacukraszda.hu", "status": "new"},
        {"company_name": "Darabos Cukrászda", "email": "kapcsolat@daraboscukraszda.hu", "status": "new"},
        {"company_name": "Koriander Cukrászda", "email": "rendeles@koriandercukraszda.hu", "status": "new"},
        {"company_name": "Giga Cukrászda", "email": "info@gigacukraszda.hu", "status": "new"},
        {"company_name": "Sütipont Debrecen", "email": "kapcsolat@sutipontdebrecen.hu", "status": "new"}
    ]
    
    added_count = 0
    skipped_count = 0

    for lead in target_leads:
        try:
            # 1. SZIGORÚ DUPLIKÁCIÓSZŰRÉS: Megnézzük, létezik-e már a cégnév a Supabase-ben
            existing = supabase.table("leads").select("*").eq("company_name", lead["company_name"]).execute()
            
            # 2. Ha a lekérdezés üres (azaz még NINCS benn az adatbázisban)
            if not existing.data:
                supabase.table("leads").insert(lead).execute()
                print(f"Új debreceni cukrászda mentve: {lead['company_name']} ({lead['email']})")
                
                # Sikeres mentés naplózása a logs táblába
                supabase.table("logs").insert({
                    "module": "lead_gen_debrecen", 
                    "message": f"Sikeresen mentve: {lead['company_name']}"
                }).execute()
                
                added_count += 1
            else:
                # Ha már benne van, kihagyjuk, így elkerüljük a duplikációt
                print(f"Már létezik az adatbázisban, kihagyva: {lead['company_name']}")
                skipped_count += 1
                
        except Exception as e:
            print(f"Hiba történt a feldolgozás során ({lead['company_name']}): {e}")
            
    print(f"Futtatás kész. Új hozzáadva: {added_count}, Duplikátum miatt kihagyva: {skipped_count}")

if __name__ == "__main__":
    run_debrecen_confectionery_scraper()
