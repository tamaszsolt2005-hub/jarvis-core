-- One CRM lead per company, with all consented contact candidates retained.
-- Company identity aliases are claimed atomically; conflicting legacy identities stop
-- the migration instead of silently merging or deleting customer data.
BEGIN;

-- Freeze legacy lead writes while identity aliases are backfilled.
LOCK TABLE public.leads IN SHARE ROW EXCLUSIVE MODE;

CREATE OR REPLACE FUNCTION public.normalize_lead_company_name(p_name text)
RETURNS text
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
SET search_path = pg_catalog
AS $$
  SELECT nullif(regexp_replace(lower(btrim(coalesce(p_name, ''))), '\\s+', ' ', 'g'), '');
$$;

CREATE OR REPLACE FUNCTION public.normalize_lead_company_domain(p_website text)
RETURNS text
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
SET search_path = pg_catalog
AS $$
  SELECT nullif(
    regexp_replace(
      regexp_replace(
        regexp_replace(
          split_part(
            regexp_replace(btrim(coalesce(p_website, '')), '^https?://', '', 'i'),
            '/', 1
          ),
          '[?#].*$', ''
        ),
        '^www\\.', '', 'i'
      ),
      ':[0-9]+$', ''
    ),
    ''
  );
$$;

CREATE TABLE IF NOT EXISTS public.lead_company_aliases (
  alias_type text NOT NULL CHECK (alias_type IN ('name', 'domain')),
  alias_value text NOT NULL CHECK (btrim(alias_value) <> ''),
  lead_id uuid NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (alias_type, alias_value),
  UNIQUE (lead_id, alias_type, alias_value)
);

CREATE INDEX IF NOT EXISTS lead_company_aliases_lead_id_idx
  ON public.lead_company_aliases(lead_id);

CREATE TABLE IF NOT EXISTS public.lead_contact_candidates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id uuid NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
  email text NOT NULL,
  email_normalized text GENERATED ALWAYS AS (lower(btrim(email))) STORED,
  priority_score integer NOT NULL,
  consent_basis text NOT NULL CHECK (consent_basis = 'consent'),
  approved_to_contact boolean NOT NULL CHECK (approved_to_contact),
  consent_confirmed_at timestamptz NOT NULL,
  opted_out boolean NOT NULL DEFAULT false,
  source text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT lead_contact_candidates_email_format
    CHECK (email_normalized ~ '^[^[:space:]@]+@[^[:space:]@]+\\.[^[:space:]@]+$'),
  CONSTRAINT lead_contact_candidates_email_unique UNIQUE (email_normalized)
);

CREATE INDEX IF NOT EXISTS lead_contact_candidates_rank_idx
  ON public.lead_contact_candidates(lead_id, priority_score DESC, created_at, email_normalized);

ALTER TABLE public.lead_company_aliases ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lead_contact_candidates ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.lead_company_aliases
  FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON TABLE public.lead_contact_candidates
  FROM PUBLIC, anon, authenticated, service_role;
GRANT USAGE ON SCHEMA public TO service_role;
GRANT SELECT, UPDATE, DELETE ON TABLE public.leads TO service_role;
REVOKE INSERT ON TABLE public.leads FROM service_role;

-- Refuse ambiguous legacy data. No existing lead is deleted or merged.
DO $company_identity_preflight$
DECLARE
  duplicate_names bigint;
  duplicate_domains bigint;
  duplicate_contact_emails bigint;
BEGIN
  SELECT count(*) INTO duplicate_names
  FROM (
    SELECT public.normalize_lead_company_name(company_name)
    FROM public.leads
    GROUP BY public.normalize_lead_company_name(company_name)
    HAVING count(*) > 1
  ) d;

  SELECT count(*) INTO duplicate_domains
  FROM (
    SELECT public.normalize_lead_company_domain(website)
    FROM public.leads
    WHERE public.normalize_lead_company_domain(website) IS NOT NULL
    GROUP BY public.normalize_lead_company_domain(website)
    HAVING count(*) > 1
  ) d;

  SELECT count(*) INTO duplicate_contact_emails
  FROM (
    SELECT lower(btrim(email))
    FROM public.leads
    WHERE email IS NOT NULL AND btrim(email) <> ''
    GROUP BY lower(btrim(email))
    HAVING count(*) > 1
  ) d;

  IF duplicate_names > 0 OR duplicate_domains > 0 OR duplicate_contact_emails > 0 THEN
    RAISE EXCEPTION
      'Cannot install company identity registry: duplicate name groups %, domain groups %, email groups %. Review and resolve manually; no rows were changed.',
      duplicate_names, duplicate_domains, duplicate_contact_emails;
  END IF;
END
$company_identity_preflight$;

INSERT INTO public.lead_company_aliases(alias_type, alias_value, lead_id)
SELECT 'name', public.normalize_lead_company_name(company_name), id
FROM public.leads
WHERE public.normalize_lead_company_name(company_name) IS NOT NULL
ON CONFLICT (alias_type, alias_value) DO NOTHING;

INSERT INTO public.lead_company_aliases(alias_type, alias_value, lead_id)
SELECT 'domain', public.normalize_lead_company_domain(website), id
FROM public.leads
WHERE public.normalize_lead_company_domain(website) IS NOT NULL
ON CONFLICT (alias_type, alias_value) DO NOTHING;

CREATE OR REPLACE FUNCTION public.lead_email_priority_score(p_email text)
RETURNS integer
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
SET search_path = pg_catalog
AS $$
  SELECT CASE
    WHEN split_part(lower(btrim(coalesce(p_email, ''))), '@', 1) IN
      ('info','info1','contact','office','admin','sales','support','hello',
       'marketing','booking','reception','customer.service','customerservice',
       'noreply','no-reply','webmaster')
      THEN 10
    WHEN split_part(lower(btrim(coalesce(p_email, ''))), '@', 2) IN
      ('gmail.com','googlemail.com','outlook.com','hotmail.com','live.com',
       'yahoo.com','yahoo.co.uk','icloud.com','me.com','proton.me','protonmail.com')
      THEN 120
    ELSE 90
  END;
$$;

-- Preserve existing, individually consented recipients as ranked candidates.
INSERT INTO public.lead_contact_candidates (
  lead_id, email, priority_score, consent_basis, approved_to_contact,
  consent_confirmed_at, opted_out, source
)
SELECT l.id, lower(btrim(l.email)), public.lead_email_priority_score(l.email),
       'consent', true, l.consent_confirmed_at, false, l.source
FROM public.leads l
WHERE l.email IS NOT NULL
  AND btrim(l.email) <> ''
  AND l.consent_basis = 'consent'
  AND l.approved_to_contact
  AND l.consent_confirmed_at IS NOT NULL
  AND NOT l.opted_out
ON CONFLICT (email_normalized) DO NOTHING;

-- The RPC is the only supported lead-creation path for research and reviewed CSV
-- imports. It serializes both name and website aliases, preserves all consented
-- candidate addresses, and never changes a recipient after outreach has begun.
CREATE OR REPLACE FUNCTION public.upsert_company_lead(
  p_company_name text,
  p_website text DEFAULT NULL,
  p_email text DEFAULT NULL,
  p_notes text DEFAULT NULL,
  p_source text DEFAULT NULL,
  p_consent_basis text DEFAULT NULL,
  p_approved_to_contact boolean DEFAULT false,
  p_consent_confirmed_at timestamptz DEFAULT NULL
)
RETURNS TABLE(lead_id uuid, outcome text, selected_email text)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $
DECLARE
  v_name text;
  v_domain text;
  v_alias_key text;
  v_alias record;
  v_lead_id uuid;
  v_match_count integer;
  v_match_ids uuid[];
  v_candidate_email text;
  v_candidate_score integer;
  v_existing_domain text;
  v_has_outreach boolean;
BEGIN
  v_name := public.normalize_lead_company_name(p_company_name);
  v_domain := public.normalize_lead_company_domain(p_website);

  IF v_name IS NULL OR char_length(v_name) > 250 THEN
    RAISE EXCEPTION 'A valid company name is required' USING ERRCODE = '22023';
  END IF;

  IF p_email IS NOT NULL AND btrim(p_email) <> '' THEN
    IF lower(btrim(coalesce(p_consent_basis, ''))) <> 'consent'
       OR p_approved_to_contact IS DISTINCT FROM true
       OR p_consent_confirmed_at IS NULL
       OR p_consent_confirmed_at > clock_timestamp()
       OR lower(btrim(p_email)) !~ '^[^[:space:]@]+@[^[:space:]@]+\\.[^[:space:]@]+$' THEN
      RAISE EXCEPTION 'A selected contact email requires its own valid, timestamped consent'
        USING ERRCODE = '22023';
    END IF;
    IF char_length(btrim(p_email)) > 254 THEN
      RAISE EXCEPTION 'Contact email is too long' USING ERRCODE = '22023';
    END IF;
  END IF;

  -- Acquire all identity locks in a stable order to avoid deadlocks.
  FOR v_alias IN
    SELECT alias_type, alias_value,
           alias_type || ':' || alias_value AS lock_key
    FROM (
      SELECT 'name'::text AS alias_type, v_name AS alias_value
      UNION
      SELECT 'domain'::text, v_domain WHERE v_domain IS NOT NULL
    ) aliases
    ORDER BY lock_key
  LOOP
    PERFORM pg_advisory_xact_lock(hashtextextended(v_alias.lock_key, 0));
  END LOOP;

  SELECT array_agg(DISTINCT a.lead_id), count(DISTINCT a.lead_id)
    INTO v_match_ids, v_match_count
  FROM public.lead_company_aliases a
  WHERE (a.alias_type = 'name' AND a.alias_value = v_name)
     OR (v_domain IS NOT NULL AND a.alias_type = 'domain' AND a.alias_value = v_domain);

  IF v_match_count > 1 THEN
    RAISE EXCEPTION 'Company name and website resolve to different existing leads; manual identity review required'
      USING ERRCODE = '23505';
  END IF;

  IF v_match_count = 1 THEN
    v_lead_id := v_match_ids[1];

    -- Same normalized name with a different already-registered website is
    -- ambiguous; do not silently merge two legal entities or branches.
    IF v_domain IS NOT NULL THEN
      SELECT a.alias_value INTO v_existing_domain
      FROM public.lead_company_aliases a
      WHERE a.lead_id = v_lead_id AND a.alias_type = 'domain'
      LIMIT 1;
      IF v_existing_domain IS NOT NULL AND v_existing_domain <> v_domain THEN
        RAISE EXCEPTION 'Company name matches, but the registered website differs; manual identity review required'
          USING ERRCODE = '23505';
      END IF;
    END IF;
  ELSE
    INSERT INTO public.leads (
      company_name, email, website, notes, source, status,
      consent_basis, approved_to_contact, consent_confirmed_at, opted_out
    )
    VALUES (
      btrim(p_company_name), NULL, nullif(btrim(coalesce(p_website, '')), ''),
      nullif(btrim(coalesce(p_notes, '')), ''),
      nullif(btrim(coalesce(p_source, '')), ''),
      CASE WHEN p_email IS NULL OR btrim(p_email) = '' THEN 'research' ELSE 'new' END,
      NULL, false, NULL, false
    )
    RETURNING id INTO v_lead_id;
  END IF;

  INSERT INTO public.lead_company_aliases(alias_type, alias_value, lead_id)
  VALUES ('name', v_name, v_lead_id)
  ON CONFLICT (alias_type, alias_value) DO NOTHING;

  IF v_domain IS NOT NULL THEN
    INSERT INTO public.lead_company_aliases(alias_type, alias_value, lead_id)
    VALUES ('domain', v_domain, v_lead_id)
    ON CONFLICT (alias_type, alias_value) DO NOTHING;
  END IF;

  IF p_email IS NOT NULL AND btrim(p_email) <> '' THEN
    v_candidate_score := public.lead_email_priority_score(p_email);

    INSERT INTO public.lead_contact_candidates (
      lead_id, email, priority_score, consent_basis, approved_to_contact,
      consent_confirmed_at, opted_out, source
    )
    VALUES (
      v_lead_id, lower(btrim(p_email)), v_candidate_score, 'consent', true,
      p_consent_confirmed_at, false, nullif(btrim(coalesce(p_source, '')), '')
    )
    ON CONFLICT (email_normalized) DO NOTHING;

    IF EXISTS (
      SELECT 1 FROM public.lead_contact_candidates c
      WHERE c.email_normalized = lower(btrim(p_email))
        AND c.lead_id <> v_lead_id
    ) THEN
      RAISE EXCEPTION 'This contact email is already assigned to another company lead'
        USING ERRCODE = '23505';
    END IF;

    SELECT c.email, c.priority_score
      INTO v_candidate_email, v_candidate_score
    FROM public.lead_contact_candidates c
    WHERE c.lead_id = v_lead_id
      AND c.approved_to_contact
      AND c.consent_basis = 'consent'
      AND c.consent_confirmed_at IS NOT NULL
      AND NOT c.opted_out
    ORDER BY c.priority_score DESC, c.created_at ASC, c.email_normalized ASC
    LIMIT 1;

    SELECT (
      l.first_sent_at IS NOT NULL
      OR l.last_message_id IS NOT NULL
      OR l.last_inbound_message_id IS NOT NULL
      OR l.reply_category IS NOT NULL
      OR l.opted_out
    ) INTO v_has_outreach
    FROM public.leads l WHERE l.id = v_lead_id FOR UPDATE;

    IF NOT coalesce(v_has_outreach, false) AND v_candidate_email IS NOT NULL THEN
      UPDATE public.leads
      SET email = v_candidate_email,
          consent_basis = 'consent',
          approved_to_contact = true,
          consent_confirmed_at = (
            SELECT c.consent_confirmed_at
            FROM public.lead_contact_candidates c
            WHERE c.lead_id = v_lead_id AND c.email_normalized = v_candidate_email
          ),
          opted_out = false,
          status = CASE WHEN status = 'research' THEN 'new' ELSE status END,
          updated_at = clock_timestamp()
      WHERE id = v_lead_id;
    END IF;
  END IF;

  RETURN QUERY
  SELECT v_lead_id,
         CASE WHEN v_match_count = 1 THEN 'existing' ELSE 'created' END,
         (SELECT l.email FROM public.leads l WHERE l.id = v_lead_id);
END;
$$;

REVOKE ALL ON FUNCTION public.normalize_lead_company_name(text)
  FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION public.normalize_lead_company_domain(text)
  FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION public.lead_email_priority_score(text)
  FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION public.upsert_company_lead(text,text,text,text,text,text,boolean,timestamptz)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.upsert_company_lead(text,text,text,text,text,text,boolean,timestamptz)
  TO service_role;

COMMIT;
