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

-- Daily cost reservations are written in the same transaction as job creation.
CREATE TABLE IF NOT EXISTS public.company_research_budget_reservations (
  operation_id text PRIMARY KEY REFERENCES public.company_research_jobs(operation_id) ON DELETE RESTRICT,
  budget_date date NOT NULL,
  reserved_cost_microusd bigint NOT NULL CHECK (reserved_cost_microusd >= 0),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS company_research_budget_reservations_daily_idx
  ON public.company_research_budget_reservations (budget_date);

-- Append-only operational audit. No UPDATE or DELETE privilege is granted.
CREATE TABLE IF NOT EXISTS public.company_research_job_audit (
  event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  operation_id text NOT NULL,
  event_type text NOT NULL CHECK (event_type IN
    ('enqueued', 'claimed', 'heartbeat', 'succeeded', 'retry_scheduled', 'dead_letter')),
  worker_id text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS company_research_job_audit_operation_idx
  ON public.company_research_job_audit (operation_id, created_at);

ALTER TABLE public.company_research_budget_reservations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_research_job_audit ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.company_research_budget_reservations FROM PUBLIC, anon, authenticated;
REVOKE ALL ON TABLE public.company_research_job_audit FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT ON TABLE public.company_research_budget_reservations TO service_role;
GRANT SELECT, INSERT ON TABLE public.company_research_job_audit TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.company_research_job_audit_event_id_seq TO service_role;

ALTER TABLE public.company_research_jobs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.company_research_jobs FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON TABLE public.company_research_jobs TO service_role;

-- SECURITY INVOKER is intentional: the caller's backend role must own the
-- permitted table privileges. No public/authenticated execution is granted.
CREATE OR REPLACE FUNCTION public.company_research_job_create(
  p_job jsonb,
  p_estimated_cost_microusd bigint DEFAULT 0,
  p_daily_budget_microusd bigint DEFAULT NULL
) RETURNS SETOF public.company_research_jobs
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $$
DECLARE
  v_existing public.company_research_jobs%ROWTYPE;
  v_reserved bigint;
  v_budget_date date := (now() AT TIME ZONE 'UTC')::date;
BEGIN
  IF p_job IS NULL OR jsonb_typeof(p_job) <> 'object'
     OR p_estimated_cost_microusd IS NULL OR p_estimated_cost_microusd < 0
     OR (p_daily_budget_microusd IS NOT NULL AND p_daily_budget_microusd < 1) THEN
    RAISE EXCEPTION 'invalid research job reservation arguments';
  END IF;

  -- Serialize daily reservations. Replays return the original job/reservation
  -- and cannot reserve the same operation twice.
  PERFORM pg_advisory_xact_lock(742026, 2);

  SELECT * INTO v_existing
  FROM public.company_research_jobs
  WHERE operation_id = p_job->>'operation_id';

  IF FOUND THEN
    IF v_existing.job_type <> p_job->>'job_type'
       OR v_existing.lead_id <> (p_job->>'lead_id')::uuid
       OR v_existing.payload <> p_job->'payload' THEN
      RAISE EXCEPTION 'research_operation_id_conflict';
    END IF;
    RETURN NEXT v_existing;
    RETURN;
  END IF;

  SELECT COALESCE(sum(reserved_cost_microusd), 0) INTO v_reserved
  FROM public.company_research_budget_reservations
  WHERE budget_date = v_budget_date;

  IF p_daily_budget_microusd IS NOT NULL
     AND v_reserved + p_estimated_cost_microusd > p_daily_budget_microusd THEN
    RAISE EXCEPTION 'research_daily_budget_exceeded';
  END IF;

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
  ) RETURNING * INTO v_existing;

  INSERT INTO public.company_research_budget_reservations (
    operation_id, budget_date, reserved_cost_microusd
  ) VALUES (
    v_existing.operation_id, v_budget_date, p_estimated_cost_microusd
  );

  INSERT INTO public.company_research_job_audit (
    operation_id, event_type, metadata
  ) VALUES (
    v_existing.operation_id, 'enqueued',
    jsonb_build_object('estimated_cost_microusd', p_estimated_cost_microusd)
  );

  RETURN NEXT v_existing;
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
  v_claimed public.company_research_jobs%ROWTYPE;
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
  WITH expired AS (
    UPDATE public.company_research_jobs
    SET status = 'dead_letter', lease_owner = NULL, lease_expires_at = NULL,
        last_error_code = COALESCE(last_error_code, 'lease_expired'),
        last_error_message = COALESCE(last_error_message, 'Worker lease expired after final attempt.'),
        updated_at = now()
    WHERE status = 'running' AND lease_expires_at <= now()
      AND attempt_count >= max_attempts
    RETURNING operation_id, attempt_count
  )
  INSERT INTO public.company_research_job_audit (operation_id, event_type, metadata)
  SELECT operation_id, 'dead_letter',
         jsonb_build_object('reason', 'lease_expired', 'attempt_count', attempt_count)
  FROM expired;

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

  UPDATE public.company_research_jobs
  SET status = 'running',
      attempt_count = attempt_count + 1,
      lease_owner = btrim(p_worker_id),
      lease_expires_at = now() + make_interval(secs => p_lease_seconds),
      heartbeat_at = now(),
      updated_at = now()
  WHERE job_id = v_job_id
  RETURNING * INTO v_claimed;

  INSERT INTO public.company_research_job_audit (operation_id, event_type, worker_id, metadata)
  VALUES (v_claimed.operation_id, 'claimed', btrim(p_worker_id),
          jsonb_build_object('attempt_count', v_claimed.attempt_count));
  RETURN NEXT v_claimed;
END;
$$;

CREATE OR REPLACE FUNCTION public.company_research_job_heartbeat(
  p_operation_id text, p_worker_id text, p_lease_seconds integer
) RETURNS SETOF public.company_research_jobs
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $$
DECLARE
  v_transition public.company_research_jobs%ROWTYPE;
BEGIN
  IF p_lease_seconds IS NULL OR p_lease_seconds < 1 THEN
    RAISE EXCEPTION 'invalid lease duration';
  END IF;
  UPDATE public.company_research_jobs
  SET lease_expires_at = now() + make_interval(secs => p_lease_seconds),
      heartbeat_at = now(), updated_at = now()
  WHERE operation_id = p_operation_id AND status = 'running'
    AND lease_owner = p_worker_id AND lease_expires_at > now()
  RETURNING * INTO v_transition;

  IF FOUND THEN
    INSERT INTO public.company_research_job_audit (operation_id, event_type, worker_id)
    VALUES (p_operation_id, 'heartbeat', p_worker_id);
    RETURN NEXT v_transition;
  END IF;
END;
$$;

CREATE OR REPLACE FUNCTION public.company_research_job_complete(
  p_operation_id text, p_worker_id text, p_result jsonb
) RETURNS SETOF public.company_research_jobs
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $$
DECLARE
  v_transition public.company_research_jobs%ROWTYPE;
BEGIN
  UPDATE public.company_research_jobs
  SET status = 'succeeded', result = COALESCE(p_result, '{}'::jsonb),
      lease_owner = NULL, lease_expires_at = NULL, updated_at = now()
  WHERE operation_id = p_operation_id AND status = 'running'
    AND lease_owner = p_worker_id AND lease_expires_at > now()
  RETURNING * INTO v_transition;

  IF FOUND THEN
    INSERT INTO public.company_research_job_audit (operation_id, event_type, worker_id)
    VALUES (p_operation_id, 'succeeded', p_worker_id);
    RETURN NEXT v_transition;
  END IF;
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
DECLARE
  v_transition public.company_research_jobs%ROWTYPE;
BEGIN
  IF p_retryable IS NULL OR p_retry_delay_seconds IS NULL OR p_max_attempts IS NULL
     OR p_retry_delay_seconds < 1 OR p_max_attempts < 1 THEN
    RAISE EXCEPTION 'invalid retry arguments';
  END IF;
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
  RETURNING * INTO v_transition;

  IF FOUND THEN
    INSERT INTO public.company_research_job_audit (operation_id, event_type, worker_id, metadata)
    VALUES (p_operation_id,
            CASE WHEN v_transition.status = 'retry_wait' THEN 'retry_scheduled' ELSE 'dead_letter' END,
            p_worker_id,
            jsonb_build_object('error_code', v_transition.last_error_code,
                               'attempt_count', v_transition.attempt_count));
    RETURN NEXT v_transition;
  END IF;
END;
$$;

REVOKE ALL ON FUNCTION public.company_research_job_create(jsonb, bigint, bigint) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.company_research_job_claim(text, integer, integer) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.company_research_job_heartbeat(text, text, integer) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.company_research_job_complete(text, text, jsonb) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.company_research_job_fail(text, text, text, text, boolean, integer, integer) FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.company_research_job_create(jsonb, bigint, bigint) TO service_role;
GRANT EXECUTE ON FUNCTION public.company_research_job_claim(text, integer, integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.company_research_job_heartbeat(text, text, integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.company_research_job_complete(text, text, jsonb) TO service_role;
GRANT EXECUTE ON FUNCTION public.company_research_job_fail(text, text, text, text, boolean, integer, integer) TO service_role;

COMMIT;
