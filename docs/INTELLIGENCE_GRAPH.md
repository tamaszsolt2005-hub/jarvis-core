# JARVIS Intelligence Graph

## Purpose

The Intelligence Graph connects the existing JARVIS business records into one queryable, provenance-aware network. It does not replace the Lead, company dossier, Opportunity, evidence, or approval tables. Those domain tables remain authoritative; the graph is a derived projection for cross-domain exploration.

The first version only materializes relationships already supported by foreign keys, explicit join rows, or source-evidence references. It does not persist AI-inferred edges as verified facts.

## Graph model

### Entity nodes

The `intelligence_entities` table represents:

| Entity type | Source of truth | Meaning |
|---|---|---|
| `company` | `leads` | A researched company / Lead |
| `person` | `company_research_snapshots.dossier.decision_maker` | A publicly sourced professional decision-maker snapshot |\n| `company_dossier_snapshot` | `company_research_snapshots` | An immutable research snapshot |
| `company_pain` | `business_pain_hypotheses` | A company-specific pain hypothesis |
| `market_pattern` | `market_problem_patterns` | A cross-company problem pattern |
| `saas_opportunity` | `saas_opportunities` | A product candidate |
| `opportunity_assessment` | `opportunity_assessments` | An explicitly approved assessment |
| `evidence` | `intelligence_evidence` | A canonical source record |

Each node has a stable `(entity_type, source_id)` key, an optional Lead reference, a display label, summary, status, confidence and structured metadata. The graph node ID is an internal UUID; the source ID remains traceable to its domain table.

### Relationship edges

The `intelligence_relationships` table stores directed, typed edges:

- `has_dossier_snapshot`: company → dossier snapshot\n- `has_decision_maker`: company → publicly sourced professional person
- `has_pain`: company → pain hypothesis
- `derived_from_snapshot`: dossier snapshot → pain hypothesis
- `supported_by_pain`: market pattern → company pain
- `addresses_pattern`: SaaS opportunity → market pattern
- `evaluates_opportunity`: approved assessment → SaaS opportunity
- `evaluates_pattern`: approved assessment → market pattern
- `evidence_for`: evidence → company, pain or dossier snapshot

Edges are unique by source, target and relationship type. Confidence and provenance are stored separately from node confidence. Removing a source relationship removes its derived edge; deleting a graph node cascades its incident edges.

## Data synchronization

Migration `20261127150000_intelligence_graph.sql`:

1. Creates the entity and relationship projection tables.
2. Adds source-table triggers for Lead, dossier, pain, pattern, pattern–pain links, SaaS opportunities and approved assessments.
3. Adds an evidence trigger to link canonical evidence to its source entity.
4. Backfills existing source rows and relationships through idempotent upserts.
5. Does not update or rewrite source business records or immutable dossier snapshots.

The migration is designed to be replayable. Source tables remain the system of record; graph rows can be rebuilt from them.

## Python projection and dashboard

- `intelligence_graph.py` validates and bounds graph data before rendering.
- It drops malformed nodes, duplicate edges and edges whose endpoints are absent.
- It validates confidence values and caps the displayed graph at 80 nodes and 180 edges in the dashboard.
- `to_graphviz_dot` escapes labels before rendering.
- The Opportunity Center has an **Intelligence Graph** tab with a relationship visualization, edge table and entity details.

The dashboard is read-only. It uses the authenticated Supabase client and RLS; it does not use a service-role write bypass.

## Security

- RLS is enabled on both graph tables.
- Authenticated `admin`, `operator` and `reader` roles can SELECT through app-metadata role policies.
- Authenticated users and `anon` receive no graph write privileges.
- `service_role` maintains the derived projection.
- Security-definer functions pin `search_path` to the empty path and their direct execution is revoked from PUBLIC, anon and authenticated.
- Trigger-maintenance functions are not exposed as dashboard write actions.

## Validation

- `tests/test_intelligence_graph.py` covers bounded projection, malformed rows, deduplication, confidence validation and DOT escaping.
- `supabase/tests/intelligence_graph.test.sql` contains 24 pgTAP assertions for schema, helper access, relationship integrity and RLS.
- CI applies the migration, runs the pgTAP file, checks the assertion plan and replays the migration for idempotency.

## Release boundary

The migration and dashboard code are repository changes on the draft PR #35 branch. They have not been applied to the production database, deployed, or merged. Review and a separate release decision are required before production rollout.
