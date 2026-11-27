"""Append-only persistence for validated company research dossier snapshots."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any
from uuid import UUID, uuid5

_SNAPSHOT_ID_NAMESPACE = UUID("7c3d6c9e-4d7b-4b3b-9a9f-6a6dcb1b2f80")


def _validated_snapshot(dossier: dict[str, Any]) -> dict[str, Any]:
    snapshot_id = str(UUID(str(dossier.get("snapshot_id"))))
    schema_version = dossier.get("schema_version")
    if isinstance(schema_version, bool) or not isinstance(schema_version, int) or schema_version < 1:
        raise ValueError("Invalid company dossier schema version.")
    researched_at = datetime.fromisoformat(str(dossier.get("researched_at", "")).replace("Z", "+00:00"))
    if researched_at.tzinfo is None:
        raise ValueError("Company dossier timestamp must be timezone-aware.")
    content = {
        "facts": dossier.get("facts", []),
        "decision_maker": dossier.get("decision_maker", {}),
    }
    if dossier.get("pain_hypotheses"):
        content["pain_hypotheses"] = dossier["pain_hypotheses"]
    if dossier.get("lead_fit_assessment"):
        content["lead_fit_assessment"] = dossier["lead_fit_assessment"]
    canonical = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if digest != dossier.get("content_sha256"):
        raise ValueError("Company dossier content fingerprint mismatch.")
    return {
        "snapshot_id": snapshot_id,
        "schema_version": schema_version,
        "researched_at": researched_at.isoformat(),
        "content_sha256": digest,
        "dossier": {**content, "schema_version": schema_version,
                    "snapshot_id": snapshot_id, "researched_at": researched_at.isoformat(),
                    "content_sha256": digest},
    }



def _existing_snapshot(db: Any, *, snapshot_id: str) -> dict[str, Any] | None:
    response = (
        db.table("company_research_snapshots")
        .select("snapshot_id,lead_id,company_domain,schema_version,researched_at,content_sha256,dossier")
        .eq("snapshot_id", snapshot_id)
        .limit(1)
        .execute()
    )
    rows = getattr(response, "data", None)
    if isinstance(rows, list) and rows:
        return rows[0] if isinstance(rows[0], dict) else None
    if isinstance(rows, dict):
        return rows
    return None


def _same_snapshot(existing: dict[str, Any], expected: dict[str, Any]) -> bool:
    existing_dossier = existing.get("dossier")
    expected_dossier = expected["dossier"]
    if not isinstance(existing_dossier, dict):
        return False
    existing_content = {"facts": existing_dossier.get("facts", []), "decision_maker": existing_dossier.get("decision_maker", {})}
    expected_content = {"facts": expected_dossier.get("facts", []), "decision_maker": expected_dossier.get("decision_maker", {})}
    if existing_dossier.get("pain_hypotheses"):
        existing_content["pain_hypotheses"] = existing_dossier["pain_hypotheses"]
    if expected_dossier.get("pain_hypotheses"):
        expected_content["pain_hypotheses"] = expected_dossier["pain_hypotheses"]
    if existing_dossier.get("lead_fit_assessment"):
        existing_content["lead_fit_assessment"] = existing_dossier["lead_fit_assessment"]
    if expected_dossier.get("lead_fit_assessment"):
        expected_content["lead_fit_assessment"] = expected_dossier["lead_fit_assessment"]
    return (
        str(existing.get("lead_id")) == expected["lead_id"]
        and str(existing.get("company_domain", "")).casefold() == expected["company_domain"]
        and existing.get("schema_version") == expected["schema_version"]
        and existing.get("content_sha256") == expected["content_sha256"]
        and json.dumps(existing_content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        == json.dumps(expected_content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def _snapshot_result(row: dict[str, Any], *, lead_id: str) -> dict[str, Any]:
    return {"snapshot_id": str(row["snapshot_id"]), "lead_id": lead_id,
            "researched_at": str(row.get("researched_at") or ""),
            "content_sha256": str(row.get("content_sha256") or "")}


def save_company_research_snapshot(
    db: Any, *, lead_id: str, company_domain: str, dossier: dict[str, Any],
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Persist an immutable snapshot, safely replaying the same worker operation."""
    lead_uuid = str(UUID(str(lead_id)))
    domain = str(company_domain or "").strip().casefold()
    if not domain or len(domain) > 253 or not re.fullmatch(r"[a-z0-9.-]+", domain):
        raise ValueError("Invalid company domain.")
    dossier_input = dict(dossier)
    if idempotency_key is not None:
        if not isinstance(idempotency_key, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}", idempotency_key):
            raise ValueError("Invalid snapshot idempotency key.")
        dossier_input["snapshot_id"] = str(uuid5(_SNAPSHOT_ID_NAMESPACE, idempotency_key))
    validated = _validated_snapshot(dossier_input)
    row = {**validated, "lead_id": lead_uuid, "company_domain": domain}
    existing = _existing_snapshot(db, snapshot_id=validated["snapshot_id"])
    if existing is not None:
        if not _same_snapshot(existing, row):
            raise ValueError("Company research snapshot idempotency conflict.")
        return _snapshot_result(existing, lead_id=lead_uuid)
    try:
        response = db.table("company_research_snapshots").insert(row).execute()
        data = getattr(response, "data", None)
        if data is not None and isinstance(data, list) and not data:
            raise RuntimeError("Company research snapshot insert returned no row.")
        return _snapshot_result(row, lead_id=lead_uuid)
    except Exception:
        # A concurrent retry may insert the deterministic ID after our read.
        existing = _existing_snapshot(db, snapshot_id=validated["snapshot_id"])
        if existing is not None and _same_snapshot(existing, row):
            return _snapshot_result(existing, lead_id=lead_uuid)
        raise


def make_company_research_snapshot_persister(db: Any):
    """Build the worker callback that persists the validated dossier before job success."""
    if db is None or not callable(getattr(db, "table", None)):
        raise ValueError("An injected snapshot database client is required.")

    def persist(job: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        operation_id = job.get("operation_id")
        payload = job.get("payload") or {}
        lead_id = job.get("lead_id") or payload.get("lead_id")
        dossier = result.get("company_dossier")
        if not isinstance(operation_id, str) or not isinstance(dossier, dict):
            raise ValueError("Research result is missing its operation ID or validated dossier.")
        saved = save_company_research_snapshot(
            db, lead_id=lead_id,
            company_domain=result.get("company_domain") or payload.get("company_domain"),
            dossier=dossier, idempotency_key=operation_id,
        )
        persisted_dossier = dict(dossier)
        persisted_dossier.update({
            "snapshot_id": saved["snapshot_id"],
            "researched_at": saved["researched_at"],
            "content_sha256": saved["content_sha256"],
        })
        from market_pattern_discovery import (
            discover_market_patterns,
            persist_company_pain_hypotheses,
        )
        pain_hypotheses = persisted_dossier.get("pain_hypotheses")
        pains_created = persist_company_pain_hypotheses(
            db,
            lead_id=str(lead_id),
            snapshot_id=saved["snapshot_id"],
            hypotheses=pain_hypotheses if isinstance(pain_hypotheses, list) else [],
        )
        discovery = discover_market_patterns(db)
        return {
            "company_dossier": persisted_dossier,
            "snapshot_id": saved["snapshot_id"],
            "snapshot_persisted": True,
            "pain_hypotheses_created": pains_created,
            "market_pattern_discovery": discovery,
        }

    return persist


def get_company_research_history(
    db: Any, *, lead_id: str, limit: int = 20
) -> list[dict[str, Any]]:
    """Read newest immutable dossier versions for one lead."""
    lead_uuid = str(UUID(str(lead_id)))
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a positive integer")
    response = (
        db.table("company_research_snapshots")
        .select("snapshot_id,company_domain,schema_version,researched_at,content_sha256,dossier")
        .eq("lead_id", lead_uuid)
        .order("researched_at", desc=True)
        .limit(min(limit, 100))
        .execute()
    )
    return list(getattr(response, "data", None) or [])
