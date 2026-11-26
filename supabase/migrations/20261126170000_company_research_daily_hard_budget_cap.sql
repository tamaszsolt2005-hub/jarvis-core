-- Persist the admission ceiling and enforce it again during actual-cost settlement.
-- Repository artifact only: do not apply to production without separate approval.
BEGIN;

ALTER TABLE public.company_research_budget_reservations
  ADD COLUMN IF NOT EXISTS daily_budget_microusd bigint
  CHECK (daily_budget_microusd IS NULL OR daily_budget_microusd > 0);

CREATE OR REPLACE FUNCTION public.company_research_job_create(
  p_job jsonb,
  p_estimated_cost_microusd bigint DEFAULT 0,
  p_daily_budget_microusd bigint DEFAULT NULL,
  p_max_jobs_per_hour integer DEFAULT NULL,
  p_max_jobs_per_domain_per_day integer DEFAULT NULL
) RETURNS SETOF public.company_research_jobs
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $$
DECLARE
  v_existing public.company_research_jobs%ROWTYPE;
  v_reserved bigint;
  v_existing_reservation bigint;
  v_existing_daily_budget bigint;
  v_effective_budget bigint;
  v_hourly_count bigint;
  v_domain_daily_count bigint;
  v_domain text := lower(btrim(COALESCE(p_job->'payload'->>'company_domain', '')));
  v_budget_date date := (now() AT TIME ZONE 'UTC')::date;
  v_hour_start timestamptz := date_trunc('hour', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC';
  v_day_start timestamptz := date_trunc('day', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC';
BEGIN
  IF p_job IS NULL OR jsonb_typeof(p_job) <> 'object'
     OR p_estimated_cost_microusd IS NULL OR p_estimated_cost_microusd < 0
     OR (p_daily_budget_microusd IS NOT NULL AND p_daily_budget_microusd < 1)
     OR (p_max_jobs_per_hour IS NOT NULL AND p_max_jobs_per_hour < 1)
     OR (p_max_jobs_per_domain_per_day IS NOT NULL AND p_max_jobs_per_domain_per_day < 1)
     OR (p_max_jobs_per_domain_per_day IS NOT NULL AND v_domain = '') THEN
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
    SELECT reserved_cost_microusd, daily_budget_microusd
      INTO v_existing_reservation, v_existing_daily_budget
    FROM public.company_research_budget_reservations
    WHERE operation_id = v_existing.operation_id;
    IF v_existing_reservation IS DISTINCT FROM p_estimated_cost_microusd
       OR v_existing_daily_budget IS DISTINCT FROM p_daily_budget_microusd THEN
      RAISE EXCEPTION 'research_operation_id_conflict';
    END IF;
    RETURN NEXT v_existing;
    RETURN;
  END IF;

  SELECT COALESCE(sum(reserved_cost_microusd), 0) INTO v_reserved
  FROM public.company_research_budget_reservations
  WHERE budget_date = v_budget_date;

  SELECT min(daily_budget_microusd) INTO v_existing_daily_budget
  FROM public.company_research_budget_reservations
  WHERE budget_date = v_budget_date AND daily_budget_microusd IS NOT NULL;
  v_effective_budget := CASE
    WHEN p_daily_budget_microusd IS NULL THEN v_existing_daily_budget
    WHEN v_existing_daily_budget IS NULL THEN p_daily_budget_microusd
    ELSE LEAST(p_daily_budget_microusd, v_existing_daily_budget)
  END;

  IF p_max_jobs_per_hour IS NOT NULL THEN
    SELECT count(*) INTO v_hourly_count
    FROM public.company_research_jobs
    WHERE created_at >= v_hour_start;
    IF v_hourly_count >= p_max_jobs_per_hour THEN
      RAISE EXCEPTION 'research_hourly_limit_exceeded';
    END IF;
  END IF;

  IF p_max_jobs_per_domain_per_day IS NOT NULL THEN
    SELECT count(*) INTO v_domain_daily_count
    FROM public.company_research_jobs
    WHERE created_at >= v_day_start
      AND lower(COALESCE(payload->>'company_domain', '')) = v_domain;
    IF v_domain_daily_count >= p_max_jobs_per_domain_per_day THEN
      RAISE EXCEPTION 'research_domain_daily_limit_exceeded';
    END IF;
  END IF;

  IF v_effective_budget IS NOT NULL
     AND v_reserved + p_estimated_cost_microusd > v_effective_budget THEN
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
    now(),
    now(),
    COALESCE((p_job->>'available_at')::timestamptz, now())
  ) RETURNING * INTO v_existing;

  INSERT INTO public.company_research_budget_reservations (
    operation_id, budget_date, reserved_cost_microusd, daily_budget_microusd
  ) VALUES (
    v_existing.operation_id, v_budget_date, p_estimated_cost_microusd, p_daily_budget_microusd
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

CREATE OR REPLACE FUNCTION public.company_research_job_complete(
  p_operation_id text, p_worker_id text, p_result jsonb,
  p_actual_cost_microusd bigint DEFAULT NULL
) RETURNS SETOF public.company_research_jobs
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $$
DECLARE
  v_job public.company_research_jobs%ROWTYPE;
  v_reservation public.company_research_budget_reservations%ROWTYPE;
  v_other_reserved bigint;
  v_effective_budget bigint;
  v_final_status text;
BEGIN
  IF p_actual_cost_microusd IS NOT NULL AND p_actual_cost_microusd < 0 THEN
    RAISE EXCEPTION 'invalid actual research cost';
  END IF;

  -- Serialize settlements with new reservations. The same lock is taken by
  -- job_create, so two workers cannot race the daily aggregate.
  PERFORM pg_advisory_xact_lock(742026, 2);

  SELECT * INTO v_job
  FROM public.company_research_jobs
  WHERE operation_id = p_operation_id AND status = 'running'
    AND lease_owner = p_worker_id AND lease_expires_at > now()
  FOR UPDATE;
  IF NOT FOUND THEN
    RETURN;
  END IF;

  SELECT * INTO v_reservation
  FROM public.company_research_budget_reservations
  WHERE operation_id = p_operation_id
  FOR UPDATE;
  IF NOT FOUND OR v_reservation.reservation_status <> 'reserved' THEN
    RAISE EXCEPTION 'research_budget_reservation_missing_or_settled';
  END IF;

  SELECT min(daily_budget_microusd) INTO v_effective_budget
  FROM public.company_research_budget_reservations
  WHERE budget_date = v_reservation.budget_date
    AND daily_budget_microusd IS NOT NULL;

  IF p_actual_cost_microusd IS NULL AND v_effective_budget IS NOT NULL THEN
    -- A capped operation without measurable actual cost cannot be declared
    -- successful. Keep its estimate reserved so it cannot free budget silently.
    v_final_status := 'dead_letter';
    UPDATE public.company_research_jobs
    SET status = v_final_status, result = COALESCE(p_result, '{}'::jsonb),
        lease_owner = NULL, lease_expires_at = NULL,
        last_error_code = 'actual_cost_missing',
        last_error_message = 'Actual provider cost was unavailable; budget remains reserved.',
        updated_at = now()
    WHERE job_id = v_job.job_id
    RETURNING * INTO v_job;
    INSERT INTO public.company_research_job_audit (operation_id, event_type, worker_id, metadata)
    VALUES (p_operation_id, 'dead_letter', p_worker_id,
            jsonb_build_object('reason', 'actual_cost_missing',
                               'reserved_cost_microusd', v_reservation.reserved_cost_microusd));
    RETURN NEXT v_job;
    RETURN;
  END IF;

  v_final_status := 'succeeded';
  IF p_actual_cost_microusd IS NOT NULL THEN
    SELECT COALESCE(sum(reserved_cost_microusd), 0) INTO v_other_reserved
    FROM public.company_research_budget_reservations
    WHERE budget_date = v_reservation.budget_date
      AND operation_id <> p_operation_id;

    IF v_effective_budget IS NOT NULL
       AND v_other_reserved + p_actual_cost_microusd > v_effective_budget THEN
      v_final_status := 'dead_letter';
    END IF;

    -- Record the provider's actual charge even on overrun. This cannot undo
    -- spend already incurred, but blocks all subsequent admissions until the
    -- UTC-day budget has room again.
    UPDATE public.company_research_budget_reservations
    SET reserved_cost_microusd = p_actual_cost_microusd,
        actual_cost_microusd = p_actual_cost_microusd,
        reservation_status = 'settled'
    WHERE operation_id = p_operation_id AND reservation_status = 'reserved';
    IF NOT FOUND THEN
      RAISE EXCEPTION 'research_budget_reservation_missing_or_settled';
    END IF;
  END IF;

  UPDATE public.company_research_jobs
  SET status = v_final_status, result = COALESCE(p_result, '{}'::jsonb),
      lease_owner = NULL, lease_expires_at = NULL,
      last_error_code = CASE WHEN v_final_status = 'dead_letter' THEN 'daily_budget_overrun' ELSE NULL END,
      last_error_message = CASE WHEN v_final_status = 'dead_letter'
        THEN 'Actual provider cost exceeded the remaining daily budget; further admissions are blocked.'
        ELSE NULL END,
      updated_at = now()
  WHERE job_id = v_job.job_id
  RETURNING * INTO v_job;

  INSERT INTO public.company_research_job_audit (operation_id, event_type, worker_id, metadata)
  VALUES (
    p_operation_id,
    CASE WHEN v_final_status = 'succeeded' THEN 'succeeded' ELSE 'dead_letter' END,
    p_worker_id,
    CASE WHEN p_actual_cost_microusd IS NULL THEN '{}'::jsonb
         ELSE jsonb_build_object('actual_cost_microusd', p_actual_cost_microusd,
              'daily_budget_microusd', v_effective_budget,
              'reason', CASE WHEN v_final_status = 'dead_letter' THEN 'daily_budget_overrun' ELSE 'settled' END)
    END
  );
  RETURN NEXT v_job;
END;
$$;

COMMIT;
