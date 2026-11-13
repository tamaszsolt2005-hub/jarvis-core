import os
import imaplib
from supabase import create_client, Client

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

def check_inbox_replies():
    print("Inbox Monitor (Válasz-figyelő) modul elindult...")
    try:
        # Csatlakozás az IMAP szerverhez (Gmail)
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(EMAIL_USER, EMAIL_PASSWORD)
        mail.select("inbox")

        # Aktív, megkeresett leidek lekérdezése
        response = supabase.table("leads").select("*").in_("status", ["sent", "followed_up"]).execute()
        active_leads = response.data

        if not active_leads:
            print("Nincs figyelt lead a postaládában.")
            mail.logout()
            return

        for lead in active_leads:
            sender_email = lead["email"]
            # Keresés az e-mail cím alapján a bejövők között
            status, messages = mail.search(None, f'(FROM "{sender_email}")')
            
            if status == "OK" and messages[0]:
                print(f"Válasz érkezett ettől a leidtől: {sender_email} ({lead['company_name']})!")
                
                # Státusz frissítése 'replied'-ra (megállítja a további follow-upokat)
                supabase.table("leads").update({"status": "replied"}).eq("id", lead["id"]).execute()
                
                supabase.table("logs").insert({
                    "module": "inbox_monitor",
                    "message": f"Válasz érkezett, státusz frissítve 'replied'-ra: {lead['company_name']}"
                }).execute()

        mail.logout()
        print("Inbox monitor futás sikeresen lefutott.")
    except Exception as e:
        print(f"Hiba az inbox monitorban: {e}")

if __name__ == "__main__":
    check_inbox_replies()
