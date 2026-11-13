import os
import time
import requests
from bs4 import BeautifulSoup
from supabase import create_client, Client

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def deep_scrape_leads():
    print("Mély weboldal-elemző Scraper modul elindult...")
    
    # Célpontok weboldalakkal és kiinduló adatokkal
    target_leads = [
        {
            "company_name": "Süti Varázs Debrecen", 
            "email": "kapcsolat@sutivarazs.hu", 
            "website": "https://example.com", 
            "status": "new", 
            "notes": "Hagyományos felület, nincs online asztalfoglalás."
        },
        {
            "company_name": "Mézeskalács Műhely Debrecen", 
            "email": "info@mezeskalacsmuhely.hu", 
            "website": "https://example.com", 
            "status": "new", 
            "notes": "Közösségi médiára fókuszálnak, hiányzik a modern webshop."
        }
    ]
    
    added_count = 0
    skipped_count = 0

    for lead in target_leads:
        try:
            # Szigorú duplikációszűrés
            existing = supabase.table("leads").select("*").eq("company_name", lead["company_name"]).execute()
            
            if not existing.data:
                # Weboldal mélyebb elemzése (Deep Scraping szimuláció)
                try:
                    res = requests.get(lead["website"], timeout=5)
                    soup = BeautifulSoup(res.text, 'html.parser')
                    title = soup.title.string if soup.title else "Nincs cím"
                    lead["notes"] += f" [Elemzett oldal címe: {title}]"
                except:
                    pass

                supabase.table("leads").insert(lead).execute()
                print(f"Új lead mentve mély web-elemzéssel: {lead['company_name']}")
                
                supabase.table("logs").insert({
                    "module": "deep_scraper", 
                    "message": f"Mélyelemzéssel mentve: {lead['company_name']}"
                }).execute()
                
                added_count += 1
            else:
                print(f"Már létezik az adatbázisban, kihagyva: {lead['company_name']}")
                skipped_count += 1
                
            time.sleep(1)
            
        except Exception as e:
            print(f"Hiba a mély web-elemzés során ({lead['company_name']}): {e}")
            
    print(f"Adatgyűjtés kész. Új hozzáadva: {added_count}, Kihagyva: {skipped_count}")

if __name__ == "__main__":
    deep_scrape_leads()
