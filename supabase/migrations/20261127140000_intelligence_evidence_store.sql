-- Durable, source-linked evidence index shared by Lead, dossier and Opportunity domains.
-- Append-only index of evidence already present in domain records; no AI-generated sources.
BEGIN;

ALTER TABLE public.leads
  ADD COLUMN IF NOT EXISTS research_evidence jsonb NOT NULL DEFAULT '[]'::jsonb;

DO $lead_evidence_check$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'public.leads'::regclass
      AND conname = 'leads_research_evidence_array_check'
  ) THEN
    ALTER TABLE public.leads
      ADD CONSTRAINT leads_research_evidence_array_check
      CHECK (jsonb_typeof(research_evidence) = 'array');
  END IF;
END;
$lead_evidence_check$;

CREATE TABLE IF NOT EXISTS public.intelligence_evidence (
  evidence_id text PRIMARY KEY CHECK (length(evidence_id) BETWEEN 32 AND 64),
  source_domain text NOT NULL CHECK (source_domain IN ('lead','company_dossier','opportunity')),
  source_kind text NOT NULL CHECK (length(btrim(source_kind)) BETWEEN 1 AND 60),
  entity_type text NOT NULL CHECK (length(btrim(entity_type)) BETWEEN 1 AND 60),
  entity_id text NOT NULL DEFAULT '',
  lead_id uuid,
  snapshot_id text NOT NULL DEFAULT '',
  source_url text NOT NULL CHECK (source_url ~ '^https?://[^[:space:]]+$'),
  excerpt text NOT NULL CHECK (length(btrim(excerpt)) BETWEEN 1 AND 1200),
  evidence_type text NOT NULL DEFAULT 'supporting'
    CHECK (evidence_type IN ('supporting','contradicting','context')),
  observed_at text NOT NULL DEFAULT 'undated',
  captured_at text NOT NULL DEFAULT 'undated',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS intelligence_evidence_domain_time_idx
  ON public.intelligence_evidence (source_domain, created_at DESC);
CREATE INDEX IF NOT EXISTS intelligence_evidence_lead_idx
  ON public.intelligence_evidence (lead_id, created_at DESC);
CREATE INDEX IF NOT EXISTS intelligence_evidence_source_idx
  ON public.intelligence_evidence (source_url);

ALTER TABLE public.intelligence_evidence ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.intelligence_evidence FROM PUBLIC, anon, authenticated;
GRANT SELECT ON TABLE public.intelligence_evidence TO authenticated;
GRANT SELECT, INSERT ON TABLE public.intelligence_evidence TO service_role;
DROP POLICY IF EXISTS intelligence_evidence_shared_read ON public.intelligence_evidence;
CREATE POLICY intelligence_evidence_shared_read
  ON public.intelligence_evidence FOR SELECT TO authenticated
  USING ((SELECT auth.jwt() -> 'app_metadata' ->> 'role') IN ('admin','operator','reader'));

CREATE OR REPLACE FUNCTION public.capture_intelligence_evidence()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $intelligence_capture$
DECLARE
  item jsonb;
  evidence_array jsonb;
  v_domain text;
  v_kind text;
  v_entity_type text;
  v_entity_id text;
  v_lead_id uuid;
  v_snapshot_id text;
  v_url text;
  v_excerpt text;
  v_type text;
  v_observed text;
  v_captured text;
  v_id text;
BEGIN
  IF TG_TABLE_NAME = 'company_research_snapshots' THEN
    v_domain := 'company_dossier';
    v_kind := 'company_dossier_fact';
    v_entity_type := 'company';
    v_entity_id := NEW.lead_id::text;
    v_lead_id := NEW.lead_id;
    v_snapshot_id := NEW.snapshot_id::text;
    evidence_array := NEW.dossier -> 'evidence_records';
  ELSIF TG_TABLE_NAME = 'business_pain_hypotheses' THEN
    v_domain := 'opportunity';
    v_kind := 'company_pain_hypothesis';
    v_entity_type := 'company_pain_hypothesis';
    v_entity_id := NEW.id::text;
    v_lead_id := NEW.lead_id;
    v_snapshot_id := COALESCE(NEW.snapshot_id::text, '');
    evidence_array := NEW.evidence;
  ELSE
    v_domain := 'lead';
    v_kind := 'lead_research_note';
    v_entity_type := 'lead';
    v_entity_id := NEW.id::text;
    v_lead_id := NEW.id;
    v_snapshot_id := '';
    evidence_array := NEW.research_evidence;
  END IF;

  IF jsonb_typeof(evidence_array) IS DISTINCT FROM 'array' THEN
    RETURN NEW;
  END IF;

  FOR item IN SELECT value FROM jsonb_array_elements(evidence_array)
  LOOP
    v_url := btrim(COALESCE(item ->> 'source_url',''));
    v_excerpt := btrim(COALESCE(item ->> 'excerpt',''));
    IF v_url !~ '^https?://[^[:space:]]+$'
      OR length(v_excerpt) NOT BETWEEN 1 AND 1200
      OR item ->> 'evidence_type' IS NOT NULL
        AND item ->> 'evidence_type' NOT IN ('supporting','contradicting','context')
    THEN
      CONTINUE;
    END IF;
    v_type := COALESCE(item ->> 'evidence_type','supporting');
    v_observed := COALESCE(NULLIF(item ->> 'observed_at',''), 'undated');
    v_captured := COALESCE(NULLIF(item ->> 'captured_at',''), v_observed);
    v_id := COALESCE(
      NULLIF(item ->> 'evidence_id',''),
      md5(concat_ws('|', v_domain, v_entity_id, v_url, v_excerpt, v_observed, v_type))
    );
    INSERT INTO public.intelligence_evidence (
      evidence_id, source_domain, source_kind, entity_type, entity_id,
      lead_id, snapshot_id, source_url, excerpt, evidence_type,
      observed_at, captured_at
    ) VALUES (
      v_id, v_domain, COALESCE(NULLIF(item ->> 'source_kind',''), v_kind),
      COALESCE(NULLIF(item ->> 'entity_type',''), v_entity_type),
      COALESCE(NULLIF(item ->> 'entity_id',''), v_entity_id),
      v_lead_id, COALESCE(NULLIF(item ->> 'snapshot_id',''), v_snapshot_id),
      v_url, v_excerpt, v_type, v_observed, v_captured
    )
    ON CONFLICT (evidence_id) DO NOTHING;
  END LOOP;
  RETURN NEW;
END;
$intelligence_capture$;

REVOKE ALL ON FUNCTION public.capture_intelligence_evidence() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.capture_intelligence_evidence() TO service_role;

DROP TRIGGER IF EXISTS capture_dossier_intelligence_evidence ON public.company_research_snapshots;
CREATE TRIGGER capture_dossier_intelligence_evidence
AFTER INSERT OR UPDATE OF dossier ON public.company_research_snapshots
FOR EACH ROW EXECUTE FUNCTION public.capture_intelligence_evidence();

DROP TRIGGER IF EXISTS capture_pain_intelligence_evidence ON public.business_pain_hypotheses;
CREATE TRIGGER capture_pain_intelligence_evidence
AFTER INSERT OR UPDATE OF evidence ON public.business_pain_hypotheses
FOR EACH ROW EXECUTE FUNCTION public.capture_intelligence_evidence();

DROP TRIGGER IF EXISTS capture_lead_intelligence_evidence ON public.leads;
CREATE TRIGGER capture_lead_intelligence_evidence
AFTER INSERT OR UPDATE OF research_evidence ON public.leads
FOR EACH ROW EXECUTE FUNCTION public.capture_intelligence_evidence();

-- Backfill only explicitly structured, source-linked records already stored.
-- Replaying the source triggers captures existing snapshot and pain evidence too.
UPDATE public.company_research_snapshots SET dossier = dossier
WHERE jsonb_typeof(dossier -> 'evidence_records') = 'array';
UPDATE public.business_pain_hypotheses SET evidence = evidence
WHERE jsonb_typeof(evidence) = 'array';
DO $intelligence_backfill$
DECLARE
  row_data record;
BEGIN
  FOR row_data IN
    SELECT id, lead_id, research_evidence FROM public.leads
    WHERE jsonb_typeof(research_evidence) = 'array'
  LOOP
    PERFORM 1;
    -- Reuse the same trigger contract without rewriting the source row.
    INSERT INTO public.intelligence_evidence (
      evidence_id, source_domain, source_kind, entity_type, entity_id, lead_id,
      source_url, excerpt, evidence_type, observed_at, captured_at
    )
    SELECT
      COALESCE(NULLIF(item ->> 'evidence_id',''),
        md5(concat_ws('|','lead',row_data.id::text,item ->> 'source_url',item ->> 'excerpt',
          COALESCE(item ->> 'observed_at','undated'),COALESCE(item ->> 'evidence_type','supporting')))),
      'lead', COALESCE(item ->> 'source_kind','lead_research_note'), 'lead',
      row_data.id::text, row_data.id, item ->> 'source_url', item ->> 'excerpt',
      COALESCE(item ->> 'evidence_type','supporting'),
      COALESCE(item ->> 'observed_at','undated'), COALESCE(item ->> 'captured_at',item ->> 'observed_at','undated')
    FROM jsonb_array_elements(row_data.research_evidence) item
    WHERE COALESCE(item ->> 'source_url','') ~ '^https?://[^[:space:]]+$'
      AND length(btrim(COALESCE(item ->> 'excerpt',''))) BETWEEN 1 AND 1200
    ON CONFLICT (evidence_id) DO NOTHING;
  END LOOP;
END;
$intelligence_backfill$;

COMMIT;
