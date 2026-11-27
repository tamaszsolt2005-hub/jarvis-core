BEGIN;
SELECT plan(7);

SELECT ok(
  (SELECT relrowsecurity FROM pg_class WHERE oid='public.market_pattern_review_events'::regclass),
  'market pattern review events enforce RLS'
);
SELECT ok(
  NOT has_table_privilege('anon','public.market_pattern_review_events','SELECT')
  AND NOT has_table_privilege('anon','public.market_pattern_review_events','INSERT'),
  'anon cannot access market pattern review events'
);
SELECT ok(
  has_table_privilege('authenticated','public.market_pattern_review_events','SELECT')
  AND NOT has_table_privilege('authenticated','public.market_pattern_review_events','INSERT')
  AND NOT has_table_privilege('authenticated','public.market_pattern_review_events','UPDATE')
  AND NOT has_table_privilege('authenticated','public.market_pattern_review_events','DELETE'),
  'authenticated roles can read but cannot mutate review events'
);
SELECT ok(
  has_function_privilege('authenticated','public.review_market_pattern(uuid,text,text)','EXECUTE')
  AND NOT has_function_privilege('anon','public.review_market_pattern(uuid,text,text)','EXECUTE'),
  'only authenticated callers can invoke the role-checked review RPC'
);

INSERT INTO public.leads (company_name, website)
VALUES ('Pattern review fixture one','https://pattern-one.invalid')
RETURNING id \gset pattern_one_
INSERT INTO public.leads (company_name, website)
VALUES ('Pattern review fixture two','https://pattern-two.invalid')
RETURNING id \gset pattern_two_

INSERT INTO public.business_pain_hypotheses (lead_id,statement,category,confidence,evidence)
VALUES (:'pattern_one_id','Manual invoice reconciliation causes delays','finance',0.600,
        '[{"source_url":"https://pattern-one.invalid/report","excerpt":"Invoices are reconciled manually and delayed.","evidence_type":"supporting"}]'::jsonb)
RETURNING id \gset pattern_pain_one_
INSERT INTO public.business_pain_hypotheses (lead_id,statement,category,confidence,evidence)
VALUES (:'pattern_two_id','Manual invoice reconciliation takes several days','finance',0.620,
        '[{"source_url":"https://pattern-two.invalid/report","excerpt":"Invoices are reconciled manually over several days.","evidence_type":"supporting"}]'::jsonb)
RETURNING id \gset pattern_pain_two_

INSERT INTO public.market_problem_patterns (title,description,confidence,status)
VALUES ('Invoice reconciliation workflow','Two source-backed company hypotheses',0.610,'candidate')
RETURNING id \gset review_pattern_
INSERT INTO public.market_pattern_pains (market_pattern_id,company_pain_id)
VALUES (:'review_pattern_id',:'pattern_pain_one_id'), (:'review_pattern_id',:'pattern_pain_two_id');

SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  '{"sub":"10000000-0000-0000-0000-000000000003","role":"authenticated","app_metadata":{"role":"operator"}}',true);
SELECT lives_ok(
  'SELECT public.review_market_pattern(' || quote_literal(:'review_pattern_id') ||
  '::uuid,''validated'',''Két külön cég forrásolt problémája ellenőrizve.'')',
  'operator can validate a source-backed two-company market pattern'
);
SELECT is(
  (SELECT status FROM public.market_problem_patterns WHERE id=:'review_pattern_id'),
  'validated',
  'review RPC updates the market pattern status'
);
SELECT is(
  (SELECT count(*) FROM public.market_pattern_review_events WHERE market_pattern_id=:'review_pattern_id'),
  1::bigint,
  'review decision is stored in append-only audit history'
);
SELECT set_config('request.jwt.claims',
  '{"sub":"10000000-0000-0000-0000-000000000004","role":"authenticated","app_metadata":{"role":"reader"}}',true);
SELECT throws_ok(
  'SELECT public.review_market_pattern(' || quote_literal(:'review_pattern_id') ||
  '::uuid,''rejected'',''Reader must not decide.'')',
  '42501', NULL,
  'reader cannot review or change a market pattern'
);
RESET ROLE;

SELECT * FROM finish();
ROLLBACK;
