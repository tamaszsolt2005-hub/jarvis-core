import os
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from supabase import create_client, Client
import google.generativeai as genai

from web_auditor import audit_company_website
from lead_scoring import score_lead

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

def send_ai_outreach_emails():
    print("AI Alapú E-mail Küldő (Fejlett modulok) elindult...")
    
    try:
        response = supabase.table("leads").select("*").eq("status", "new").execute()
        leads = response.data
        
        if not leads:
            print("Nincs új, kiküldésre váró lead.")
            return

        # Leidek rendezése pontszám szerint (a legjobbakat küldjük előre)
        for lead in leads:
            lead["calculated_score"] = score_lead(lead)
        
        leads.sort(key=lambda x: x["calculated_score"], reverse=True)
        
        # Biztonságos batch limit: maximum 3 darab futásonként
        batch_leads = leads[:3]
        print(f"Ebben a körben feldolgozott top leidek száma: {len(batch_leads)}")

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)

        for lead in batch_leads:
            company_name = lead["company_name"]
            recipient_email = lead["email"]
            company_url = lead.get("website", "")

            # Webhely elemzése az egyedi érvekhez
            audit_info = audit_company_website(company_url)
            
            prompt = (
                f"Írj egy nagyon rövid, barátságos és közvetlen B2B hideg megkereső e-mailt magyarul "
                f"a '{company_name}' nevű debreceni cégnek. "
                f"Weboldal elemzés / háttér info: {audit_info}. "
                f"Ajánld fel a webfejlesztési és AI chatbot/automatizációs megoldásainkat. "
                f"Ne használj helyőrzőket, hanem írd alá közvetlenül Tomként (Vantrox / SoftScale). "
                f"Legyen természetes és modern hangvételű."
            )
            
            ai_response = model.generate_content(prompt)
            email_body = ai_response.text

            msg = MIMEMultipart()
            msg["From"] = EMAIL_USER
            msg["To"] = recipient_email
            msg["Subject"] = f"Fejlesztési ötlet a(z) {company_name} online rendszeréhez"
            msg.attach(MIMEText(email_body, "plain", "utf-8"))

            server.sendmail(EMAIL_USER, recipient_email, msg.as_string())
            print(f"Személyre szabott e-mail elküldve ide: {recipient_email} ({company_name})")

            # Státusz frissítése és pontszám mentése
            supabase.table("leads").update({
                "status": "sent",
                "score": lead["calculated_score"]
            }).eq("id", lead["id"]).execute()

            supabase.table("logs").insert({
                "module": "advanced_email_sender", 
                "message": f"Személyre szabott levél elküldve: {company_name} (Pontszám: {lead['calculated_score']})"
            }).execute()

            print("Várakozás a következő levél előtt...")
            time.sleep(30)

        server.quit()
        print("A batch küldés sikeresen lefutott.")

    except Exception as e:
        print(f"Hiba történt az e-mailek küldése során: {e}")

if __name__ == "__main__":
    send_ai_outreach_emails()
