CREATE TABLE public.lead_identity_race_control (
  singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
  company_name text NOT NULL,
  website text NOT NULL
);
INSERT INTO public.lead_identity_race_control(singleton, company_name, website)
VALUES (
  true,
  'JARVIS concurrency fixture ' || replace(gen_random_uuid()::text, '-', ''),
  'https://race-' || replace(gen_random_uuid()::text, '-', '') || '.example.invalid'
);

GRANT SELECT ON public.lead_identity_race_control TO service_role;
