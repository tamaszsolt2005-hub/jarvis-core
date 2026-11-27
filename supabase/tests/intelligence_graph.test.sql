BEGIN;
SELECT plan(24);

SELECT has_table('public','intelligence_entities',
  'canonical Intelligence graph entities table exists');
SELECT has_table('public','intelligence_relationships',
  'canonical Intelligence graph relationships table exists');
SELECT has_column('public','intelligence_entities','metadata',
  'graph entities preserve structured metadata');
SELECT has_column('public','intelligence_relationships','provenance',
  'graph relationships preserve provenance');
SELECT ok(
  (SELECT relrowsecurity FROM pg_class WHERE oid='public.intelligence_entities'::regclass),
  'entity graph has row-level security enabled'
);
SELECT ok(
  (SELECT relrowsecurity FROM pg_class WHERE oid='public.intelligence_relationships'::regclass),
  'relationship graph has row-level security enabled'
);
SELECT ok(
  has_function_privilege(
    'service_role',
    'public.upsert_intelligence_entity(text,text,uuid,text,text,text,numeric,jsonb)',
    'EXECUTE'
  ),
  'service role can maintain graph entities through the guarded helper'
);
SELECT ok(
  NOT has_function_privilege(
    'authenticated',
    'public.upsert_intelligence_entity(text,text,uuid,text,text,text,numeric,jsonb)',
    'EXECUTE'
  ),
  'authenticated users cannot call the graph entity write helper'
);
SELECT lives_ok(
  $$SELECT public.upsert_intelligence_entity(
    'company','graph-test-company',NULL,'Graph test company','Fixture','active',NULL,'{}'::jsonb
  )$$,
  'graph entity helper creates a company node'
);
SELECT lives_ok(
  $$SELECT public.upsert_intelligence_entity(
    'company_pain','graph-test-pain',NULL,'Graph test pain','Fixture pain','hypothesis',0.75,'{}'::jsonb
  )$$,
  'graph entity helper creates a pain node'
);
SELECT is(
  (SELECT count(*)::integer FROM public.intelligence_entities
   WHERE (entity_type,source_id) IN (('company','graph-test-company'),('company_pain','graph-test-pain'))),
  2,
  'graph entity identifiers are unique and stable'
);
SELECT lives_ok(
  $SELECT public.upsert_intelligence_entity(
    'person','graph-test-person',NULL,'Alex Example','Managing Director','public_professional',NULL,'{}'::jsonb
  )$,
  'graph entity helper supports a source-linked public decision maker'
);
SELECT lives_ok(
  $SELECT public.upsert_intelligence_relationship(
    'company','graph-test-company','person','graph-test-person',
    'has_decision_maker',NULL,'{"source":"dossier"}'::jsonb
  )$,
  'company can link to its source-backed decision maker'
);
SELECT is(
  (SELECT count(*)::integer FROM public.intelligence_relationships relationship
   JOIN public.intelligence_entities source_node ON source_node.id=relationship.source_entity_id
   JOIN public.intelligence_entities target_node ON target_node.id=relationship.target_entity_id
   WHERE source_node.source_id='graph-test-company'
     AND target_node.source_id='graph-test-person'
     AND relationship.relationship_type='has_decision_maker'),
  1,
  'decision maker edge is stored as a typed relationship'
);
SELECT lives_ok(
  $$SELECT public.upsert_intelligence_relationship(
    'company','graph-test-company','company_pain','graph-test-pain',
    'has_pain',0.75,'{"source":"pgTAP"}'::jsonb
  )$$,
  'graph relationship helper creates a typed edge'
);
SELECT is(
  (SELECT count(*)::integer FROM public.intelligence_relationships relationship
   JOIN public.intelligence_entities source_node ON source_node.id=relationship.source_entity_id
   JOIN public.intelligence_entities target_node ON target_node.id=relationship.target_entity_id
   WHERE source_node.source_id='graph-test-company'
     AND target_node.source_id='graph-test-pain'
     AND relationship.relationship_type='has_pain'),
  1,
  'graph relationship connects the expected nodes'
);
SELECT ok(
  has_table_privilege('service_role','public.intelligence_entities','SELECT')
  AND has_table_privilege('service_role','public.intelligence_entities','INSERT')
  AND has_table_privilege('service_role','public.intelligence_entities','UPDATE')
  AND has_table_privilege('service_role','public.intelligence_entities','DELETE')
  AND has_table_privilege('service_role','public.intelligence_relationships','SELECT')
  AND has_table_privilege('service_role','public.intelligence_relationships','INSERT')
  AND has_table_privilege('service_role','public.intelligence_relationships','UPDATE')
  AND has_table_privilege('service_role','public.intelligence_relationships','DELETE'),
  'service role has the required projection maintenance privileges'
);
SELECT ok(
  has_table_privilege('authenticated','public.intelligence_entities','SELECT')
  AND has_table_privilege('authenticated','public.intelligence_relationships','SELECT')
  AND NOT has_table_privilege('authenticated','public.intelligence_entities','INSERT')
  AND NOT has_table_privilege('authenticated','public.intelligence_relationships','INSERT'),
  'authenticated users receive read-only graph table privileges'
);
SELECT ok(
  NOT has_table_privilege('anon','public.intelligence_entities','SELECT')
  AND NOT has_table_privilege('anon','public.intelligence_relationships','SELECT'),
  'anonymous users cannot read graph tables'
);

SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  '{"sub":"10000000-0000-0000-0000-000000000093","role":"authenticated","app_metadata":{"role":"reader"}}',true);
SELECT is(
  (SELECT count(*)::integer FROM public.intelligence_entities
   WHERE source_id IN ('graph-test-company','graph-test-pain')),
  2,
  'reader can inspect graph entities through RLS'
);
SELECT throws_ok(
  $$INSERT INTO public.intelligence_entities(entity_type,source_id,label)
    VALUES ('company','reader-write-denied','Denied')$$,
  '42501',NULL,'reader cannot write graph entities'
);
RESET ROLE;

SET LOCAL ROLE anon;
SELECT throws_ok(
  $$SELECT count(*) FROM public.intelligence_entities$$,
  '42501',NULL,'anonymous role cannot query graph entities'
);
RESET ROLE;

SELECT throws_ok(
  $$INSERT INTO public.intelligence_entities(entity_type,source_id,label)
    VALUES ('unsupported','invalid-entity','Invalid')$$,
  '23514',NULL,'graph rejects unsupported entity types'
);
SELECT throws_ok(
  $$INSERT INTO public.intelligence_relationships(source_entity_id,target_entity_id,relationship_type)
    SELECT id,id,'has_pain' FROM public.intelligence_entities WHERE source_id='graph-test-company'$$,
  '23514',NULL,'graph rejects self-referential relationships'
);

SELECT * FROM finish();
ROLLBACK;
