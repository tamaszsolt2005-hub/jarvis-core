import json

import global_lead_research as research


class Result:
    def __init__(self, data=None):
        self.data = data or []


class Query:
    def __init__(self, db):
        self.db = db
        self.row = None

    def select(self, _columns):
        return self

    def limit(self, _limit):
        return self

    def insert(self, row):
        self.row = row
        return self

    def execute(self):
        if self.row is not None:
            self.db.inserted.append(self.row)
            return Result([self.row])
        return Result(self.db.existing)


class FakeDB:
    def __init__(self, existing=None):
        self.existing = existing or []
        self.inserted = []

    def table(self, _name):
        return Query(self)


class FakeModels:
    def __init__(self, response):
        self.response = response

    def generate_content(self, **_kwargs):
        return self.response


class FakeClient:
    def __init__(self, response):
        self.models = FakeModels(response)


def test_parse_companies_accepts_json_fence():
    parsed = research._parse_companies(' ```json\n{"companies":[{"company_name":"Acme"}]}\n``` ')
    assert parsed == [{"company_name": "Acme"}]


def test_rejects_non_http_and_local_urls():
    assert research._valid_http_url("https://example.com")
    assert research._valid_http_url("file:///etc/passwd") is None
    assert research._valid_http_url("http://localhost/admin") is None
    assert research._valid_http_url("https://user:pass@example.com") is None


def test_global_research_stores_company_only_without_contact_permission(monkeypatch):
    company = {
        "company_name": "Acme Systems",
        "website": "https://acme.example",
        "country": "Canada",
        "industry": "Manufacturing",
        "business_summary": "Industrial components",
        "potential_fit": "Could benefit from process automation",
        "business_fit_score": 128,
        "fit_evidence": ["Uses multiple production lines", "Public case study mentions manual workflows"],
        "business_need": "Potentially repetitive production workflows",
        "recommended_next_step": "Review public case studies",
        "research_confidence": "high",
        "source_url": "https://acme.example/about",
    }
    response = {
        "text": json.dumps({"companies": [company]}),
        "candidates": [{
            "grounding_metadata": {
                "grounding_chunks": [{"web": {"uri": "https://acme.example/about"}}]
            }
        }],
    }
    monkeypatch.setattr(research.types, "GenerateContentConfig", lambda **kwargs: kwargs)
    monkeypatch.setattr(research.types, "Tool", lambda **kwargs: kwargs)
    monkeypatch.setattr(research.types, "GoogleSearch", lambda: {})
    monkeypatch.setattr(research, "get_model_name", lambda: "test-model")
    monkeypatch.setattr(research, "log_event", lambda *_args, **_kwargs: None)

    db = FakeDB()
    result = research.research_global_companies(db, "globális cégek", FakeClient(response))

    assert result["saved_count"] == 1
    saved = db.inserted[0]
    assert saved["company_name"] == "Acme Systems"
    assert saved["email"] is None
    assert saved["approved_to_contact"] is False
    assert saved["consent_basis"] is None
    assert saved["status"] == "research"
    assert "AI üzleti illeszkedési becslés: 100/100" in saved["notes"]
    assert "Uses multiple production lines" in saved["notes"]
    assert result["companies"][0]["business_fit_score"] == 100
    assert result["companies"][0]["research_confidence"] == "high"
    assert result["email_sending"] == "disabled"


def test_global_research_deduplicates_existing_company(monkeypatch):
    company = {
        "company_name": "Acme Systems",
        "website": "https://acme.example",
        "source_url": "https://acme.example/about",
    }
    response = {
        "text": json.dumps({"companies": [company]}),
        "candidates": [{
            "grounding_metadata": {
                "grounding_chunks": [{"web": {"uri": "https://acme.example/about"}}]
            }
        }],
    }
    monkeypatch.setattr(research.types, "GenerateContentConfig", lambda **kwargs: kwargs)
    monkeypatch.setattr(research.types, "Tool", lambda **kwargs: kwargs)
    monkeypatch.setattr(research.types, "GoogleSearch", lambda: {})
    monkeypatch.setattr(research, "get_model_name", lambda: "test-model")
    monkeypatch.setattr(research, "log_event", lambda *_args, **_kwargs: None)

    db = FakeDB(existing=[{"company_name": "Acme Systems", "website": "https://acme.example"}])
    result = research.research_global_companies(db, "globális cégek", FakeClient(response))

    assert result["saved_count"] == 0
    assert result["skipped_count"] == 1
    assert db.inserted == []



def test_market_switch_aliases():
    assert research.detect_market_change("JARVIS, válts németre") == "Germany"
    assert research.detect_market_change("Állj át a francia piacra") == "France"
    assert research.detect_market_change("Válts vissza Magyarországra") == "Hungary"
    assert research.detect_market_change("Válts portugálra") == "Portugal"
    assert research.detect_market_change("Keress új leadeket") is None


def test_market_default_is_hungary():
    class SettingsQuery:
        def select(self, _columns):
            return self
        def eq(self, _key, _value):
            return self
        def limit(self, _limit):
            return self
        @property
        def data(self):
            return []
        def execute(self):
            return Result([])
    class SettingsDB:
        def table(self, _name):
            return SettingsQuery()
    assert research.get_research_market(SettingsDB()) == "Hungary"


def test_market_switch_persists():
    class SettingsQuery:
        def __init__(self):
            self.payload = None
        def upsert(self, payload):
            self.payload = payload
            return self
        def execute(self):
            return Result([])
    class SettingsDB:
        def __init__(self):
            self.query = SettingsQuery()
        def table(self, _name):
            return self.query
    db = SettingsDB()
    assert research.set_research_market(db, "Germany") == "Germany"
    assert db.query.payload == {"key": "lead_research_market", "value": {"country": "Germany"}}
