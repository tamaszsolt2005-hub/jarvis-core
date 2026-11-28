-- Isolated PostgreSQL integration test for human-approved opportunity snapshots.
BEGIN;
SELECT plan(10);

SELECT has_table('public','opportunity_assessments',
  'append-only opportunity assessment history exists');

INSERT INTO public.leads (company_name, website)
VALUES ('Approval fixture one','https://approval-one.invalid')
RETURNING id \gset approval_lead_one_
INSERT INTO public.leads (company_name, website)
VALUES ('Approval fixture two','https://approval-two.invalid')
RETURNING id \gset approval_lead_two_

INSERT INTO public.business_pain_hypotheses (lead_id,statement,confidence,status,evidence)
VALUES (:'approval_lead_one_id','Manual reconciliation is repeated',0.8,'supported',
  '[{"source_url":"https://source-one.invalid/report","excerpt":"Manual reconciliation takes several hours each week."}]'::jsonb)
RETURNING id \gset approval_pain_one_
INSERT INTO public.business_pain_hypotheses (lead_id,statement,confidence,status,evidence)
VALUES (:'approval_lead_two_id','Manual reconciliation is repeated',0.75,'supported',
  '[{"source_url":"https://source-two.invalid/report","excerpt":"The finance team manually reconciles the same records."}]'::jsonb)
RETURNING id \gset approval_pain_two_

INSERT INTO public.market_problem_patterns (title,description,confidence)
VALUES ('Cross-company reconciliation','Repeated manual finance reconciliation',0.8)
RETURNING id \gset approval_pattern_
INSERT INTO public.market_pattern_pains (market_pattern_id,company_pain_id)
VALUES (:'approval_pattern_id',:'approval_pain_one_id'),
       (:'approval_pattern_id',:'approval_pain_two_id');
UPDATE public.market_problem_patterns SET status='validated' WHERE id=:'approval_pattern_id';

INSERT INTO public.saas_opportunities (market_pattern_id,name,summary)
VALUES (:'approval_pattern_id','Reconciliation SaaS','Automates recurring reconciliation')
RETURNING id \gset approval_opportunity_

INSERT INTO public.saas_opportunities (market_pattern_id,name,summary,status)
VALUES (:'approval_pattern_id','Rejected reconciliation candidate','Previously rejected idea','rejected')
RETURNING id \gset rejected_opportunity_

SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  '{"sub":"10000000-0000-0000-0000-000000000091","role":"authenticated","app_metadata":{"role":"operator"}}',true);

INSERT INTO public.opportunity_assessments (
  opportunity_id,market_pattern_id,idempotency_key,
  score_problem_evidence,score_business_value,score_willingness_to_pay,
  score_feasibility,score_reusability,score_risk,assessment_confidence,
  score_rationale,score_evidence,evaluator_model,evaluator_version
) VALUES (
  :'approval_opportunity_id',:'approval_pattern_id',
  '10000000-0000-0000-0000-000000000092',
  80,70,60,90,80,20,0.82,
  '{"problem_evidence":"Two company sources","business_value":"Repeated work","willingness_to_pay":"Budget signal","feasibility":"Known integrations","reusability":"Shared workflow","risk":"Manageable risk"}'::jsonb,
  jsonb_build_object(
    'problem_evidence',jsonb_build_array(
      jsonb_build_object('pain_hypothesis_id',:'approval_pain_one_id','source_url','https://source-one.invalid/report','excerpt','Manual reconciliation takes several hours each week.','observed_at','undated','evidence_type','supporting'),
      jsonb_build_object('pain_hypothesis_id',:'approval_pain_two_id','source_url','https://source-two.invalid/report','excerpt','The finance team manually reconciles the same records.','observed_at','undated','evidence_type','supporting')),
    'business_value',jsonb_build_array(jsonb_build_object('pain_hypothesis_id',:'approval_pain_one_id','source_url','https://source-one.invalid/report','excerpt','Manual reconciliation takes several hours each week.','observed_at','undated','evidence_type','supporting')),
    'willingness_to_pay',jsonb_build_array(jsonb_build_object('pain_hypothesis_id',:'approval_pain_two_id','source_url','https://source-two.invalid/report','excerpt','The finance team manually reconciles the same records.','observed_at','undated','evidence_type','supporting')),
    'feasibility',jsonb_build_array(jsonb_build_object('pain_hypothesis_id',:'approval_pain_one_id','source_url','https://source-one.invalid/report','excerpt','Manual reconciliation takes several hours each week.','observed_at','undated','evidence_type','supporting')),
    'reusability',jsonb_build_array(jsonb_build_object('pain_hypothesis_id',:'approval_pain_two_id','source_url','https://source-two.invalid/report','excerpt','The finance team manually reconciles the same records.','observed_at','undated','evidence_type','supporting')),
    'risk',jsonb_build_array(jsonb_build_object('pain_hypothesis_id',:'approval_pain_one_id','source_url','https://source-one.invalid/report','excerpt','Manual reconciliation takes several hours each week.','observed_at','undated','evidence_type','supporting'))
  ),
  'test-model','opportunity-evaluator-v1'
);

SELECT is((SELECT weighted_score FROM public.opportunity_assessments
           WHERE idempotency_key='10000000-0000-0000-0000-000000000092'),
          76.50::numeric,'approved snapshot calculates its own weighted score');

SELECT throws_ok(
  format(
    'INSERT INTO public.opportunity_assessments (opportunity_id,market_pattern_id,idempotency_key,score_problem_evidence,score_business_value,score_willingness_to_pay,score_feasibility,score_reusability,score_risk,assessment_confidence,score_rationale,score_evidence,evaluator_model,evaluator_version) SELECT %L,market_pattern_id,%L,score_problem_evidence,score_business_value,score_willingness_to_pay,score_feasibility,score_reusability,score_risk,assessment_confidence,score_rationale,score_evidence,evaluator_model,evaluator_version FROM public.opportunity_assessments LIMIT 1',
    :'rejected_opportunity_id','10000000-0000-0000-0000-000000000095'
  ),
  '23514',NULL,'rejected SaaS candidates cannot receive approved assessments'
);
SELECT is((SELECT approved_by::text FROM public.opportunity_assessments
           WHERE idempotency_key='10000000-0000-0000-0000-000000000092'),
          '10000000-0000-0000-0000-000000000091','approval actor is derived from the authenticated user');
SELECT is((SELECT approval_status FROM public.opportunity_assessments
           WHERE idempotency_key='10000000-0000-0000-0000-000000000092'),
          'approved','inserted assessment is explicitly recorded as approved');
SELECT throws_ok(
  'INSERT INTO public.opportunity_assessments (opportunity_id,market_pattern_id,idempotency_key,score_problem_evidence,score_business_value,score_willingness_to_pay,score_feasibility,score_reusability,score_risk,assessment_confidence,score_rationale,score_evidence,evaluator_model,evaluator_version) SELECT opportunity_id,market_pattern_id,idempotency_key,score_problem_evidence,score_business_value,score_willingness_to_pay,score_feasibility,score_reusability,score_risk,assessment_confidence,score_rationale,score_evidence,evaluator_model,evaluator_version FROM public.opportunity_assessments WHERE idempotency_key = ''10000000-0000-0000-0000-000000000092''',
  '23505',NULL,'duplicate approval idempotency key is rejected'
);
RESET ROLE;

SELECT throws_ok(
  'UPDATE public.opportunity_assessments SET evaluator_model=''tampered'' WHERE idempotency_key=''10000000-0000-0000-0000-000000000092''',
  '55000',NULL,'approved assessments cannot be updated, even by the table owner'
);
SELECT throws_ok(
  'DELETE FROM public.opportunity_assessments WHERE idempotency_key=''10000000-0000-0000-0000-000000000092''',
  '55000',NULL,'approved assessments cannot be deleted, even by the table owner'
);

SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  '{"sub":"10000000-0000-0000-0000-000000000093","role":"authenticated","app_metadata":{"role":"reader"}}',true);
SELECT is((SELECT count(*)::integer FROM public.opportunity_assessments),1,
  'reader can inspect approved assessment history');
SELECT throws_ok(
  'INSERT INTO public.opportunity_assessments (opportunity_id,market_pattern_id,idempotency_key,score_problem_evidence,score_business_value,score_willingness_to_pay,score_feasibility,score_reusability,score_risk,assessment_confidence,score_rationale,score_evidence,evaluator_model,evaluator_version) SELECT opportunity_id,market_pattern_id,''10000000-0000-0000-0000-000000000094'',score_problem_evidence,score_business_value,score_willingness_to_pay,score_feasibility,score_reusability,score_risk,assessment_confidence,score_rationale,score_evidence,evaluator_model,evaluator_version FROM public.opportunity_assessments LIMIT 1',
  '42501',NULL,'reader cannot approve or insert assessments'
);
SELECT throws_ok(
  'UPDATE public.opportunity_assessments SET evaluator_model=''tampered''',
  '42501',NULL,'reader cannot update approved assessments'
);
RESET ROLE;

SELECT * FROM finish();
ROLLBACK;
