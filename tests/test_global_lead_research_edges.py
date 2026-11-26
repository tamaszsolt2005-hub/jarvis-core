"""Grounding, deduplication and fail-closed tests for global company research."""
from types import SimpleNamespace

import pytest

import global_lead_research as research


def test_research_parsers_and_quality_helpers_reject_untrusted_shapes():
    assert research._field({"text": "ok"}, "text") == "ok"
    assert research._field(SimpleNamespace(text="ok"), "text") == "ok"
    assert research._field(None, "missing", "fallback") == "fallback"
    assert research._grounded_sources({"candidates": [
        {"grounding_metadata": {"grounding_chunks": [
            {"web": {"uri": "https://www.example.com/source"}},
            {"web": {"uri": None}},
        ]}}
    ]}) == ["https://www.example.com/source"]
    assert research._parse_companies("not json") == []
    assert research._parse_companies('{"companies": "not-a-list"}') == []
    assert research._parse_companies('prefix ```json\n{"companies":[{"company_name":"A"},null]}\n```') == [
        {"company_name": "A"}
    ]
    assert research._valid_http_url("https://user:pass@example.com") is None
    assert research._valid_http_url("file:///etc/passwd") is None
    assert research._valid_http_url("https://localhost") is None
    assert research._domain("https://www.Example.com/path") == "example.com"

    confidence, score, evidence = research._research_quality({
        "research_confidence": "high", "business_fit_score": 95,
        "fit_evidence": ["one"], "potential_fit": "Specific fit",
    })
    assert (confidence, score, evidence) == ("medium", 70, ["one"])
    assert research._research_quality({
        "research_confidence": "unknown", "business_fit_score": "bad",
        "fit_evidence": [], "potential_fit": "",
    }) == ("low", None, [])


def test_research_market_helpers_default_report_and_validate(monkeypatch):
    reports = []
    monkeypatch.setattr(research, "report_error", lambda error, **kwargs: reports.append((error, kwargs)))

    class BrokenDB:
        def table(self, _name):
            raise ConnectionError("mock settings outage")

    assert research.get_research_market(BrokenDB()) == "Hungary"
    assert reports[0][1]["operation"] == "read_research_market"

    class Query:
        def __init__(self):
            self.payload = None
        def upsert(self, payload):
            self.payload = payload
            return self
        def execute(self):
            return SimpleNamespace(data=[])
    query = Query()
    class DB:
        def table(self, name):
            assert name == "settings"
            return query
    assert research.set_research_market(DB(), "Germany") == "Germany"
    assert query.payload == {"key": "lead_research_market", "value": {"country": "Germany"}}
    with pytest.raises(ValueError):
        research.set_research_market(DB(), "Mars")

    assert research.detect_market_change("Válts a német piacra") == "Germany"
    assert research.detect_market_change("Milyen az időjárás?") is None


class _ResearchDB:
    def __init__(self, existing=None):
        self.existing = existing or []
        self.inserted = []
    def table(self, name):
        assert name == "leads"
        return _ResearchQuery(self)

    def rpc(self, _name, params):
        db = self

        class RPCQuery:
            def execute(self):
                db.inserted.append({
                    "company_name": params["p_company_name"],
                    "email": params["p_email"],
                    "website": params["p_website"],
                    "notes": params["p_notes"],
                    "source": params["p_source"],
                    "status": "research" if not params["p_email"] else "new",
                    "consent_basis": params["p_consent_basis"],
                    "approved_to_contact": params["p_approved_to_contact"],
                    "opted_out": False,
                })
                return SimpleNamespace(data=[{
                    "lead_id": "new-lead",
                    "outcome": "created",
                    "selected_email": params["p_email"],
                }])

        return RPCQuery()


class _ResearchQuery:
    def __init__(self, db):
        self.db = db
        self.payload = None
    def select(self, *_args, **_kwargs):
        return self
    def limit(self, *_args, **_kwargs):
        return self
    def order(self, *_args, **_kwargs):
        return self
    def range(self, *_args, **_kwargs):
        return self
    def insert(self, payload):
        self.payload = payload
        return self
    def execute(self):
        if self.payload is not None:
            self.db.inserted.append(self.payload)
            return SimpleNamespace(data=[{"id": "new-lead"}])
        return SimpleNamespace(data=list(self.db.existing))


def test_research_inserts_only_grounded_new_company_without_contact_permission(monkeypatch):
    company = {
        "company_name": "New Example Ltd", "website": "https://new.example",
        "source_url": "https://industry.example/article", "country": "Germany",
        "industry": "Manufacturing", "business_summary": "Public company profile",
        "potential_fit": "Automation fit", "business_fit_score": 88,
        "fit_evidence": ["Published production workflow", "Public service catalogue"],
        "research_confidence": "high",
    }
    duplicate = {**company, "company_name": "Existing Ltd", "website": "https://existing.example"}
    unsupported = {**company, "company_name": "Unverified Ltd", "website": "https://not-grounded.example"}
    response = SimpleNamespace(
        text=__import__("json").dumps({"companies": [company, duplicate, unsupported]}),
        candidates=[SimpleNamespace(grounding_metadata=SimpleNamespace(
            grounding_chunks=[
                SimpleNamespace(web=SimpleNamespace(uri="https://new.example/about")),
                SimpleNamespace(web=SimpleNamespace(uri="https://industry.example/article")),
                SimpleNamespace(web=SimpleNamespace(uri="https://existing.example")),
            ]
        ))],
    )
    class Models:
        def generate_content(self, **kwargs):
            assert kwargs["model"] == "test-model"
            assert "Germany" in kwargs["contents"]
            return response
    client = SimpleNamespace(models=Models())
    db = _ResearchDB(existing=[{"company_name": "Existing Ltd", "website": "https://existing.example"}])
    audits, events = [], []
    monkeypatch.setattr(research, "get_model_name", lambda: "test-model")
    monkeypatch.setattr(research, "audit_event", lambda *args, **kwargs: audits.append(kwargs) or True)
    monkeypatch.setattr(research, "log_event", lambda *args: events.append(args))

    result = research.research_global_companies(db, "find manufacturing firms", client=client, market_country="Germany")

    assert result["saved_count"] == 1
    assert result["skipped_count"] == 2
    assert result["email_sending"] == "disabled"
    assert result["contact_permission"] == "not_granted"
    assert len(db.inserted) == 1
    saved = db.inserted[0]
    assert saved["company_name"] == "New Example Ltd"
    assert saved["email"] is None
    assert saved["approved_to_contact"] is False
    assert saved["consent_basis"] is None
    assert saved["opted_out"] is False
    # The per-company write is audited before insertion; the summary audit is last.
    assert audits[0]["action"] == "save_researched_company"
    assert audits[-1]["action"] == "research_companies"
    assert events


def test_research_refuses_to_save_when_google_grounding_is_absent():
    class Models:
        def generate_content(self, **_kwargs):
            return SimpleNamespace(text='{"companies":[{"company_name":"Invented"}]}', candidates=[])
    db = _ResearchDB()
    with pytest.raises(RuntimeError, match="forrás"):
        research.research_global_companies(
            db, "find companies", client=SimpleNamespace(models=Models()),
            market_country="Worldwide",
        )
    assert db.inserted == []
