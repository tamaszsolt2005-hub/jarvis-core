-- Both clients execute the same approved operation concurrently.
SET request.jwt.claims = '{"role":"authenticated","sub":"10000000-0000-4000-8000-000000000001","app_metadata":{"role":"operator"}}';
SELECT public.execute_approved_task_action(
  repeat('a', 64),
  'auth:10000000-0000-4000-8000-000000000001',
  '20000000-0000-4000-8000-000000000002'::uuid,
  '{"type":"create","operation_id":"20000000-0000-4000-8000-000000000002","title":"Concurrent approval fixture","priority":"normal","due_at":null,"notes":""}'::jsonb
);
