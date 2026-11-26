"""Append-only persistence for validated company research dossier snapshots."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any
from uuid import UUID


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


def save_company_research_snapshot(
    db: Any, *, lead_id: str, company_domain: str, dossier: dict[str, Any]
) -> dict[str, Any]:
    """Persist one immutable dossier version; duplicate IDs are not silently overwritten."""
    validated = _validated_snapshot(dossier)
    lead_uuid = str(UUID(str(lead_id)))
    domain = str(company_domain or "").strip().casefold()
    if not domain or len(domain) > 253 or not re.fullmatch(r"[a-z0-9.-]+", domain):
        raise ValueError("Invalid company domain.")
    row = {
        **validated,
        "lead_id": lead_uuid,
        "company_domain": domain,
    }
    response = db.table("company_research_snapshots").insert(row).execute()
    data = getattr(response, "data", None)
    if data is not None and isinstance(data, list) and not data:
        raise RuntimeError("Company research snapshot insert returned no row.")
    return {"snapshot_id": validated["snapshot_id"], "lead_id": lead_uuid}


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
