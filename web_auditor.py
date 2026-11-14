import requests
from bs4 import BeautifulSoup

def audit_company_website(url):
    """Megvizsgálja a célpont weboldalát, és visszatér egy rövid elemzéssel a Gemini számára."""
    if not url or not url.startswith("http"):
        return "Standard webes jelenlét."
    
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200:
            return "A weboldal nehezen tölthető be vagy hiányos."
        
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.title.string if soup.title else "Nincs megadva cím"
        text_sample = ' '.join([p.text for p in soup.find_all('p')[:3]])
        
        return f"Weboldal címe: {title}. Tartalom minta: {text_sample[:250]}..."
    except Exception as e:
        return "Nem sikerült elemezni a weboldalt (lehet, hogy védett vagy offline)."
