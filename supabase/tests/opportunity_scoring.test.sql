-- Run only against the isolated PostgreSQL integration fixtures.
BEGIN;
SELECT plan(9);
SELECT ok(
  (SELECT count(*) = 10 FROM information_schema.columns
   WHERE table_schema='public' AND table_name='saas_opportunities'
     AND column_name IN ('scoring_status','score_problem_evidence','score_business_value',
       'score_willingness_to_pay','score_feasibility','score_reusability','score_risk',
       'assessment_confidence','score_rationale','weighted_score')),
  'opportunity scoring columns are installed'
);
INSERT INTO public.leads (company_name, website)
VALUES ('Opportunity scoring fixture','https://scoring.invalid')
RETURNING id \gset scoring_lead_
INSERT INTO public.market_problem_patterns (title, confidence)
VALUES ('Scoring fixture pattern',0.7)
RETURNING id \gset scoring_pattern_
INSERT INTO public.saas_opportunities (market_pattern_id,name,summary)
VALUES (:'scoring_pattern_id','Unscored candidate','Awaiting adequate evidence')
RETURNING id \gset unscored_
SELECT is((SELECT scoring_status FROM public.saas_opportunities WHERE id=:'unscored_id'),
          'insufficient_evidence', 'new opportunities default to insufficient evidence');
SELECT is((SELECT weighted_score FROM public.saas_opportunities WHERE id=:'unscored_id'),
          NULL::numeric, 'incomplete assessments do not receive a numeric score');
INSERT INTO public.saas_opportunities (
  market_pattern_id,name,summary,scoring_status,score_problem_evidence,score_business_value,
  score_willingness_to_pay,score_feasibility,score_reusability,score_risk,
  assessment_confidence,score_rationale
) VALUES (
  :'scoring_pattern_id','Scored candidate','Complete explained assessment','scored',
  80,70,60,90,80,20,0.82,
  '{"problem_evidence":"Two independent company records","business_value":"Estimated workflow savings","willingness_to_pay":"Budget signal observed","feasibility":"Existing APIs are sufficient","reusability":"Common workflow across sectors","risk":"Moderate data integration risk"}'::jsonb
) RETURNING id \gset scored_
SELECT is((SELECT weighted_score FROM public.saas_opportunities WHERE id=:'scored_id'),
          76.50::numeric, 'generated score applies documented weights and risk penalty');
SELECT throws_ok(
  'INSERT INTO public.saas_opportunities (market_pattern_id,name,summary,scoring_status,score_problem_evidence) VALUES (' ||
  quote_literal(:'scoring_pattern_id') || ',''Partial'',''Partial score'',''scored'',80)',
  '23514', NULL, 'partial scoring is rejected'
);
SELECT throws_ok(
  'INSERT INTO public.saas_opportunities (market_pattern_id,name,summary,score_problem_evidence) VALUES (' ||
  quote_literal(:'scoring_pattern_id') || ',''Out of range'',''Invalid score'',101)',
  '23514', NULL, 'score values above 100 are rejected'
);
SELECT throws_ok(
  'INSERT INTO public.saas_opportunities (market_pattern_id,name,summary,scoring_status,score_problem_evidence,score_business_value,score_willingness_to_pay,score_feasibility,score_reusability,score_risk,assessment_confidence,score_rationale) VALUES (' ||
  quote_literal(:'scoring_pattern_id') || ',''No rationale'',''Missing rationale'',''scored'',80,70,60,90,80,20,0.8,''{}''::jsonb)',
  '23514', NULL, 'scored assessment requires a rationale for every dimension'
);
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  '{"sub":"10000000-0000-0000-0000-000000000003","role":"authenticated","app_metadata":{"role":"reader"}}',true);
SELECT is((SELECT weighted_score FROM public.saas_opportunities WHERE id=:'scored_id'),
          76.50::numeric, 'reader role can inspect calculated scores');
SELECT throws_ok(
  'UPDATE public.saas_opportunities SET score_business_value=99 WHERE id=' || quote_literal(:'scored_id'),
  '42501', NULL, 'reader cannot modify opportunity assessments'
);
RESET ROLE;
SELECT * FROM finish();
ROLLBACK;
