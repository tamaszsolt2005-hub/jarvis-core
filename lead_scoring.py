def score_lead(lead):
    """Pontozza a leidet 1 és 100 közötti skálán a konverziós esély alapján."""
    score = 50  # Alap pontszám
    
    email = lead.get("email", "")
    website = lead.get("website", "")
    company_name = lead.get("company_name", "")
    
    # Hivatalos céges domain előnyben részesítése
    if email and "@gmail.com" not in email and "@freemail.hu" not in email and "@index.hu" not in email:
        score += 30
        
    # Ha van weboldala
    if website and website.startswith("http"):
        score += 20
        
    # Ha van név
    if company_name:
        score += 10
        
    return min(score, 100)
