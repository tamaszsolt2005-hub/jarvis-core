import os
from supabase import create_client, Client

# Adatok behúzása a környezeti változókból / GitHub Secrets-ből
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def print_jarvis_status():
    """Lekéri és emberi/AI által olvasható formába önti a Jarvis rendszer statisztikáit."""
    print("📊 Jarvis Rendszerstatisztika & Elemzés lekérése...\n")
    
    try:
        # Leidek lekérése
        leads_res = supabase.table("leads").select("*").execute()
        leads = leads_res.data if leads_res.data else []
        
        # Utolsó naplók lekérése
        logs_res = supabase.table("logs").select("*").order("created_at", desc=True).limit(5).execute()
        logs = logs_res.data if logs_res.data else []
        
        total_leads = len(leads)
        new_count = sum(1 for l in leads if l.get("status") == "new")
        sent_count = sum(1 for l in leads if l.get("status") == "sent")
        interested_count = sum(1 for l in leads if l.get("status") == "interested")
        conversion_rate = round((interested_count / sent_count * 100), 1) if sent_count > 0 else 0.0
        
        print("=== 🛡️ JARVIS B2B MOTOR JELENTÉS ===")
        print(f"• Összes regisztrált lead: {total_leads}")
        print(f"• Várakozó (new): {new_count}")
        print(f"• Kiküldött ajánlat (sent): {sent_count}")
        print(f"• Pozitív válasz (interested): {interested_count}")
        print(f"• Becsült konverziós arány: {conversion_rate}%\n")
        
        print("=== 📜 LEGFRISSEBB RENDSZERLOGOK ===")
        if logs:
            for log in logs:
                print(f"[{log.get('created_at')}] ({log.get('module')}): {log.get('message')}")
        else:
            print("Nincsenek még logbejegyzések.")
            
    except Exception as e:
        print(f"Hiba történt a statisztikák lekérése közben: {e}")

if __name__ == "__main__":
    print_jarvis_status()
