-- Human-controlled pause/resume and read-only operational visibility for company research.
-- Repository-only until separately reviewed and deployed.
BEGIN;

CREATE TABLE IF NOT EXISTS public.company_research_runtime_control (
  singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
  paused boolean NOT NULL DEFAULT false,
  note text NOT NULL DEFAULT '',
  updated_at timestamptz NOT NULL DEFAULT now(),
  updated_by uuid
);
INSERT INTO public.company_research_runtime_control(singleton, paused, note)
VALUES (true, false, 'Initial operating state')
ON CONFLICT (singleton) DO NOTHING;

CREATE TABLE IF NOT EXISTS public.company_research_runtime_control_events (
  event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  paused boolean NOT NULL,
  note text NOT NULL CHECK (length(btrim(note)) BETWEEN 5 AND 500),
  actor_id uuid,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.company_research_runtime_control ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_research_runtime_control_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.company_research_runtime_control FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON TABLE public.company_research_runtime_control_events FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT ON TABLE public.company_research_runtime_control TO service_role;

CREATE OR REPLACE FUNCTION public.company_research_worker_control_state()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $worker_ops$
DECLARE
  v_role text := auth.jwt() -> 'app_metadata' ->> 'role';
  v_state public.company_research_runtime_control%ROWTYPE;
  v_counts jsonb;
  v_jobs jsonb;
  v_budget jsonb;
  v_events jsonb;
  v_job_events jsonb;
BEGIN
  IF COALESCE(v_role, '') NOT IN ('admin', 'operator', 'reader') THEN
    RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'research_control_read_forbidden';
  END IF;
  SELECT * INTO v_state
  FROM public.company_research_runtime_control
  WHERE singleton = true;
  IF NOT FOUND THEN
    RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'research_runtime_control_unavailable';
  END IF;
  SELECT COALESCE(jsonb_object_agg(status, total), '{}'::jsonb) INTO v_counts
  FROM (
    SELECT status, count(*)::integer AS total
    FROM public.company_research_jobs
    GROUP BY status
  ) counts;
  SELECT COALESCE(jsonb_agg(job ORDER BY job->>'created_at' DESC), '[]'::jsonb) INTO v_jobs
  FROM (
    SELECT jsonb_build_object(
      'operation_id', operation_id, 'lead_id', lead_id, 'status', status,
      'attempt_count', attempt_count, 'created_at', created_at,
      'updated_at', updated_at, 'available_at', available_at,
      'lease_expires_at', lease_expires_at, 'last_error_code', last_error_code
    ) AS job
    FROM (
      SELECT DISTINCT ON (lead_id)
        operation_id, lead_id, status, attempt_count, created_at,
        updated_at, available_at, lease_expires_at, last_error_code, job_id
      FROM public.company_research_jobs
      ORDER BY lead_id, created_at DESC, job_id DESC
    ) latest_per_lead
    ORDER BY created_at DESC, job_id DESC
    LIMIT 1000
  ) latest_jobs;
  SELECT jsonb_build_object(
    'reserved_microusd', COALESCE(sum(reserved_cost_microusd) FILTER (WHERE reservation_status = 'reserved'), 0),
    'committed_microusd', COALESCE(sum(reserved_cost_microusd), 0),
    'actual_microusd', COALESCE(sum(actual_cost_microusd), 0),
    'limit_microusd', COALESCE(min(daily_budget_microusd), 0),
    'over_budget', COALESCE(sum(reserved_cost_microusd), 0) > COALESCE(min(daily_budget_microusd), 0)
                   AND min(daily_budget_microusd) IS NOT NULL,
    'jobs_today', count(*)
  ) INTO v_budget
  FROM public.company_research_budget_reservations
  WHERE budget_date = (now() AT TIME ZONE 'UTC')::date;
  SELECT COALESCE(jsonb_agg(jsonb_build_object(
    'event_id', event_id, 'paused', paused, 'note', note,
    'created_at', created_at
  ) ORDER BY created_at DESC, event_id DESC), '[]'::jsonb) INTO v_events
  FROM (
    SELECT event_id, paused, note, created_at
    FROM public.company_research_runtime_control_events
    ORDER BY created_at DESC, event_id DESC
    LIMIT 20
  ) recent_events;
  SELECT COALESCE(jsonb_agg(job_event ORDER BY job_event->>'created_at' DESC), '[]'::jsonb)
  INTO v_job_events
  FROM (
    SELECT jsonb_build_object(
      'operation_id', operation_id, 'event_type', event_type,
      'worker_id', worker_id, 'metadata', metadata, 'created_at', created_at
    ) AS job_event
    FROM public.company_research_job_audit
    ORDER BY created_at DESC, event_id DESC
    LIMIT 50
  ) recent_job_events;
  RETURN jsonb_build_object(
    'paused', COALESCE(v_state.paused, false),
    'note', COALESCE(v_state.note, ''),
    'updated_at', v_state.updated_at,
    'counts', v_counts,
    'recent_jobs', v_jobs,
    'budget_today', v_budget,
    'recent_events', v_events,
    'recent_job_events', v_job_events
  );
END;
$worker_ops$;

CREATE OR REPLACE FUNCTION public.company_research_worker_set_paused(
  p_paused boolean, p_note text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $worker_ops$
DECLARE
  v_role text := auth.jwt() -> 'app_metadata' ->> 'role';
  v_actor uuid := NULLIF(auth.jwt() ->> 'sub', '')::uuid;
BEGIN
  IF COALESCE(v_role, '') NOT IN ('admin', 'operator') THEN
    RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'research_control_write_forbidden';
  END IF;
  IF p_paused IS NULL OR p_note IS NULL
     OR length(btrim(p_note)) NOT BETWEEN 5 AND 500 THEN
    RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'research_control_note_required';
  END IF;
  PERFORM pg_advisory_xact_lock(742026, 3);
  UPDATE public.company_research_runtime_control
  SET paused = p_paused, note = btrim(p_note), updated_at = now(), updated_by = v_actor
  WHERE singleton = true;
  INSERT INTO public.company_research_runtime_control_events(paused, note, actor_id)
  VALUES (p_paused, btrim(p_note), v_actor);
  RETURN public.company_research_worker_control_state();
END;
$worker_ops$;

-- Replace claim with an atomic pause gate. Claims and pause/resume share an
-- advisory transaction lock, so no new lease starts after a pause commits.
CREATE OR REPLACE FUNCTION public.company_research_job_claim(
  p_worker_id text, p_lease_seconds integer, p_max_concurrent_jobs integer
) RETURNS SETOF public.company_research_jobs
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $worker_ops$
DECLARE
  v_paused boolean;
  v_job_id uuid;
  v_running_count integer;
  v_claimed public.company_research_jobs%ROWTYPE;
BEGIN
  IF p_worker_id IS NULL OR length(btrim(p_worker_id)) = 0
     OR p_lease_seconds IS NULL OR p_lease_seconds < 1
     OR p_max_concurrent_jobs IS NULL OR p_max_concurrent_jobs < 1 THEN
    RAISE EXCEPTION 'invalid claim arguments';
  END IF;
  PERFORM pg_advisory_xact_lock(742026, 3);
  SELECT paused INTO v_paused
  FROM public.company_research_runtime_control
  WHERE singleton = true;
  IF v_paused IS DISTINCT FROM false THEN
    RETURN;
  END IF;
  PERFORM pg_advisory_xact_lock(742026, 1);
  SELECT count(*) INTO v_running_count
  FROM public.company_research_jobs
  WHERE status = 'running' AND lease_expires_at > now();
  IF v_running_count >= p_max_concurrent_jobs THEN
    RETURN;
  END IF;
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
  SET status = 'running', attempt_count = attempt_count + 1,
      lease_owner = btrim(p_worker_id),
      lease_expires_at = now() + make_interval(secs => p_lease_seconds),
      heartbeat_at = now(), updated_at = now()
  WHERE job_id = v_job_id
  RETURNING * INTO v_claimed;
  INSERT INTO public.company_research_job_audit (operation_id, event_type, worker_id, metadata)
  VALUES (v_claimed.operation_id, 'claimed', btrim(p_worker_id),
          jsonb_build_object('attempt_count', v_claimed.attempt_count));
  RETURN NEXT v_claimed;
END;
$worker_ops$;

REVOKE ALL ON FUNCTION public.company_research_worker_control_state() FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.company_research_worker_set_paused(boolean, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.company_research_worker_control_state() TO authenticated;
GRANT EXECUTE ON FUNCTION public.company_research_worker_set_paused(boolean, text) TO authenticated;

COMMIT;
