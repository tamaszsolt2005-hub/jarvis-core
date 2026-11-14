from lead_scoring import score_lead

def test_score_is_bounded():
    assert 1 <= score_lead({}) <= 100

def test_company_domain_scores_higher_than_free_email():
    company = {"company_name":"Példa Kft.","email":"hello@pelda.hu","website":"https://pelda.hu","notes":"Részletes ellenőrzött megjegyzés","source":"manual"}
    free = {"company_name":"Példa Kft.","email":"hello@gmail.com"}
    assert score_lead(company) > score_lead(free)
