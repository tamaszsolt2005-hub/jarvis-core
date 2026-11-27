-- Canonical entity and relationship graph over existing JARVIS business records.
-- Derived graph projections only; source domain tables remain authoritative.
BEGIN;

CREATE TABLE IF NOT EXISTS public.intelligence_entities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_type text NOT NULL CHECK (entity_type IN (
    'company','company_dossier_snapshot','company_pain','market_pattern',
    'saas_opportunity','opportunity_assessment','evidence'
  )),
  source_id text NOT NULL CHECK (length(btrim(source_id)) BETWEEN 1 AND 120),
  lead_id uuid REFERENCES public.leads(id) ON DELETE CASCADE,
  label text NOT NULL CHECK (length(btrim(label)) BETWEEN 1 AND 240),
  summary text NOT NULL DEFAULT '' CHECK (length(summary) <= 2000),
  status text NOT NULL DEFAULT '',
  confidence numeric(4,3) CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (entity_type, source_id)
);

CREATE INDEX IF NOT EXISTS intelligence_entities_type_updated_idx
  ON public.intelligence_entities (entity_type, updated_at DESC);
CREATE INDEX IF NOT EXISTS intelligence_entities_lead_idx
  ON public.intelligence_entities (lead_id, entity_type);

CREATE TABLE IF NOT EXISTS public.intelligence_relationships (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_entity_id uuid NOT NULL REFERENCES public.intelligence_entities(id) ON DELETE CASCADE,
  target_entity_id uuid NOT NULL REFERENCES public.intelligence_entities(id) ON DELETE CASCADE,
  relationship_type text NOT NULL CHECK (relationship_type IN (
    'has_dossier_snapshot','has_pain','derived_from_snapshot',
    'supported_by_pain','addresses_pattern','evaluates_opportunity',
    'evaluates_pattern','evidence_for'
  )),
  confidence numeric(4,3) CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
  provenance jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(provenance) = 'object'),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_entity_id, target_entity_id, relationship_type),
  CHECK (source_entity_id <> target_entity_id)
);

CREATE INDEX IF NOT EXISTS intelligence_relationships_source_idx
  ON public.intelligence_relationships (source_entity_id, relationship_type);
CREATE INDEX IF NOT EXISTS intelligence_relationships_target_idx
  ON public.intelligence_relationships (target_entity_id, relationship_type);

ALTER TABLE public.intelligence_entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.intelligence_relationships ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.intelligence_entities, public.intelligence_relationships
  FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT ON TABLE public.intelligence_entities, public.intelligence_relationships
  TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.intelligence_entities,
  public.intelligence_relationships TO service_role;

DROP POLICY IF EXISTS intelligence_entities_shared_read ON public.intelligence_entities;
CREATE POLICY intelligence_entities_shared_read
  ON public.intelligence_entities FOR SELECT TO authenticated
  USING ((SELECT auth.jwt() -> 'app_metadata' ->> 'role') IN ('admin','operator','reader'));
DROP POLICY IF EXISTS intelligence_relationships_shared_read ON public.intelligence_relationships;
CREATE POLICY intelligence_relationships_shared_read
  ON public.intelligence_relationships FOR SELECT TO authenticated
  USING ((SELECT auth.jwt() -> 'app_metadata' ->> 'role') IN ('admin','operator','reader'));

CREATE OR REPLACE FUNCTION public.upsert_intelligence_entity(
  p_entity_type text,
  p_source_id text,
  p_lead_id uuid,
  p_label text,
  p_summary text,
  p_status text,
  p_confidence numeric,
  p_metadata jsonb
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $graph_entity$
DECLARE
  v_id uuid;
BEGIN
  INSERT INTO public.intelligence_entities (
    entity_type, source_id, lead_id, label, summary, status, confidence, metadata
  ) VALUES (
    p_entity_type, p_source_id, p_lead_id,
    left(COALESCE(NULLIF(btrim(p_label),''), p_entity_type), 240),
    left(COALESCE(p_summary,''), 2000),
    COALESCE(p_status,''),
    p_confidence,
    CASE WHEN jsonb_typeof(p_metadata) = 'object' THEN p_metadata ELSE '{}'::jsonb END
  )
  ON CONFLICT (entity_type, source_id) DO UPDATE SET
    lead_id = COALESCE(EXCLUDED.lead_id, public.intelligence_entities.lead_id),
    label = EXCLUDED.label,
    summary = EXCLUDED.summary,
    status = EXCLUDED.status,
    confidence = EXCLUDED.confidence,
    metadata = EXCLUDED.metadata,
    updated_at = now()
  RETURNING id INTO v_id;
  RETURN v_id;
END;
$graph_entity$;

CREATE OR REPLACE FUNCTION public.upsert_intelligence_relationship(
  p_source_type text,
  p_source_id text,
  p_target_type text,
  p_target_id text,
  p_relationship_type text,
  p_confidence numeric,
  p_provenance jsonb
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $graph_relationship$
DECLARE
  v_source uuid;
  v_target uuid;
  v_id uuid;
BEGIN
  SELECT id INTO v_source FROM public.intelligence_entities
    WHERE entity_type = p_source_type AND source_id = p_source_id;
  SELECT id INTO v_target FROM public.intelligence_entities
    WHERE entity_type = p_target_type AND source_id = p_target_id;
  IF v_source IS NULL OR v_target IS NULL OR v_source = v_target THEN
    RETURN NULL;
  END IF;
  INSERT INTO public.intelligence_relationships (
    source_entity_id, target_entity_id, relationship_type, confidence, provenance
  ) VALUES (
    v_source, v_target, p_relationship_type, p_confidence,
    CASE WHEN jsonb_typeof(p_provenance) = 'object' THEN p_provenance ELSE '{}'::jsonb END
  )
  ON CONFLICT (source_entity_id, target_entity_id, relationship_type) DO UPDATE SET
    confidence = EXCLUDED.confidence,
    provenance = EXCLUDED.provenance
  RETURNING id INTO v_id;
  RETURN v_id;
END;
$graph_relationship$;

CREATE OR REPLACE FUNCTION public.delete_intelligence_relationship(
  p_source_type text,
  p_source_id text,
  p_target_type text,
  p_target_id text,
  p_relationship_type text
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $graph_delete_relationship$
BEGIN
  DELETE FROM public.intelligence_relationships relationship
  USING public.intelligence_entities source_entity,
        public.intelligence_entities target_entity
  WHERE relationship.source_entity_id = source_entity.id
    AND relationship.target_entity_id = target_entity.id
    AND source_entity.entity_type = p_source_type
    AND source_entity.source_id = p_source_id
    AND target_entity.entity_type = p_target_type
    AND target_entity.source_id = p_target_id
    AND relationship.relationship_type = p_relationship_type;
END;
$graph_delete_relationship$;

CREATE OR REPLACE FUNCTION public.sync_intelligence_graph_source()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $graph_source$
DECLARE
  v_id text;
  v_lead_id uuid;
  v_label text;
  v_summary text;
  v_status text;
  v_confidence numeric;
  v_metadata jsonb;
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF TG_TABLE_NAME = 'leads' THEN
      DELETE FROM public.intelligence_entities WHERE entity_type = 'company' AND source_id = OLD.id::text;
    ELSIF TG_TABLE_NAME = 'company_research_snapshots' THEN
      DELETE FROM public.intelligence_entities WHERE entity_type = 'company_dossier_snapshot' AND source_id = OLD.snapshot_id::text;
    ELSIF TG_TABLE_NAME = 'business_pain_hypotheses' THEN
      DELETE FROM public.intelligence_entities WHERE entity_type = 'company_pain' AND source_id = OLD.id::text;
    ELSIF TG_TABLE_NAME = 'market_problem_patterns' THEN
      DELETE FROM public.intelligence_entities WHERE entity_type = 'market_pattern' AND source_id = OLD.id::text;
    ELSIF TG_TABLE_NAME = 'saas_opportunities' THEN
      DELETE FROM public.intelligence_entities WHERE entity_type = 'saas_opportunity' AND source_id = OLD.id::text;
    END IF;
    RETURN OLD;
  END IF;

  IF TG_TABLE_NAME = 'leads' THEN
    v_id := NEW.id::text;
    v_label := NEW.company_name;
    v_summary := COALESCE(NEW.notes,'');
    v_status := COALESCE(NEW.status,'');
    v_metadata := jsonb_build_object('website', COALESCE(NEW.website,''));
    PERFORM public.upsert_intelligence_entity(
      'company', v_id, NEW.id, v_label, v_summary, v_status, NULL, v_metadata
    );

  ELSIF TG_TABLE_NAME = 'company_research_snapshots' THEN
    v_id := NEW.snapshot_id::text;
    v_lead_id := NEW.lead_id;
    SELECT company_name INTO v_label FROM public.leads WHERE id = NEW.lead_id;
    v_label := 'Cégdosszié · ' || COALESCE(v_label, NEW.lead_id::text);
    v_summary := COALESCE(NEW.dossier ->> 'summary','');
    v_metadata := jsonb_build_object(
      'researched_at', COALESCE(NEW.dossier ->> 'researched_at',''),
      'schema_version', COALESCE(NEW.dossier ->> 'schema_version','')
    );
    PERFORM public.upsert_intelligence_entity(
      'company_dossier_snapshot', v_id, v_lead_id, v_label, v_summary, 'snapshot', NULL, v_metadata
    );
    PERFORM public.upsert_intelligence_relationship(
      'company', v_lead_id::text, 'company_dossier_snapshot', v_id,
      'has_dossier_snapshot', NULL, jsonb_build_object('source','company_research_snapshots')
    );

  ELSIF TG_TABLE_NAME = 'business_pain_hypotheses' THEN
    v_id := NEW.id::text;
    v_lead_id := NEW.lead_id;
    v_label := left(NEW.statement, 240);
    v_summary := NEW.statement;
    v_status := NEW.status;
    v_confidence := NEW.confidence;
    v_metadata := jsonb_build_object('category', NEW.category);
    PERFORM public.upsert_intelligence_entity(
      'company_pain', v_id, v_lead_id, v_label, v_summary, v_status, v_confidence, v_metadata
    );
    PERFORM public.upsert_intelligence_relationship(
      'company', v_lead_id::text, 'company_pain', v_id,
      'has_pain', NEW.confidence, jsonb_build_object('source','business_pain_hypotheses')
    );
    IF NEW.snapshot_id IS NOT NULL THEN
      PERFORM public.upsert_intelligence_relationship(
        'company_dossier_snapshot', NEW.snapshot_id::text, 'company_pain', v_id,
        'derived_from_snapshot', NEW.confidence, '{}'::jsonb
      );
    END IF;

  ELSIF TG_TABLE_NAME = 'market_problem_patterns' THEN
    v_id := NEW.id::text;
    v_label := NEW.title;
    v_summary := NEW.description;
    v_status := NEW.status;
    v_confidence := NEW.confidence;
    v_metadata := '{}'::jsonb;
    PERFORM public.upsert_intelligence_entity(
      'market_pattern', v_id, NULL, v_label, v_summary, v_status, v_confidence, v_metadata
    );

  ELSIF TG_TABLE_NAME = 'saas_opportunities' THEN
    v_id := NEW.id::text;
    v_label := NEW.name;
    v_summary := NEW.summary;
    v_status := NEW.status;
    v_metadata := jsonb_build_object('market_pattern_id', NEW.market_pattern_id::text);
    PERFORM public.upsert_intelligence_entity(
      'saas_opportunity', v_id, NULL, v_label, v_summary, v_status, NULL, v_metadata
    );
    PERFORM public.upsert_intelligence_relationship(
      'saas_opportunity', v_id, 'market_pattern', NEW.market_pattern_id::text,
      'addresses_pattern', NULL, jsonb_build_object('source','saas_opportunities')
    );

  ELSIF TG_TABLE_NAME = 'opportunity_assessments' THEN
    v_id := NEW.id::text;
    v_label := NEW.opportunity_name_snapshot;
    v_summary := NEW.opportunity_summary_snapshot;
    v_status := NEW.approval_status;
    v_confidence := NEW.assessment_confidence;
    v_metadata := jsonb_build_object(
      'weighted_score', NEW.weighted_score,
      'approved_at', NEW.approved_at,
      'approved_by', NEW.approved_by
    );
    PERFORM public.upsert_intelligence_entity(
      'opportunity_assessment', v_id, NULL, v_label, v_summary, v_status, v_confidence, v_metadata
    );
    PERFORM public.upsert_intelligence_relationship(
      'opportunity_assessment', v_id, 'saas_opportunity', NEW.opportunity_id::text,
      'evaluates_opportunity', NEW.assessment_confidence, '{}'::jsonb
    );
    PERFORM public.upsert_intelligence_relationship(
      'opportunity_assessment', v_id, 'market_pattern', NEW.market_pattern_id::text,
      'evaluates_pattern', NEW.assessment_confidence, '{}'::jsonb
    );
  END IF;

  RETURN NEW;
END;
$graph_source$;

CREATE OR REPLACE FUNCTION public.sync_intelligence_graph_pattern_pain()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $graph_pattern_pain$
DECLARE
  v_pattern_id text;
  v_pain_id text;
BEGIN
  IF TG_OP = 'DELETE' THEN
    PERFORM public.delete_intelligence_relationship(
      'market_pattern', OLD.market_pattern_id::text,
      'company_pain', OLD.company_pain_id::text,
      'supported_by_pain'
    );
    RETURN OLD;
  END IF;
  v_pattern_id := NEW.market_pattern_id::text;
  v_pain_id := NEW.company_pain_id::text;
  PERFORM public.upsert_intelligence_relationship(
    'market_pattern', v_pattern_id, 'company_pain', v_pain_id,
    'supported_by_pain', NULL, jsonb_build_object('source','market_pattern_pains')
  );
  RETURN NEW;
END;
$graph_pattern_pain$;

CREATE OR REPLACE FUNCTION public.sync_intelligence_graph_evidence()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $graph_evidence$
DECLARE
  v_target_type text;
  v_target_id text;
BEGIN
  PERFORM public.upsert_intelligence_entity(
    'evidence', NEW.evidence_id, NEW.lead_id,
    left(NEW.excerpt,240), NEW.excerpt, NEW.evidence_type, NULL,
    jsonb_build_object(
      'source_url', NEW.source_url,
      'source_domain', NEW.source_domain,
      'source_kind', NEW.source_kind,
      'observed_at', NEW.observed_at,
      'captured_at', NEW.captured_at
    )
  );

  IF NEW.source_domain = 'lead' THEN
    v_target_type := 'company';
    v_target_id := NEW.entity_id;
  ELSIF NEW.source_domain = 'company_dossier' THEN
    v_target_type := 'company';
    v_target_id := NEW.entity_id;
  ELSIF NEW.source_domain = 'opportunity' THEN
    v_target_type := 'company_pain';
    v_target_id := NEW.entity_id;
  END IF;

  IF v_target_type IS NOT NULL AND v_target_id IS NOT NULL AND v_target_id <> '' THEN
    PERFORM public.upsert_intelligence_relationship(
      'evidence', NEW.evidence_id, v_target_type, v_target_id,
      'evidence_for', NULL, jsonb_build_object('source_url', NEW.source_url)
    );
  END IF;
  IF NEW.snapshot_id <> '' THEN
    PERFORM public.upsert_intelligence_relationship(
      'evidence', NEW.evidence_id, 'company_dossier_snapshot', NEW.snapshot_id,
      'evidence_for', NULL, jsonb_build_object('source_url', NEW.source_url)
    );
  END IF;
  RETURN NEW;
END;
$graph_evidence$;

REVOKE ALL ON FUNCTION public.upsert_intelligence_entity(text,text,uuid,text,text,text,numeric,jsonb)
  FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.upsert_intelligence_relationship(text,text,text,text,text,numeric,jsonb)
  FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.delete_intelligence_relationship(text,text,text,text,text)
  FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.sync_intelligence_graph_source()
  FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.sync_intelligence_graph_pattern_pain()
  FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.sync_intelligence_graph_evidence()
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.upsert_intelligence_entity(text,text,uuid,text,text,text,numeric,jsonb)
  TO service_role;
GRANT EXECUTE ON FUNCTION public.upsert_intelligence_relationship(text,text,text,text,text,numeric,jsonb)
  TO service_role;
GRANT EXECUTE ON FUNCTION public.delete_intelligence_relationship(text,text,text,text,text)
  TO service_role;
GRANT EXECUTE ON FUNCTION
  public.sync_intelligence_graph_source(),
  public.sync_intelligence_graph_pattern_pain(),
  public.sync_intelligence_graph_evidence()
  TO service_role;

DROP TRIGGER IF EXISTS intelligence_graph_lead_sync ON public.leads;
CREATE TRIGGER intelligence_graph_lead_sync
AFTER INSERT OR UPDATE OF company_name, notes, status, website OR DELETE ON public.leads
FOR EACH ROW EXECUTE FUNCTION public.sync_intelligence_graph_source();

DROP TRIGGER IF EXISTS intelligence_graph_dossier_sync ON public.company_research_snapshots;
CREATE TRIGGER intelligence_graph_dossier_sync
AFTER INSERT OR DELETE ON public.company_research_snapshots
FOR EACH ROW EXECUTE FUNCTION public.sync_intelligence_graph_source();

DROP TRIGGER IF EXISTS intelligence_graph_pain_sync ON public.business_pain_hypotheses;
CREATE TRIGGER intelligence_graph_pain_sync
AFTER INSERT OR UPDATE OF statement, confidence, status, category, snapshot_id OR DELETE ON public.business_pain_hypotheses
FOR EACH ROW EXECUTE FUNCTION public.sync_intelligence_graph_source();

DROP TRIGGER IF EXISTS intelligence_graph_pattern_sync ON public.market_problem_patterns;
CREATE TRIGGER intelligence_graph_pattern_sync
AFTER INSERT OR UPDATE OF title, description, confidence, status OR DELETE ON public.market_problem_patterns
FOR EACH ROW EXECUTE FUNCTION public.sync_intelligence_graph_source();

DROP TRIGGER IF EXISTS intelligence_graph_pattern_pain_sync ON public.market_pattern_pains;
CREATE TRIGGER intelligence_graph_pattern_pain_sync
AFTER INSERT OR DELETE ON public.market_pattern_pains
FOR EACH ROW EXECUTE FUNCTION public.sync_intelligence_graph_pattern_pain();

DROP TRIGGER IF EXISTS intelligence_graph_opportunity_sync ON public.saas_opportunities;
CREATE TRIGGER intelligence_graph_opportunity_sync
AFTER INSERT OR UPDATE OF name, summary, status, market_pattern_id OR DELETE ON public.saas_opportunities
FOR EACH ROW EXECUTE FUNCTION public.sync_intelligence_graph_source();

DROP TRIGGER IF EXISTS intelligence_graph_assessment_sync ON public.opportunity_assessments;
CREATE TRIGGER intelligence_graph_assessment_sync
AFTER INSERT ON public.opportunity_assessments
FOR EACH ROW EXECUTE FUNCTION public.sync_intelligence_graph_source();

DROP TRIGGER IF EXISTS intelligence_graph_evidence_sync ON public.intelligence_evidence;
CREATE TRIGGER intelligence_graph_evidence_sync
AFTER INSERT ON public.intelligence_evidence
FOR EACH ROW EXECUTE FUNCTION public.sync_intelligence_graph_evidence();

-- Idempotent backfill: project existing source records without modifying them.
DO $graph_backfill$
DECLARE
  item record;
BEGIN
  FOR item IN SELECT id, company_name, notes, status, website FROM public.leads LOOP
    PERFORM public.upsert_intelligence_entity(
      'company', item.id::text, item.id, item.company_name,
      COALESCE(item.notes,''), COALESCE(item.status,''),
      NULL, jsonb_build_object('website', COALESCE(item.website,''))
    );
  END LOOP;

  FOR item IN
    SELECT snapshot.snapshot_id, snapshot.lead_id, snapshot.dossier, lead.company_name
    FROM public.company_research_snapshots snapshot
    LEFT JOIN public.leads lead ON lead.id = snapshot.lead_id
  LOOP
    PERFORM public.upsert_intelligence_entity(
      'company_dossier_snapshot', item.snapshot_id::text, item.lead_id,
      'Cégdosszié · ' || COALESCE(item.company_name,item.lead_id::text),
      COALESCE(item.dossier ->> 'summary',''), 'snapshot', NULL,
      jsonb_build_object(
        'researched_at', COALESCE(item.dossier ->> 'researched_at',''),
        'schema_version', COALESCE(item.dossier ->> 'schema_version','')
      )
    );
    PERFORM public.upsert_intelligence_relationship(
      'company', item.lead_id::text, 'company_dossier_snapshot', item.snapshot_id::text,
      'has_dossier_snapshot', NULL, jsonb_build_object('source','company_research_snapshots')
    );
  END LOOP;

  FOR item IN SELECT id, lead_id, snapshot_id, statement, category, confidence, status
    FROM public.business_pain_hypotheses LOOP
    PERFORM public.upsert_intelligence_entity(
      'company_pain', item.id::text, item.lead_id, item.statement,
      item.statement, item.status, item.confidence, jsonb_build_object('category',item.category)
    );
    PERFORM public.upsert_intelligence_relationship(
      'company', item.lead_id::text, 'company_pain', item.id::text,
      'has_pain', item.confidence, jsonb_build_object('source','business_pain_hypotheses')
    );
    IF item.snapshot_id IS NOT NULL THEN
      PERFORM public.upsert_intelligence_relationship(
        'company_dossier_snapshot', item.snapshot_id::text, 'company_pain', item.id::text,
        'derived_from_snapshot', item.confidence, '{}'::jsonb
      );
    END IF;
  END LOOP;

  FOR item IN SELECT id, title, description, confidence, status
    FROM public.market_problem_patterns LOOP
    PERFORM public.upsert_intelligence_entity(
      'market_pattern', item.id::text, NULL, item.title,
      item.description, item.status, item.confidence, '{}'::jsonb
    );
  END LOOP;

  FOR item IN SELECT id, market_pattern_id, name, summary, status
    FROM public.saas_opportunities LOOP
    PERFORM public.upsert_intelligence_entity(
      'saas_opportunity', item.id::text, NULL, item.name,
      item.summary, item.status, NULL,
      jsonb_build_object('market_pattern_id',item.market_pattern_id::text)
    );
    PERFORM public.upsert_intelligence_relationship(
      'saas_opportunity', item.id::text, 'market_pattern', item.market_pattern_id::text,
      'addresses_pattern', NULL, jsonb_build_object('source','saas_opportunities')
    );
  END LOOP;

  FOR item IN SELECT id, opportunity_id, market_pattern_id,
      opportunity_name_snapshot, opportunity_summary_snapshot, approval_status,
      assessment_confidence, weighted_score, approved_at, approved_by
    FROM public.opportunity_assessments LOOP
    PERFORM public.upsert_intelligence_entity(
      'opportunity_assessment', item.id::text, NULL,
      item.opportunity_name_snapshot, item.opportunity_summary_snapshot,
      item.approval_status, item.assessment_confidence,
      jsonb_build_object(
        'weighted_score',item.weighted_score,
        'approved_at',item.approved_at,
        'approved_by',item.approved_by
      )
    );
    PERFORM public.upsert_intelligence_relationship(
      'opportunity_assessment', item.id::text, 'saas_opportunity', item.opportunity_id::text,
      'evaluates_opportunity', item.assessment_confidence, '{}'::jsonb
    );
    PERFORM public.upsert_intelligence_relationship(
      'opportunity_assessment', item.id::text, 'market_pattern', item.market_pattern_id::text,
      'evaluates_pattern', item.assessment_confidence, '{}'::jsonb
    );
  END LOOP;

  FOR item IN SELECT market_pattern_id, company_pain_id
    FROM public.market_pattern_pains LOOP
    PERFORM public.upsert_intelligence_relationship(
      'market_pattern', item.market_pattern_id::text, 'company_pain', item.company_pain_id::text,
      'supported_by_pain', NULL, jsonb_build_object('source','market_pattern_pains')
    );
  END LOOP;

  FOR item IN SELECT evidence_id, source_domain, entity_type, entity_id, lead_id,
      snapshot_id, source_url, excerpt, evidence_type, source_kind, observed_at, captured_at
    FROM public.intelligence_evidence LOOP
    PERFORM public.upsert_intelligence_entity(
      'evidence', item.evidence_id, item.lead_id,
      left(item.excerpt,240), item.excerpt, item.evidence_type, NULL,
      jsonb_build_object(
        'source_url',item.source_url,
        'source_domain',item.source_domain,
        'source_kind',item.source_kind,
        'observed_at',item.observed_at,
        'captured_at',item.captured_at
      )
    );
    IF item.source_domain IN ('lead','company_dossier') THEN
      PERFORM public.upsert_intelligence_relationship(
        'evidence', item.evidence_id, 'company', item.entity_id,
        'evidence_for', NULL, jsonb_build_object('source_url',item.source_url)
      );
    ELSIF item.source_domain = 'opportunity' THEN
      PERFORM public.upsert_intelligence_relationship(
        'evidence', item.evidence_id, 'company_pain', item.entity_id,
        'evidence_for', NULL, jsonb_build_object('source_url',item.source_url)
      );
    END IF;
    IF item.snapshot_id <> '' THEN
      PERFORM public.upsert_intelligence_relationship(
        'evidence', item.evidence_id, 'company_dossier_snapshot', item.snapshot_id,
        'evidence_for', NULL, jsonb_build_object('source_url',item.source_url)
      );
    END IF;
  END LOOP;
END;
$graph_backfill$;

COMMENT ON TABLE public.intelligence_entities IS
  'Derived, queryable graph nodes for existing JARVIS business records; source tables remain authoritative.';
COMMENT ON TABLE public.intelligence_relationships IS
  'Derived, provenance-aware edges between JARVIS intelligence graph entities.';
COMMENT ON COLUMN public.intelligence_relationships.provenance IS
  'Machine-readable provenance for the relationship; AI-suggested edges are not written here as verified links.';

COMMIT;
