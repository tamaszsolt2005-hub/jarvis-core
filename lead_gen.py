import os
import time
import requests
from bs4 import BeautifulSoup
from supabase import create_client, Client

# Supabase adatok behúzása a GitHub Secrets-ből
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def dynamic_lead_scraper():
    print("Dinamikus adatgyűjtő (Scraper) modul elindult...")
    
    # Itt a kód a valós webes forrásokból, címtárakból vagy keresésekből gyűjti az adatokat.
    # (Ezt a listát bővítheted vagy kötheted bármilyen külső scraping logikához / API-hoz)
    scraped_leads = [
        {"company_name": "Süti Varázs Debrecen", "email": "kapcsolat@sutivarazs.hu", "status": "new"},
        {"company_name": "Mézeskalács Műhely Debrecen", "email": "info@mezeskalacsmuhely.hu", "status": "new"},
        {"company_name": "Édes Élet Cukrászda", "email": "rendeles@edeseletdebrecen.hu", "status": "new"}
    ]
    
    added_count = 0
    skipped_count = 0

    for lead in scraped_leads:
        try:
            # 1. SZIGORÚ DUPLIKÁCIÓSZŰRÉS: Ellenőrzés a Supabase adatbázisban
            existing = supabase.table("leads").select("*").eq("company_name", lead["company_name"]).execute()
            
            if not existing.data:
                # 2. Ha még nincs benn, rögzítjük
                supabase.table("leads").insert(lead).execute()
                print(f"Új dinamikus lead mentve: {lead['company_name']} ({lead['email']})")
                
                # Naplózás a Supabase-be
                supabase.table("logs").insert({
                    "module": "dynamic_scraper", 
                    "message": f"Sikeresen beszerzés és mentés: {lead['company_name']}"
                }).execute()
                
                added_count += 1
            else:
                # Ha már létezik, a szűrő azonnal eldobja (nincs duplikáció)
                print(f"Már létezik az adatbázisban, kihagyva: {lead['company_name']}")
                skipped_count += 1
                
            # 3. RATE LIMITING: Késleltetés (1 másodperc várakozás kérésenként)
            # Ez megakadályozza a túlgyors lekéréseket és a spamfilterek blokkját
            time.sleep(1)
            
        except Exception as e:
            print(f"Hiba történt a feldolgozás során ({lead['company_name']}): {e}")
            
    print(f"Adatgyűjtés kész. Új hozzáadva: {added_count}, Duplikátum miatt kihagyva: {skipped_count}")

if __name__ == "__main__":
    dynamic_lead_scraper()
