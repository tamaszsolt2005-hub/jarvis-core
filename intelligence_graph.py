"""Read-only, deterministic graph projection for JARVIS Intelligence entities.

The database projection is authoritative for persisted relationships. This module
only validates, bounds and renders rows; it never creates inferred edges.
"""
from __future__ import annotations

import math
import re
from typing import Any, Iterable


DEFAULT_MAX_NODES = 80
DEFAULT_MAX_EDGES = 180


def _clean_text(value: Any, limit: int = 240) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()[:limit]


def _confidence(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    if not math.isfinite(numeric) or not 0 <= numeric <= 1:
        return None
    return round(numeric, 3)


def build_graph_snapshot(
    entities: Iterable[dict[str, Any]],
    relationships: Iterable[dict[str, Any]],
    *,
    max_nodes: int = DEFAULT_MAX_NODES,
    max_edges: int = DEFAULT_MAX_EDGES,
) -> dict[str, Any]:
    """Build a bounded graph containing only valid nodes and connected edges."""
    for name, value, maximum in (
        ("max_nodes", max_nodes, 500),
        ("max_edges", max_edges, 1500),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
            raise ValueError(f"{name} must be an integer between 1 and {maximum}")

    normalized: dict[str, dict[str, Any]] = {}
    for raw in entities:
        if not isinstance(raw, dict):
            continue
        entity_id = _clean_text(raw.get("id"), 80)
        entity_type = _clean_text(raw.get("entity_type"), 60)
        if not entity_id or not entity_type:
            continue
        created_at = _clean_text(raw.get("created_at"), 80)
        raw_metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        metadata = {
            key: _clean_text(raw_metadata.get(key), 2048 if key == "source_url" else 160)
            for key in ("source_url", "source_kind", "source_domain", "snapshot_id", "website")
            if isinstance(raw_metadata.get(key), str) and raw_metadata.get(key).strip()
        }
        normalized[entity_id] = {
            "id": entity_id,
            "entity_type": entity_type,
            "source_id": _clean_text(raw.get("source_id"), 120),
            "label": _clean_text(raw.get("label")) or entity_type,
            "summary": _clean_text(raw.get("summary"), 500),
            "status": _clean_text(raw.get("status"), 60),
            "confidence": _confidence(raw.get("confidence")),
            "lead_id": _clean_text(raw.get("lead_id"), 80),
            "metadata": metadata,
            "created_at": created_at,
        }

    ordered_nodes = sorted(
        normalized.values(),
        key=lambda item: (item["created_at"], item["entity_type"], item["label"].casefold(), item["id"]),
        reverse=True,
    )[:max_nodes]
    node_ids = {item["id"] for item in ordered_nodes}
    ordered_edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    for raw in relationships:
        if not isinstance(raw, dict):
            continue
        source_id = _clean_text(raw.get("source_entity_id"), 80)
        target_id = _clean_text(raw.get("target_entity_id"), 80)
        relationship_type = _clean_text(raw.get("relationship_type"), 60)
        if (
            not source_id or not target_id or source_id == target_id
            or source_id not in node_ids or target_id not in node_ids
            or not relationship_type
        ):
            continue
        key = (source_id, target_id, relationship_type)
        raw_provenance = raw.get("provenance") if isinstance(raw.get("provenance"), dict) else {}
        provenance = {
            key: _clean_text(raw_provenance.get(key), 2048 if key == "source_url" else 160)
            for key in ("source_url", "source", "snapshot_id")
            if isinstance(raw_provenance.get(key), str) and raw_provenance.get(key).strip()
        }
        ordered_edges[key] = {
            "source_entity_id": source_id,
            "target_entity_id": target_id,
            "relationship_type": relationship_type,
            "confidence": _confidence(raw.get("confidence")),
            "provenance": provenance,
        }

    edges = [
        ordered_edges[key]
        for key in sorted(ordered_edges)
    ][:max_edges]
    return {
        "schema_version": 1,
        "node_count": len(ordered_nodes),
        "edge_count": len(edges),
        "nodes": ordered_nodes,
        "relationships": edges,
        "truncated": len(normalized) > len(ordered_nodes),
    }


def _dot_escape(value: Any) -> str:
    text = _clean_text(value, 500)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def to_graphviz_dot(snapshot: dict[str, Any]) -> str:
    """Render a safe Graphviz DOT string from a validated graph snapshot."""
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be a graph object")
    nodes = snapshot.get("nodes", [])
    edges = snapshot.get("relationships", [])
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("snapshot nodes and relationships must be lists")

    lines = [
        "digraph JARVIS_Intelligence {",
        '  graph [rankdir="LR", bgcolor="transparent", overlap="false"];',
        '  node [shape="box", style="rounded,filled", fillcolor="#243247", fontcolor="#FFFFFF"];',
        '  edge [fontcolor="#AAB7C4", color="#8292A5"];',
    ]
    valid_ids: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict):
            continue
        entity_id = _clean_text(node.get("id"), 80)
        if not entity_id:
            continue
        valid_ids.add(entity_id)
        label = _dot_escape(node.get("label") or node.get("entity_type"))
        entity_type = _dot_escape(node.get("entity_type"))
        status = _dot_escape(node.get("status"))
        suffix = "\\n" + status if status else ""
        lines.append(f'  "{_dot_escape(entity_id)}" [label="{entity_type}\\n{label}{suffix}"];')

    for edge in edges:
        if not isinstance(edge, dict):
            continue
        source_id = _clean_text(edge.get("source_entity_id"), 80)
        target_id = _clean_text(edge.get("target_entity_id"), 80)
        if source_id not in valid_ids or target_id not in valid_ids:
            continue
        label = _dot_escape(edge.get("relationship_type"))
        lines.append(f'  "{_dot_escape(source_id)}" -> "{_dot_escape(target_id)}" [label="{label}"];')
    lines.append("}")
    return "\n".join(lines)
