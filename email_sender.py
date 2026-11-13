import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from supabase import create_client, Client

# Supabase adatok behúzása a GitHub Secrets-ből
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# Email beállítások a GitHub Secrets-ből
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

def send_outreach_emails():
    print("E-mail küldő modul elindult...")
    
    try:
        # 1. Lekérdezzük azokat a leideket, akiknek a státusza 'new'
        response = supabase.table("leads").select("*").eq("status", "new").execute()
        leads = response.data
        
        if not leads:
            print("Nincs új, kiküldésre váró lead.")
            return

        print(f"Talált új leidek száma: {len(leads)}")

        # 2. Csatlakozunk az SMTP szerverhez (pl. Gmail App Password használatával)
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)

        sent_count = 0
        for lead in leads:
            company_name = lead["company_name"]
            recipient_email = lead["email"]
            
            # Üzenet összeállítása
            msg = MIMEMultipart()
            msg["From"] = EMAIL_USER
            msg["To"] = recipient_email
            msg["Subject"] = f"Együttműködési ajánlat - {company_name}"
            
            body = f"""Üdvözlöm a {company_name} csapatát!

A nevem Tom, és egyedi webfejlesztéssel, valamint AI-alapú rendszerek (chatbotok, automatizációk) építésével foglalkozom. 
Észrevettem, hogy a debreceni piacon kiváló cukrászdát visznek, és tudnék segíteni a digitális jelenlétük erősítésében, valamint a rendelések kezelésének automatizálásában.

Ha érdekli egy kötetlen egyeztetés arról, hogyan tudnánk növelni az online láthatóságot, válaszoljon erre az e-mailre.

Üdvözlettel,
Tom
Vantrox / SoftScale
"""
            msg.attach(MIMEText(body, "plain", "utf-8"))

            # 3. E-mail küldés
            server.sendmail(EMAIL_USER, recipient_email, msg.as_string())
            print(f"E-mail elküldve ide: {recipient_email} ({company_name})")

            # 4. Státusz frissítése 'sent'-re, hogy SOHA ne kapja meg kétszer
            supabase.table("leads").update({"status": "sent"}).eq("id", lead["id"]).execute()

            # Naplózás a logs táblába
            supabase.table("logs").insert({
                "module": "email_sender", 
                "message": f"Ajánlat elküldve: {company_name} ({recipient_email})"
            }).execute()

            sent_count += 1

        server.quit()
        print(f"E-mail küldés kész. Sikeresen elküldve: {sent_count} db.")

    except Exception as e:
        print(f"Hiba történt az e-mailek küldése során: {e}")

if __name__ == "__main__":
    send_outreach_emails()
