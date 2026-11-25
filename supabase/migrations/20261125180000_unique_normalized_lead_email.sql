-- Enforce case/whitespace-insensitive uniqueness for non-empty lead email addresses.
-- The table lock closes the gap between duplicate preflight and index creation.
-- Existing rows are never modified or deleted; conflicting data stops this migration.
BEGIN;

LOCK TABLE public.leads IN SHARE ROW EXCLUSIVE MODE;

DO $lead_email_preflight$
DECLARE
  duplicate_groups bigint;
BEGIN
  SELECT count(*)
    INTO duplicate_groups
    FROM (
      SELECT lower(btrim(email))
        FROM public.leads
       WHERE email IS NOT NULL
         AND btrim(email) <> ''
       GROUP BY lower(btrim(email))
      HAVING count(*) > 1
    ) duplicates;

  IF duplicate_groups > 0 THEN
    RAISE EXCEPTION
      'Cannot enforce unique lead emails: % duplicate normalized email group(s) exist. Resolve them manually, then retry this migration.',
      duplicate_groups;
  END IF;
END
$lead_email_preflight$;

CREATE UNIQUE INDEX IF NOT EXISTS leads_email_normalized_uidx
  ON public.leads (lower(btrim(email)))
  WHERE email IS NOT NULL AND btrim(email) <> '';

COMMIT;
