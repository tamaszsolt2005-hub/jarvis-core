import os
import smtplib
import time
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from supabase import create_client, Client
import google.generativeai as genai

# Adatok behúzása a GitHub Secrets-ből
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Gemini AI beállítása
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

def send_follow_up_emails():
    print("Follow-up (Utánkövető) modul elindult...")
    
    try:
        # 1. Lekérdezzük azokat a leideket, akiknek a státusza 'sent' (azaz kaptak első levelet, de még nem voltak követve)
        response = supabase.table("leads").select("*").eq("status", "sent").execute()
        leads = response.data
        
        if not leads:
            print("Nincs követésre váró lead.")
            return

        print(f"Talált leidek follow-up küldéshez: {len(leads)}")

        # 2. SMTP kapcsolat
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)

        for lead in leads:
            company_name = lead["company_name"]
            recipient_email = lead["email"]
            
            # 3. Gemini AI emlékeztető levél generálása (Anti-spam: természetes, emberi hangvétel)
            prompt = (
                f"Írj egy nagyon rövid, barátságos, nem tolakodó follow-up (emlékeztető) e-mailt magyarul "
                f"a '{company_name}' nevű debreceni cukrászdának. "
                f"Említsd meg, hogy csak érdeklődsz, megkapták-e az előző üzenetet a webfejlesztési és AI automatizációs ajánlatunkkal kapcsolatban. "
                f"Aláírás: Tom (Vantrox / SoftScale). Kerüld a spames kulcsszavakat, legyen modern és természetes."
            )
            
            ai_response = model.generate_content(prompt)
            email_body = ai_response.text

            msg = MIMEMultipart()
            msg["From"] = EMAIL_USER
            msg["To"] = recipient_email
            msg["Subject"] = f"Re: Együttműködési ajánlat - {company_name}"
            msg.attach(MIMEText(email_body, "plain", "utf-8"))

            # 4. Küldés
            server.sendmail(EMAIL_USER, recipient_email, msg.as_string())
            print(f"Follow-up e-mail elküldve ide: {recipient_email} ({company_name})")

            # 5. Státusz frissítése 'followed_up'-ra (Biztosítja, hogy soha ne kapja meg kétszer)
            supabase.table("leads").update({"status": "followed_up"}).eq("id", lead["id"]).execute()

            # Naplózás
            supabase.table("logs").insert({
                "module": "follow_up_sender", 
                "message": f"Follow-up levél elküldve és rögzítve: {company_name}"
            }).execute()

            # 6. ANTI-SPAM VÉDELEM: Véletlenszerű késleltetés (5-10 másodperc), hogy emberi tempónak tűnjön
            sleep_time = random.randint(5, 10)
            print(f"Anti-spam várakozás: {sleep_time} másodperc...")
            time.sleep(sleep_time)

        server.quit()
        print("Az összes follow-up e-mail sikeresen elküldve.")

    except Exception as e:
        print(f"Hiba történt a follow-up e-mailek küldése során: {e}")

if __name__ == "__main__":
    send_follow_up_emails()
