-- Final task-table privilege lockdown.
-- Apply only after the RPC-enabled application version is deployed. Until then,
-- service_role retains the legacy table-write path for a zero-downtime rollout.
BEGIN;

REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
  ON TABLE public.tasks
  FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT ON TABLE public.tasks TO authenticated, service_role;

COMMIT;
