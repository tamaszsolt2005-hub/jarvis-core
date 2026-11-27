-- Run only against the isolated PostgreSQL integration fixtures.
BEGIN;
SELECT plan(18);

SELECT is(
  (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname='public'
     AND c.relname IN ('business_pain_hypotheses','market_problem_patterns','market_pattern_pains','saas_opportunities')
     AND c.relrowsecurity),
  4::bigint, 'all opportunity tables enforce row-level security'
);
SELECT is(
  (SELECT count(*) FROM unnest(ARRAY[
    'public.business_pain_hypotheses','public.market_problem_patterns',
    'public.market_pattern_pains','public.saas_opportunities'
  ]) AS relations(relation_name)
  WHERE has_table_privilege('anon',relation_name,'SELECT')
     OR has_table_privilege('anon',relation_name,'INSERT')
     OR has_table_privilege('anon',relation_name,'UPDATE')
     OR has_table_privilege('anon',relation_name,'DELETE')),
  0::bigint, 'anon has no opportunity-table privileges'
);
SELECT is(
  (SELECT count(*) FROM unnest(ARRAY[
    'public.business_pain_hypotheses','public.market_problem_patterns',
    'public.market_pattern_pains','public.saas_opportunities'
  ]) AS relations(relation_name)
  WHERE has_table_privilege('authenticated',relation_name,'SELECT')
    AND NOT has_table_privilege('authenticated',relation_name,'INSERT')
    AND NOT has_table_privilege('authenticated',relation_name,'UPDATE')
    AND NOT has_table_privilege('authenticated',relation_name,'DELETE')),
  4::bigint, 'authenticated has read-only table grants'
);
SELECT is(
  (SELECT count(*) FROM unnest(ARRAY[
    'public.business_pain_hypotheses','public.market_problem_patterns',
    'public.market_pattern_pains','public.saas_opportunities'
  ]) AS relations(relation_name)
  WHERE has_table_privilege('service_role',relation_name,'SELECT')
    AND has_table_privilege('service_role',relation_name,'INSERT')
    AND has_table_privilege('service_role',relation_name,'UPDATE')),
  4::bigint, 'service_role has backend read and write privileges'
);
SELECT ok(
  has_table_privilege('service_role','public.market_pattern_pains','DELETE'),
  'service_role can remove a stale evidence link so validated patterns can be downgraded'
);

INSERT INTO public.leads (company_name, website)
VALUES ('Opportunity fixture company','https://opportunity.invalid')
RETURNING id \gset opportunity_

INSERT INTO public.business_pain_hypotheses (lead_id, statement, confidence, evidence)
VALUES (:'opportunity_id', 'Manual reconciliation may be costly', 0.650,
        '[{"source_url":"https://example.invalid/report","excerpt":"Public evidence","evidence_type":"context"}]'::jsonb)
RETURNING id \gset pain_

INSERT INTO public.market_problem_patterns (title, description, confidence)
VALUES ('Repeated reconciliation workflow','Observed in multiple company records',0.700)
RETURNING id \gset pattern_

INSERT INTO public.market_pattern_pains (market_pattern_id, company_pain_id)
VALUES (:'pattern_id', :'pain_id');

SELECT throws_ok(
  'UPDATE public.market_problem_patterns SET status=''validated'' WHERE id=' ||
  quote_literal(:'pattern_id'),
  '23514', NULL, 'a one-company pattern cannot be marked validated'
);

INSERT INTO public.leads (company_name, website)
VALUES ('Second opportunity fixture company','https://opportunity-two.invalid')
RETURNING id \gset opportunity2_
INSERT INTO public.business_pain_hypotheses (lead_id, statement, confidence, evidence)
VALUES (:'opportunity2_id', 'The same manual reconciliation workflow appears here', 0.610,
        '[{"source_url":"https://example.invalid/second-report","excerpt":"Second company evidence","evidence_type":"supporting"}]'::jsonb)
RETURNING id \gset pain2_
INSERT INTO public.market_pattern_pains (market_pattern_id, company_pain_id)
VALUES (:'pattern_id', :'pain2_id');
UPDATE public.market_problem_patterns SET status='validated' WHERE id=:'pattern_id';
SELECT is((SELECT status FROM public.market_problem_patterns WHERE id=:'pattern_id'),
          'validated', 'pattern can be validated after two distinct companies are linked');
DELETE FROM public.market_pattern_pains
WHERE market_pattern_id=:'pattern_id' AND company_pain_id=:'pain2_id';
SELECT is((SELECT status FROM public.market_problem_patterns WHERE id=:'pattern_id'),
          'under_review', 'removing a company downgrades a validated pattern instead of blocking deletion');

INSERT INTO public.saas_opportunities (market_pattern_id, name, summary)
VALUES (:'pattern_id','Reconciliation SaaS','A product candidate linked to a recurring pattern');

SELECT is((SELECT count(*) FROM public.business_pain_hypotheses WHERE id=:'pain_id'),1::bigint,
          'company pain hypothesis can be persisted with evidence');
SELECT is((SELECT count(*) FROM public.market_pattern_pains WHERE market_pattern_id=:'pattern_id'),1::bigint,
          'market pattern links back to a concrete company pain');
SELECT is((SELECT count(*) FROM public.saas_opportunities WHERE market_pattern_id=:'pattern_id'),1::bigint,
          'SaaS opportunity must reference a market pattern');

SELECT throws_ok(
  'INSERT INTO public.business_pain_hypotheses (lead_id,statement,confidence) VALUES (' ||
  quote_literal(:'opportunity_id') || ',''Invalid confidence'',1.500)',
  '23514', NULL, 'confidence above one is rejected'
);
SELECT throws_ok(
  'INSERT INTO public.market_pattern_pains (market_pattern_id,company_pain_id) VALUES (' ||
  quote_literal(:'pattern_id') || ',gen_random_uuid())',
  '23503', NULL, 'pattern links cannot reference missing company pains'
);

SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  '{"sub":"10000000-0000-0000-0000-000000000003","role":"authenticated","app_metadata":{"role":"reader"}}',true);
SELECT is((SELECT count(*) FROM public.business_pain_hypotheses),1::bigint,
          'reader role can read company pain hypotheses');
SELECT is((SELECT count(*) FROM public.market_problem_patterns),1::bigint,
          'reader role can read market patterns');
SELECT is((SELECT count(*) FROM public.saas_opportunities),1::bigint,
          'reader role can read SaaS opportunities');
SELECT throws_ok(
  'INSERT INTO public.business_pain_hypotheses (lead_id,statement,confidence) VALUES (' ||
  quote_literal(:'opportunity_id') || ',''Reader write denied'',0.500)',
  '42501', NULL, 'reader cannot insert opportunity data'
);
SELECT throws_ok(
  'UPDATE public.market_problem_patterns SET title=''Reader changed'' WHERE id=' ||
  quote_literal(:'pattern_id'),
  '42501', NULL, 'reader cannot update market patterns'
);
RESET ROLE;

SELECT * FROM finish();
ROLLBACK;
