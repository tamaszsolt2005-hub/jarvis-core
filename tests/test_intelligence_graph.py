import pytest

from intelligence_graph import build_graph_snapshot, to_graphviz_dot


def test_graph_snapshot_keeps_only_edges_between_known_nodes():
    nodes = [
        {"id": "company-1", "entity_type": "company", "label": "Acme"},
        {"id": "pain-1", "entity_type": "company_pain", "label": "Manual reporting"},
    ]
    edges = [
        {
            "source_entity_id": "company-1",
            "target_entity_id": "pain-1",
            "relationship_type": "has_pain",
            "confidence": 0.9,
        },
        {
            "source_entity_id": "company-1",
            "target_entity_id": "missing",
            "relationship_type": "has_pain",
        },
    ]

    graph = build_graph_snapshot(nodes, edges)

    assert graph["node_count"] == 2
    assert graph["edge_count"] == 1
    assert graph["relationships"][0]["relationship_type"] == "has_pain"
    assert graph["relationships"][0]["confidence"] == 0.9


def test_graph_snapshot_deduplicates_nodes_and_edges_deterministically():
    nodes = [
        {"id": "a", "entity_type": "company", "label": "Acme"},
        {"id": "a", "entity_type": "company", "label": "Acme Updated"},
        {"id": "b", "entity_type": "market_pattern", "label": "Repeated issue"},
    ]
    edge = {
        "source_entity_id": "a",
        "target_entity_id": "b",
        "relationship_type": "supports_pattern",
    }

    graph = build_graph_snapshot(nodes, [edge, edge])

    assert graph["node_count"] == 2
    assert graph["edge_count"] == 1
    assert graph["nodes"][0]["label"] == "Acme Updated"


def test_graph_snapshot_bounds_nodes_and_reports_truncation():
    nodes = [
        {"id": f"node-{index}", "entity_type": "company", "label": str(index)}
        for index in range(5)
    ]

    graph = build_graph_snapshot(nodes, [], max_nodes=3)

    assert graph["node_count"] == 3
    assert graph["truncated"] is True


def test_graph_snapshot_rejects_invalid_limits():
    with pytest.raises(ValueError):
        build_graph_snapshot([], [], max_nodes=0)
    with pytest.raises(ValueError):
        build_graph_snapshot([], [], max_edges=True)


def test_graph_snapshot_ignores_invalid_confidence_values():
    graph = build_graph_snapshot(
        [{"id": "a", "entity_type": "company", "confidence": float("nan")}],
        [],
    )

    assert graph["nodes"][0]["confidence"] is None


def test_graph_snapshot_ignores_malformed_rows():
    graph = build_graph_snapshot(
        [None, {}, {"id": "ok", "entity_type": "company", "label": "Valid"}],
        [None, {}, {"source_entity_id": "ok", "target_entity_id": "ok", "relationship_type": "loop"}],
    )

    assert graph["node_count"] == 1
    assert graph["edge_count"] == 0


def test_graphviz_output_escapes_quotes_and_drops_dangling_edges():
    graph = build_graph_snapshot(
        [
            {"id": "a", "entity_type": "company", "label": 'Acme "North"'},
            {"id": "b", "entity_type": "company_pain", "label": "Manual\\nwork"},
        ],
        [
            {"source_entity_id": "a", "target_entity_id": "b", "relationship_type": "has_pain"},
            {"source_entity_id": "a", "target_entity_id": "missing", "relationship_type": 'bad"edge'},
        ],
    )

    dot = to_graphviz_dot(graph)

    assert 'Acme \\"North\\"' in dot
    assert 'bad' not in dot
    assert dot.startswith("digraph JARVIS_Intelligence {")


def test_graph_snapshot_preserves_allowlisted_source_provenance():
    graph = build_graph_snapshot(
        [{
            "id": "evidence-1",
            "entity_type": "evidence",
            "label": "Public source excerpt",
            "source_id": "evidence-key",
            "metadata": {
                "source_url": "https://example.com/source",
                "source_kind": "company_dossier_fact",
                "private_note": "must not be copied",
            },
        }],
        [{
            "source_entity_id": "evidence-1",
            "target_entity_id": "company-1",
            "relationship_type": "evidence_for",
            "provenance": {
                "source_url": "https://example.com/source",
                "source": "dossier",
                "untrusted": "must not be copied",
            },
        }],
    )

    assert graph["nodes"][0]["metadata"] == {
        "source_url": "https://example.com/source",
        "source_kind": "company_dossier_fact",
    }
    assert graph["edge_count"] == 0


def test_graphviz_rejects_non_object_snapshot():
    with pytest.raises(ValueError):
        to_graphviz_dot([])
