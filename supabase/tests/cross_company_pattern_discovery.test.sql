BEGIN;
SELECT plan(3);

SELECT has_column(
  'public', 'market_problem_patterns', 'fingerprint',
  'market pattern candidates have a deterministic idempotency fingerprint'
);
SELECT ok(
  EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='business_pain_snapshot_statement_uidx'),
  'company pain hypotheses are idempotent per lead and immutable research snapshot'
);
SELECT ok(
  EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='market_problem_patterns_fingerprint_uidx')
  AND EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='saas_opportunities_discovery_fingerprint_uidx'),
  'market patterns and SaaS candidates have unique discovery keys'
);

SELECT * FROM finish();
ROLLBACK;
