SET request.jwt.claims = '{"role":"service_role"}';
SELECT public.execute_approved_task_action(
  repeat('a', 64),
  'legacy:74000000-0000-4000-8000-000000000004',
  '74000000-0000-4000-8000-000000000002'::uuid,
  '{"type":"create","operation_id":"74000000-0000-4000-8000-000000000002","title":"Lead race first","priority":"normal","due_at":null,"notes":"","lead_id":"74000000-0000-4000-8000-000000000001"}'::jsonb
);
