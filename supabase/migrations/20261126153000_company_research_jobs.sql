-- Durable, service-role-only company research job queue.
-- Repository artifact only: do not apply to production without separate approval.
BEGIN;

CREATE TABLE IF NOT EXISTS public.company_research_jobs (
  job_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  operation_id text NOT NULL UNIQUE CHECK (operation_id ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$'),
  job_type text NOT NULL CHECK (job_type = 'company_research_refresh'),
  lead_id uuid NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
  payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
  status text NOT NULL CHECK (status IN ('queued', 'running', 'retry_wait', 'succeeded', 'dead_letter')),
  attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
  max_attempts integer NOT NULL DEFAULT 3 CHECK (max_attempts > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  available_at timestamptz NOT NULL DEFAULT now(),
  lease_owner text,
  lease_expires_at timestamptz,
  heartbeat_at timestamptz,
  last_error_code text,
  last_error_message text,
  result jsonb CHECK (result IS NULL OR jsonb_typeof(result) = 'object'),
  CONSTRAINT company_research_jobs_lease_pair CHECK (
    (lease_owner IS NULL AND lease_expires_at IS NULL)
    OR (lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL)
  )
);

CREATE INDEX IF NOT EXISTS company_research_jobs_ready_idx
  ON public.company_research_jobs (available_at, created_at)
  WHERE status IN ('queued', 'retry_wait');
CREATE INDEX IF NOT EXISTS company_research_jobs_expired_lease_idx
  ON public.company_research_jobs (lease_expires_at)
  WHERE status = 'running';

ALTER TABLE public.company_research_jobs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.company_research_jobs FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON TABLE public.company_research_jobs TO service_role;

-- SECURITY INVOKER is intentional: the caller's backend role must own the
-- permitted table privileges. No public/authenticated execution is granted.
CREATE OR REPLACE FUNCTION public.company_research_job_create(p_job jsonb)
RETURNS SETOF public.company_research_jobs
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $$
BEGIN
  INSERT INTO public.company_research_jobs (
    operation_id, job_type, lead_id, payload, status, attempt_count,
    max_attempts, created_at, updated_at, available_at
  ) VALUES (
    p_job->>'operation_id', p_job->>'job_type', (p_job->>'lead_id')::uuid,
    p_job->'payload', p_job->>'status',
    COALESCE((p_job->>'attempt_count')::integer, 0),
    COALESCE((p_job->>'max_attempts')::integer, 3),
    COALESCE((p_job->>'created_at')::timestamptz, now()),
    COALESCE((p_job->>'updated_at')::timestamptz, now()),
    COALESCE((p_job->>'available_at')::timestamptz, now())
  )
  ON CONFLICT (operation_id) DO NOTHING;

  RETURN QUERY
    SELECT * FROM public.company_research_jobs
    WHERE operation_id = p_job->>'operation_id';
END;
$$;

DROP FUNCTION IF EXISTS public.company_research_job_claim(text, integer);

CREATE OR REPLACE FUNCTION public.company_research_job_claim(
  p_worker_id text, p_lease_seconds integer, p_max_concurrent_jobs integer
) RETURNS SETOF public.company_research_jobs
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $$
DECLARE
  v_job_id uuid;
  v_running_count integer;
BEGIN
  IF p_worker_id IS NULL OR length(btrim(p_worker_id)) = 0
     OR p_lease_seconds IS NULL OR p_lease_seconds < 1
     OR p_max_concurrent_jobs IS NULL OR p_max_concurrent_jobs < 1 THEN
    RAISE EXCEPTION 'invalid claim arguments';
  END IF;

  -- Serialize claim decisions so concurrent workers cannot all observe the
  -- same free slot and exceed the global active-lease ceiling.
  PERFORM pg_advisory_xact_lock(742026, 1);

  SELECT count(*) INTO v_running_count
  FROM public.company_research_jobs
  WHERE status = 'running' AND lease_expires_at > now();

  IF v_running_count >= p_max_concurrent_jobs THEN
    RETURN;
  END IF;

  -- A worker that vanished on its final permitted attempt must not be
  -- reclaimed indefinitely. Move those expired leases to the terminal queue.
  UPDATE public.company_research_jobs
  SET status = 'dead_letter', lease_owner = NULL, lease_expires_at = NULL,
      last_error_code = COALESCE(last_error_code, 'lease_expired'),
      last_error_message = COALESCE(last_error_message, 'Worker lease expired after final attempt.'),
      updated_at = now()
  WHERE status = 'running' AND lease_expires_at <= now()
    AND attempt_count >= max_attempts;

  SELECT job_id INTO v_job_id
  FROM public.company_research_jobs
  WHERE (
    (status IN ('queued', 'retry_wait') AND available_at <= now())
    OR (status = 'running' AND lease_expires_at <= now() AND attempt_count < max_attempts)
  )
  ORDER BY available_at, created_at, job_id
  LIMIT 1
  FOR UPDATE SKIP LOCKED;

  IF v_job_id IS NULL THEN
    RETURN;
  END IF;

  RETURN QUERY
    UPDATE public.company_research_jobs
    SET status = 'running',
        attempt_count = attempt_count + 1,
        lease_owner = btrim(p_worker_id),
        lease_expires_at = now() + make_interval(secs => p_lease_seconds),
        heartbeat_at = now(),
        updated_at = now()
    WHERE job_id = v_job_id
    RETURNING *;
END;
$$;

CREATE OR REPLACE FUNCTION public.company_research_job_heartbeat(
  p_operation_id text, p_worker_id text, p_lease_seconds integer
) RETURNS SETOF public.company_research_jobs
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $$
BEGIN
  IF p_lease_seconds IS NULL OR p_lease_seconds < 1 THEN RAISE EXCEPTION 'invalid lease duration'; END IF;
  RETURN QUERY
    UPDATE public.company_research_jobs
    SET lease_expires_at = now() + make_interval(secs => p_lease_seconds),
        heartbeat_at = now(), updated_at = now()
    WHERE operation_id = p_operation_id AND status = 'running'
      AND lease_owner = p_worker_id AND lease_expires_at > now()
    RETURNING *;
END;
$$;

CREATE OR REPLACE FUNCTION public.company_research_job_complete(
  p_operation_id text, p_worker_id text, p_result jsonb
) RETURNS SETOF public.company_research_jobs
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $$
BEGIN
  RETURN QUERY
    UPDATE public.company_research_jobs
    SET status = 'succeeded', result = COALESCE(p_result, '{}'::jsonb),
        lease_owner = NULL, lease_expires_at = NULL, updated_at = now()
    WHERE operation_id = p_operation_id AND status = 'running'
      AND lease_owner = p_worker_id AND lease_expires_at > now()
    RETURNING *;
END;
$$;

CREATE OR REPLACE FUNCTION public.company_research_job_fail(
  p_operation_id text, p_worker_id text, p_error_code text,
  p_error_message text, p_retryable boolean,
  p_retry_delay_seconds integer, p_max_attempts integer
) RETURNS SETOF public.company_research_jobs
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $$
BEGIN
  IF p_retryable IS NULL OR p_retry_delay_seconds IS NULL OR p_max_attempts IS NULL
     OR p_retry_delay_seconds < 1 OR p_max_attempts < 1 THEN
    RAISE EXCEPTION 'invalid retry arguments';
  END IF;
  RETURN QUERY
    UPDATE public.company_research_jobs
    SET status = CASE
          WHEN p_retryable AND attempt_count < LEAST(max_attempts, p_max_attempts)
            THEN 'retry_wait' ELSE 'dead_letter' END,
        available_at = now() + make_interval(secs => p_retry_delay_seconds),
        lease_owner = NULL, lease_expires_at = NULL,
        last_error_code = left(COALESCE(NULLIF(p_error_code, ''), 'unknown'), 80),
        last_error_message = left(COALESCE(p_error_message, ''), 1000),
        updated_at = now()
    WHERE operation_id = p_operation_id AND status = 'running'
      AND lease_owner = p_worker_id AND lease_expires_at > now()
    RETURNING *;
END;
$$;

REVOKE ALL ON FUNCTION public.company_research_job_create(jsonb) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.company_research_job_claim(text, integer, integer) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.company_research_job_heartbeat(text, text, integer) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.company_research_job_complete(text, text, jsonb) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.company_research_job_fail(text, text, text, text, boolean, integer, integer) FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.company_research_job_create(jsonb) TO service_role;
GRANT EXECUTE ON FUNCTION public.company_research_job_claim(text, integer, integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.company_research_job_heartbeat(text, text, integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.company_research_job_complete(text, text, jsonb) TO service_role;
GRANT EXECUTE ON FUNCTION public.company_research_job_fail(text, text, text, text, boolean, integer, integer) TO service_role;

COMMIT;
