-- Isolated PostgreSQL integration test for SaaS candidate review lifecycle.
BEGIN;
SELECT plan(8);

SELECT has_table('public','saas_opportunity_review_events',
  'append-only SaaS opportunity review history exists');

INSERT INTO public.leads (company_name, website)
VALUES ('SaaS review fixture one','https://saas-review-one.invalid')
RETURNING id \gset saas_review_lead_one_
INSERT INTO public.leads (company_name, website)
VALUES ('SaaS review fixture two','https://saas-review-two.invalid')
RETURNING id \gset saas_review_lead_two_

INSERT INTO public.business_pain_hypotheses (lead_id,statement,confidence,status,evidence)
VALUES (:'saas_review_lead_one_id','Manual order reconciliation repeats',0.8,'supported',
  '[{"source_url":"https://saas-review-one.invalid/report","excerpt":"Orders are reconciled manually each day."}]'::jsonb)
RETURNING id \gset saas_review_pain_one_
INSERT INTO public.business_pain_hypotheses (lead_id,statement,confidence,status,evidence)
VALUES (:'saas_review_lead_two_id','Manual order reconciliation repeats',0.75,'supported',
  '[{"source_url":"https://saas-review-two.invalid/report","excerpt":"The team manually reconciles orders each day."}]'::jsonb)
RETURNING id \gset saas_review_pain_two_

INSERT INTO public.market_problem_patterns (title,description,confidence)
VALUES ('Repeated order reconciliation','A repeated manual order workflow',0.8)
RETURNING id \gset saas_review_pattern_
INSERT INTO public.market_pattern_pains (market_pattern_id,company_pain_id)
VALUES (:'saas_review_pattern_id',:'saas_review_pain_one_id'),
       (:'saas_review_pattern_id',:'saas_review_pain_two_id');

INSERT INTO public.saas_opportunities (market_pattern_id,name,summary)
VALUES (:'saas_review_pattern_id','Order reconciliation SaaS','Automates recurring order reconciliation')
RETURNING id \gset saas_review_candidate_
INSERT INTO public.saas_opportunities (market_pattern_id,name,summary,status)
VALUES (:'saas_review_pattern_id','Rejected order candidate','Rejected product hypothesis','rejected')
RETURNING id \gset saas_review_rejected_

SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  '{"sub":"10000000-0000-0000-0000-000000000101","role":"authenticated","app_metadata":{"role":"operator"}}',true);

SELECT ok(
  public.review_saas_opportunity(:'saas_review_candidate_id','under_review','Check demand and implementation evidence') IS NOT NULL,
  'operator can move a SaaS candidate into review'
);
SELECT is(
  (SELECT status FROM public.saas_opportunities WHERE id=:'saas_review_candidate_id'),
  'under_review','review decision updates candidate status'
);
SELECT throws_ok(
  format('SELECT public.review_saas_opportunity(%L,''shortlisted'',''Promote to shortlist after evidence'')', :'saas_review_candidate_id'),
  '23514',NULL,'candidate cannot be shortlisted before its pattern is validated'
);

RESET ROLE;
UPDATE public.market_problem_patterns SET status='validated' WHERE id=:'saas_review_pattern_id';
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  '{"sub":"10000000-0000-0000-0000-000000000101","role":"authenticated","app_metadata":{"role":"operator"}}',true);

SELECT ok(
  public.review_saas_opportunity(:'saas_review_candidate_id','shortlisted','Two companies support this reusable workflow') IS NOT NULL,
  'operator can shortlist a candidate backed by a validated multi-company pattern'
);
SELECT is(
  (SELECT count(*)::integer FROM public.saas_opportunity_review_events WHERE opportunity_id=:'saas_review_candidate_id'),
  2,'each decision is stored in the append-only review history'
);
RESET ROLE;
SELECT throws_ok(
  format('UPDATE public.saas_opportunity_review_events SET note=''tampered'' WHERE opportunity_id=%L', :'saas_review_candidate_id'),
  '55000',NULL,'review history cannot be updated'
);

SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  '{"sub":"10000000-0000-0000-0000-000000000101","role":"authenticated","app_metadata":{"role":"operator"}}',true);
SELECT throws_ok(
  format('SELECT public.review_saas_opportunity(%L,''under_review'',''Try to reopen rejected idea'')', :'saas_review_rejected_id'),
  '23514',NULL,'rejected candidates cannot be reopened'
);

RESET ROLE;
SELECT * FROM finish();
ROLLBACK;
