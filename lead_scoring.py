def score_lead(lead):
    """Pontozza a leidet 1 és 100 közötti skálán a konverziós esély alapján."""
    score = 50   Alap pontszám
    
    company_name = lead.get("company_name", "")
    email = lead.get("email", "")
    
    # Ha van hivatalos céges domain (nem gmail/citromail)
    if email and "@gmail.com" not in email and "@freemail.hu" not in email:
        score += 30
        
    # Ha van weboldal / domain a lead adatai között
    if lead.get("website"):
        score += 20
        
    return min(score, 100)
