from __future__ import annotations

import pytest

from company_dossier import stamp_company_dossier
from intelligence_engine import (
    EvidenceRecord,
    build_intelligence_snapshot,
    evidence_records_from_pains,
)


def test_dossier_snapshot_exposes_shared_source_provenance():
    dossier = stamp_company_dossier({
        "facts": [{
            "category": "business_model",
            "fact": "Subscription-based workflow platform",
            "source_url": "https://example.com/company",
        }],
        "decision_maker": {},
    })

    assert dossier["evidence_records"][0]["source_kind"] == "company_dossier_fact"
    assert dossier["evidence_records"][0]["snapshot_id"] == dossier["snapshot_id"]
    assert dossier["evidence_records"][0]["observed_at"] == dossier["researched_at"]
    assert len(dossier["evidence_records"][0]["evidence_id"]) == 64


def test_pain_evidence_keeps_hypothesis_provenance():
    records = evidence_records_from_pains([{
        "id": "pain-1",
        "created_at": "2026-11-27T10:00:00+00:00",
        "evidence": [{
            "source_url": "https://example.com/report",
            "excerpt": "Manual reconciliation takes several hours.",
        }],
    }])

    assert records[0]["source_kind"] == "company_pain_hypothesis"
    assert records[0]["entity_type"] == "company_pain_hypothesis"
    assert records[0]["entity_id"] == "pain-1"
    assert records[0]["evidence_type"] == "supporting"


def test_shared_intelligence_snapshot_deduplicates_and_counts_sources():
    record = EvidenceRecord.from_dict({
        "source_url": "https://example.com/a",
        "excerpt": "A source-backed statement",
        "source_kind": "other",
    }).to_dict()

    snapshot = build_intelligence_snapshot(
        dossier_evidence=[record],
        pain_evidence=[record],
    )

    assert snapshot["schema_version"] == 1
    assert snapshot["evidence_count"] == 1
    assert snapshot["source_count"] == 1
    assert snapshot["domain_count"] == 1


@pytest.mark.parametrize("source_url", [
    "javascript:alert(1)",
    "http://localhost/private",
    "https://user:password@example.com/private",
])
def test_shared_evidence_rejects_non_public_or_unsafe_urls(source_url):
    with pytest.raises(ValueError):
        EvidenceRecord.from_dict({
            "source_url": source_url,
            "excerpt": "Not a safe public source",
        })


def test_shared_evidence_rejects_unknown_evidence_type():
    with pytest.raises(ValueError):
        EvidenceRecord.from_dict({
            "source_url": "https://example.com",
            "excerpt": "A statement",
            "evidence_type": "assumed_true",
        })
