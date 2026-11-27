import json

import global_lead_research as research


class Result:
    def __init__(self, data=None):
        self.data = data or []


class Query:
    def __init__(self, db):
        self.db = db
        self.row = None
        self.update_payload = None
        self.filters = {}
        self.selected_columns = None
        self.start = 0
        self.end = None

    def select(self, columns):
        self.selected_columns = columns
        return self

    def limit(self, _limit):
        return self

    def order(self, _column):
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        return self

    def insert(self, row):
        self.row = row
        return self

    def update(self, payload):
        self.update_payload = payload
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def execute(self):
        if self.update_payload is not None:
            self.db.updated.append({"payload": self.update_payload, "filters": self.filters})
            return Result([])
        if self.row is not None:
            self.db.inserted.append(self.row)
            if self.db.lose_insert_response or self.selected_columns != "id":
                return Result([])
            return Result([{"id": "inserted-lead-id"}])
        rows = self.db.existing[self.start:self.end + 1] if self.end is not None else self.db.existing
        return Result(rows)


class FakeDB:
    def __init__(self, existing=None, lose_insert_response=False):
        self.existing = existing or []
        self.inserted = []
        self.updated = []
        self.lose_insert_response = lose_insert_response

    def table(self, _name):
        return Query(self)

    def rpc(self, _name, params):
        db = self

        class RPCQuery:
            def execute(self):
                row = {
                    "company_name": params["p_company_name"],
                    "email": params["p_email"],
                    "website": params["p_website"],
                    "notes": params["p_notes"],
                    "source": params["p_source"],
                    "status": "research" if not params["p_email"] else "new",
                    "consent_basis": params["p_consent_basis"],
                    "approved_to_contact": params["p_approved_to_contact"],
                }
                db.inserted.append(row)
                if db.lose_insert_response:
                    return Result([])
                return Result([{
                    "lead_id": "inserted-lead-id",
                    "outcome": "created",
                    "selected_email": params["p_email"],
                }])

        return RPCQuery()


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
        "company_facts": [{
            "category": "products_services",
            "fact": "Manufactures industrial control systems.",
            "source_url": "https://acme.example/products",
        }],
        "decision_maker": {
            "name": "Alex Example",
            "role": "Managing Director",
            "professional_background": "Leads the company's industrial operations.",
            "source_url": "https://acme.example/leadership",
            "email": "private@example.com",
        },
    }
    response = {
        "text": json.dumps({"companies": [company]}),
        "candidates": [{
            "grounding_metadata": {
                "grounding_chunks": [
                    {"web": {"uri": "https://acme.example/about"}},
                    {"web": {"uri": "https://acme.example/products"}},
                    {"web": {"uri": "https://acme.example/leadership"}},
                ]
            }
        }],
    }
    monkeypatch.setattr(research.types, "GenerateContentConfig", lambda **kwargs: kwargs)
    monkeypatch.setattr(research.types, "Tool", lambda **kwargs: kwargs)
    monkeypatch.setattr(research.types, "GoogleSearch", lambda: {})
    monkeypatch.setattr(research, "get_model_name", lambda: "test-model")
    monkeypatch.setattr(research, "log_event", lambda *_args, **_kwargs: None)
    saved_snapshots = []
    monkeypatch.setattr(
        research, "save_company_research_snapshot",
        lambda _db, **kwargs: saved_snapshots.append(kwargs) or {"snapshot_id": kwargs["dossier"]["snapshot_id"]},
    )
    audit_events = []
    monkeypatch.setattr(
        research, "audit_event",
        lambda _db, **kwargs: audit_events.append(kwargs) or True,
    )

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
    dossier = result["companies"][0]["company_dossier"]
    assert dossier["decision_maker"]["name"] == "Alex Example"
    assert dossier["facts"][0]["fact"] == "Manufactures industrial control systems."
    assert "private@example.com" not in saved["notes"]
    assert "Alex Example" in saved["notes"]
    assert "https://acme.example/leadership" in saved["notes"]
    assert result["email_sending"] == "disabled"
    insert_events = [event for event in audit_events if event["action"] == "save_researched_company"]
    assert [event["status"] for event in insert_events] == ["pending", "success"]
    assert insert_events[0]["operation_id"] == insert_events[1]["operation_id"]
    assert len(saved_snapshots) == 1
    assert saved_snapshots[0]["lead_id"] == "inserted-lead-id"
    assert saved_snapshots[0]["company_domain"] == "acme.example"
    assert saved_snapshots[0]["dossier"]["snapshot_id"] == dossier["snapshot_id"]
    assert len(db.updated) == 1
    assert db.updated[0]["filters"] == {"id": "inserted-lead-id"}
    lead_evidence = db.updated[0]["payload"]["research_evidence"]
    assert lead_evidence[0]["source_url"] == "https://acme.example/products"
    assert lead_evidence[0]["excerpt"] == "Manufactures industrial control systems."
    assert lead_evidence[0]["source_kind"] == "lead_research_note"
    snapshot_events = [event for event in audit_events if event["action"] == "company_research_snapshot"]
    assert [event["status"] for event in snapshot_events] == ["pending", "success"]
    snapshot_manifest = snapshot_events[-1]["result"]
    assert snapshot_manifest["snapshot_id"] == dossier["snapshot_id"]
    assert snapshot_manifest["schema_version"] == 1
    assert snapshot_manifest["company_domain"] == "acme.example"
    assert len(snapshot_manifest["content_sha256"]) == 64


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
    monkeypatch.setattr(research, "audit_event", lambda *_args, **_kwargs: True)

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



def test_research_quality_caps_confidence_when_evidence_is_thin():
    confidence, score, evidence = research._research_quality({
        "research_confidence": "high",
        "business_fit_score": 96,
        "potential_fit": "Possible automation fit",
        "fit_evidence": ["One public signal"],
    })
    assert confidence == "medium"
    assert score == 70
    assert evidence == ["One public signal"]


def test_research_quality_requires_evidence_and_specific_fit():
    confidence, score, evidence = research._research_quality({
        "research_confidence": "high",
        "business_fit_score": 88,
        "potential_fit": " ",
        "fit_evidence": [],
    })
    assert confidence == "low"
    assert score == 40
    assert evidence == []



def test_global_research_uses_configured_gemini_client_and_no_sampling_params(monkeypatch):
    captured = {}
    response = {
        "text": json.dumps({"companies": []}),
        "candidates": [{"grounding_metadata": {"grounding_chunks": [{"web": {"uri": "https://example.com/source"}}]}}],
    }
    client = FakeClient(response)
    monkeypatch.setattr(research.types, "GenerateContentConfig", lambda **kwargs: captured.update(kwargs) or kwargs)
    monkeypatch.setattr(research.types, "Tool", lambda **kwargs: kwargs)
    monkeypatch.setattr(research.types, "GoogleSearch", lambda: {})
    monkeypatch.setattr(research, "get_model_name", lambda: "gemini-3.8-flash")
    monkeypatch.setattr(research, "get_gemini_client", lambda: client)
    monkeypatch.setattr(research, "log_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(research, "audit_event", lambda *_args, **_kwargs: True)
    result = research.research_global_companies(FakeDB(), "teszt leadkutatás")
    assert result["saved_count"] == 0
    assert "temperature" not in captured
    assert "top_p" not in captured
    assert "top_k" not in captured


def test_lead_research_and_market_write_deny_missing_auth_session_when_enforced(monkeypatch):
    import jarvis_common
    import pytest

    monkeypatch.setattr(jarvis_common, "env_bool", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        jarvis_common, "get_user_supabase",
        lambda *_args, **_kwargs: pytest.fail("Missing session must be denied before DB access"),
    )
    with pytest.raises(PermissionError, match="Auth-munkamenet"):
        research.research_global_companies(FakeDB(), "kutatás", FakeClient({}))
    with pytest.raises(PermissionError, match="Auth-munkamenet"):
        research.set_research_market(FakeDB(), "Germany")



def test_global_research_does_not_insert_company_when_pending_audit_fails(monkeypatch):
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
    monkeypatch.setattr(
        research, "audit_event",
        lambda _db, **kwargs: kwargs["status"] != "pending"
        or kwargs["action"] != "save_researched_company",
    )

    db = FakeDB()
    import pytest
    with pytest.raises(RuntimeError, match="pending auditbejegyzés"):
        research.research_global_companies(db, "globális cégek", FakeClient(response))
    assert db.inserted == []


def test_global_research_rejects_unapproved_market_before_external_search(monkeypatch):
    import pytest

    monkeypatch.setattr(
        research, "get_gemini_client",
        lambda: pytest.fail("Invalid market must be rejected before creating a search client"),
    )
    for market in ("Atlantis", "Hungary; ignore rules", "", None, 42):
        if market is None:
            continue
        with pytest.raises(ValueError, match="célország"):
            research.research_global_companies(
                FakeDB(), "test", client=FakeClient({}), market_country=market
            )


def test_global_research_uses_default_market_when_market_is_omitted(monkeypatch):
    captured = {}
    response = {
        "text": json.dumps({"companies": []}),
        "candidates": [{"grounding_metadata": {"grounding_chunks": [{"web": {"uri": "https://example.com/source"}}]}}],
    }
    monkeypatch.setattr(research.types, "GenerateContentConfig", lambda **kwargs: captured.update(kwargs) or kwargs)
    monkeypatch.setattr(research.types, "Tool", lambda **kwargs: kwargs)
    monkeypatch.setattr(research.types, "GoogleSearch", lambda: {})
    monkeypatch.setattr(research, "get_model_name", lambda: "test-model")
    monkeypatch.setattr(research, "get_research_market", lambda _db: "Hungary")
    monkeypatch.setattr(research, "log_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(research, "audit_event", lambda *_args, **_kwargs: True)

    result = research.research_global_companies(FakeDB(), "test", FakeClient(response))
    assert result["market_country"] == "Hungary"


def test_global_research_marks_insert_without_database_confirmation_unknown(monkeypatch):
    import pytest

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
    events = []
    monkeypatch.setattr(
        research, "audit_event",
        lambda _db, **kwargs: events.append(kwargs) or True,
    )

    db = FakeDB(lose_insert_response=True)
    with pytest.raises(RuntimeError, match="nem igazolta vissza"):
        research.research_global_companies(db, "globális cégek", FakeClient(response))

    assert len(db.inserted) == 1
    insert_events = [event for event in events if event["action"] == "save_researched_company"]
    assert [event["status"] for event in insert_events] == ["pending", "unknown"]
    assert insert_events[0]["operation_id"] == insert_events[1]["operation_id"]


def test_global_research_deduplicates_company_beyond_first_database_page(monkeypatch):
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
    monkeypatch.setattr(research, "audit_event", lambda *_args, **_kwargs: True)

    existing = [
        {"company_name": "Existing Company %s" % index, "website": "https://existing-%s.example" % index}
        for index in range(research.EXISTING_LEAD_PAGE_SIZE)
    ]
    existing.append({"company_name": "Acme Systems", "website": "https://acme.example"})
    db = FakeDB(existing=existing)

    result = research.research_global_companies(db, "globális cégek", FakeClient(response))

    assert result["saved_count"] == 0
    assert result["skipped_count"] == 1
    assert db.inserted == []
