import os
import smtplib
import time
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

# Gemini AI konfigurálása
genai.configure(api_key=GEMINI_API_KEY)
# A leggyorsabb és leghatékonyabb modell használata szöveggeneráláshoz
model = genai.GenerativeModel('gemini-2.5-flash')

def send_ai_outreach_emails():
    print("AI Alapú E-mail Küldő (Gemini) modul elindult...")
    
    try:
        # 1. Új leidek lekérdezése az adatbázisból
        response = supabase.table("leads").select("*").eq("status", "new").execute()
        leads = response.data
        
        if not leads:
            print("Nincs új, kiküldésre váró lead.")
            return

        print(f"Talált új leidek száma (Gemini személyre szabással): {len(leads)}")

        # 2. SMTP kapcsolat a levelezéshez
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)

        for lead in leads:
            company_name = lead["company_name"]
            recipient_email = lead["email"]
            
            # 3. Gemini AI felkérése egyedi levél írására
            prompt = (
                f"Írj egy rövid, barátságos, de professzionális B2B hideg megkereső e-mailt magyarul "
                f"a '{company_name}' nevű debreceni cukrászdának. "
                f"Ajánld fel a webfejlesztési és AI chatbot/automatizációs szolgáltatásainkat, amelyek növelik az online rendeléseiket. "
                f"Ne használj helyőrzőket (mint [Neved]), hanem írd alá közvetlenül Tomként (Vantrox / SoftScale). "
                f"Legyen lényegretörő és modern."
            )
            
            ai_response = model.generate_content(prompt)
            email_body = ai_response.text

            # Levél összeállítása
            msg = MIMEMultipart()
            msg["From"] = EMAIL_USER
            msg["To"] = recipient_email
            msg["Subject"] = f"Együttműködési ajánlat - {company_name}"
            msg.attach(MIMEText(email_body, "plain", "utf-8"))

            # 4. Küldés
            server.sendmail(EMAIL_USER, recipient_email, msg.as_string())
            print(f"Gemini által írt e-mail elküldve ide: {recipient_email} ({company_name})")

            # 5. Státusz frissítése 'sent'-re (dupla küldés gátló)
            supabase.table("leads").update({"status": "sent"}).eq("id", lead["id"]).execute()

            # Naplózás
            supabase.table("logs").insert({
                "module": "gemini_email_sender", 
                "message": f"Gemini levél kiküldve és rögzítve: {company_name}"
            }).execute()

            # Biztonsági késleltetés a spamfilterek elkerülésére
            time.sleep(2)

        server.quit()
        print("Az összes Gemini által generált e-mail sikeresen elküldve.")

    except Exception as e:
        print(f"Hiba történt az AI e-mailek küldése során: {e}")

if __name__ == "__main__":
    send_ai_outreach_emails()
