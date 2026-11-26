-- Finalize the rolling deployment: all application instances must call
-- upsert_company_lead before this migration is applied.
-- Re-scan under a write lock so any legacy inserts made during the compatible
-- rollout window receive aliases before direct INSERT is revoked.
BEGIN;

LOCK TABLE public.leads IN SHARE ROW EXCLUSIVE MODE;

DO $company_write_lockdown_preflight$
DECLARE
  duplicate_names bigint;
  duplicate_domains bigint;
  duplicate_emails bigint;
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

  SELECT count(*) INTO duplicate_emails
  FROM (
    SELECT lower(btrim(email))
    FROM public.leads
    WHERE email IS NOT NULL AND btrim(email) <> ''
    GROUP BY lower(btrim(email))
    HAVING count(*) > 1
  ) d;

  IF duplicate_names > 0 OR duplicate_domains > 0 OR duplicate_emails > 0 THEN
    RAISE EXCEPTION
      'Cannot enforce atomic company lead writes: duplicate name groups %, domain groups %, email groups %. Review manually; no rows were changed.',
      duplicate_names, duplicate_domains, duplicate_emails;
  END IF;
END
$company_write_lockdown_preflight$;

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

-- The deployed application uses the RPC for inserts; direct writes are closed.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
  ON TABLE public.leads FROM service_role;
GRANT SELECT ON TABLE public.leads TO service_role;

-- Keep routine CRM status/outreach updates, but only the SECURITY DEFINER
-- company RPC may change company identity, selected email or consent proof.
DO $lead_update_column_grants$
DECLARE
  update_columns text;
BEGIN
  SELECT string_agg(format('%I', column_name), ', ' ORDER BY ordinal_position)
    INTO update_columns
  FROM information_schema.columns
  WHERE table_schema = 'public'
    AND table_name = 'leads'
    AND column_name NOT IN (
      'id', 'company_name', 'website', 'email',
      'consent_basis', 'approved_to_contact', 'consent_confirmed_at',
      'created_at'
    );

  IF update_columns IS NOT NULL THEN
    EXECUTE format(
      'GRANT UPDATE (%s) ON TABLE public.leads TO service_role',
      update_columns
    );
  END IF;
END
$lead_update_column_grants$;

COMMIT;
