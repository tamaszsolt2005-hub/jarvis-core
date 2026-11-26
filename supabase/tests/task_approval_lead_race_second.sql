SET request.jwt.claims = '{"role":"service_role"}';
SELECT public.execute_approved_task_action(
  encode(extensions.digest('jarvis:task-approval:lead-race:second', 'sha256'), 'hex'),
  'legacy:74000000-0000-4000-8000-000000000005',
  '74000000-0000-4000-8000-000000000003'::uuid,
  '{"type":"create","operation_id":"74000000-0000-4000-8000-000000000003","title":"Lead race second","priority":"normal","due_at":null,"notes":"","lead_id":"74000000-0000-4000-8000-000000000001"}'::jsonb
);
