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
model = genai.GenerativeModel('gemini-2.5-flash')

def send_ai_outreach_emails():
    print("AI Alapú E-mail Küldő (Gemini) modul elindult...")
    
    try:
        # 1. Új leidek lekérdezése - MAXIMUM 3 DARAB futásonként a spam elkerülése érdekében!
        response = supabase.table("leads").select("*").eq("status", "new").limit(3).execute()
        leads = response.data
        
        if not leads:
            print("Nincs új, kiküldésre váró lead.")
            return

        print(f"Ebben a körben feldolgozott leidek száma (Biztonságos batch): {len(leads)}")

        # 2. SMTP kapcsolat a levelezéshez
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)

        for lead in leads:
            company_name = lead["company_name"]
            recipient_email = lead["email"]
            
            # 3. Gemini AI felkérése egyedi levél írására változatosabb prompttal
            prompt = (
                f"Írj egy nagyon rövid, barátságos és közvetlen B2B hideg megkereső e-mailt magyarul "
                f"a '{company_name}' nevű debreceni cégnek. "
                f"Említsd meg, hogy észrevettétek őket online, és ajánld fel a webfejlesztési és AI automatizációs megoldásainkat. "
                f"Ne használj helyőrzőket (mint [Neved]), hanem írd alá közvetlenül Tomként (Vantrox / SoftScale). "
                f"Legyen természetes hangvételű, semmiképpen ne hasson sablonosnak."
            )
            
            ai_response = model.generate_content(prompt)
            email_body = ai_response.text

            # Levél összeállítása
            msg = MIMEMultipart()
            msg["From"] = EMAIL_USER
            msg["To"] = recipient_email
            msg["Subject"] = f"Kérdés a(z) {company_name} online jelenlétével kapcsolatban"
            msg.attach(MIMEText(email_body, "plain", "utf-8"))

            # 4. Küldés
            server.sendmail(EMAIL_USER, recipient_email, msg.as_string())
            print(f"Gemini által írt e-mail elküldve ide: {recipient_email} ({company_name})")

            # 5. Státusz frissítése 'sent'-re
            supabase.table("leads").update({"status": "sent"}).eq("id", lead["id"]).execute()

            # Naplózás
            supabase.table("logs").insert({
                "module": "gemini_email_sender", 
                "message": f"Gemini levél kiküldve: {company_name}"
            }).execute()

            # Biztonsági késleltetés a levelek között (30 másodperc szünet két levél közt)
            print("Várakozás a következő levél előtt...")
            time.sleep(30)

        server.quit()
        print("A jelenlegi batch e-mailek sikeresen elküldve.")

    except Exception as e:
        print(f"Hiba történt az AI e-mailek küldése során: {e}")

if __name__ == "__main__":
    send_ai_outreach_emails()
