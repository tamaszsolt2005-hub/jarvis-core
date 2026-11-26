-- Verify that researched lead tasks are linked and concurrent first-stage
-- work is blocked when an open task already exists for the same lead.
SET request.jwt.claims = '{"role":"service_role"}';

DO $lead_linked_task$
DECLARE
  v_lead uuid := '73000000-0000-4000-8000-000000000001';
  v_first_operation uuid := '73000000-0000-4000-8000-000000000002';
  v_second_operation uuid := '73000000-0000-4000-8000-000000000003';
  v_third_operation uuid := '73000000-0000-4000-8000-000000000004';
  v_bad_operation uuid := '73000000-0000-4000-8000-000000000008';
  v_invalid_rejected boolean := false;
  v_first jsonb;
  v_second jsonb;
  v_third jsonb;
BEGIN
  INSERT INTO public.leads (id, company_name, status)
  VALUES (v_lead, 'Lead-linked task fixture', 'research')
  ON CONFLICT (id) DO NOTHING;

  IF NOT public.issue_pending_approval(
    repeat('7', 64),
    'legacy:73000000-0000-4000-8000-000000000005',
    jsonb_build_object(
      'type', 'create', 'operation_id', v_first_operation,
      'title', 'Lead research validation', 'priority', 'normal',
      'due_at', NULL, 'notes', 'Grounded internal review',
      'lead_id', v_lead
    ),
    300
  ) THEN
    RAISE EXCEPTION 'Could not issue first lead-linked approval';
  END IF;

  v_first := public.execute_approved_task_action(
    repeat('7', 64),
    'legacy:73000000-0000-4000-8000-000000000005',
    v_first_operation,
    jsonb_build_object(
      'type', 'create', 'operation_id', v_first_operation,
      'title', 'Lead research validation', 'priority', 'normal',
      'due_at', NULL, 'notes', 'Grounded internal review',
      'lead_id', v_lead
    )
  );

  IF v_first ->> 'status' IS DISTINCT FROM 'success'
     OR (SELECT lead_id FROM public.tasks WHERE operation_id = v_first_operation) IS DISTINCT FROM v_lead THEN
    RAISE EXCEPTION 'Created task was not linked to its lead';
  END IF;

  IF NOT public.issue_pending_approval(
    repeat('8', 64),
    'legacy:73000000-0000-4000-8000-000000000006',
    jsonb_build_object(
      'type', 'create', 'operation_id', v_second_operation,
      'title', 'Duplicate initial review', 'priority', 'normal',
      'due_at', NULL, 'notes', 'Should be blocked',
      'lead_id', v_lead
    ),
    300
  ) THEN
    RAISE EXCEPTION 'Could not issue second lead-linked approval';
  END IF;

  v_second := public.execute_approved_task_action(
    repeat('8', 64),
    'legacy:73000000-0000-4000-8000-000000000006',
    v_second_operation,
    jsonb_build_object(
      'type', 'create', 'operation_id', v_second_operation,
      'title', 'Duplicate initial review', 'priority', 'normal',
      'due_at', NULL, 'notes', 'Should be blocked',
      'lead_id', v_lead
    )
  );

  IF v_second ->> 'status' IS DISTINCT FROM 'blocked'
     OR (SELECT count(*) FROM public.tasks WHERE lead_id = v_lead AND status = 'open') <> 1 THEN
    RAISE EXCEPTION 'A second open task for the same lead was not blocked';
  END IF;

  UPDATE public.tasks SET status = 'done', completed_at = clock_timestamp()
   WHERE operation_id = v_first_operation;

  IF NOT public.issue_pending_approval(
    repeat('9', 64),
    'legacy:73000000-0000-4000-8000-000000000007',
    jsonb_build_object(
      'type', 'create', 'operation_id', v_third_operation,
      'title', 'Next workflow stage', 'priority', 'normal',
      'due_at', NULL, 'notes', 'Allowed after previous task completion',
      'lead_id', v_lead
    ),
    300
  ) THEN
    RAISE EXCEPTION 'Could not issue subsequent-stage approval';
  END IF;

  v_third := public.execute_approved_task_action(
    repeat('9', 64),
    'legacy:73000000-0000-4000-8000-000000000007',
    v_third_operation,
    jsonb_build_object(
      'type', 'create', 'operation_id', v_third_operation,
      'title', 'Next workflow stage', 'priority', 'normal',
      'due_at', NULL, 'notes', 'Allowed after previous task completion',
      'lead_id', v_lead
    )
  );

  IF v_third ->> 'status' IS DISTINCT FROM 'success'
     OR (SELECT count(*) FROM public.tasks WHERE lead_id = v_lead AND status = 'open') <> 1 THEN
    RAISE EXCEPTION 'A subsequent workflow task was not allowed after completion';
  END IF;

  IF NOT public.issue_pending_approval(
    repeat('c', 64),
    'legacy:73000000-0000-4000-8000-000000000009',
    jsonb_build_object(
      'type', 'create', 'operation_id', v_bad_operation,
      'title', 'Invalid lead id fixture', 'priority', 'normal',
      'due_at', NULL, 'notes', '', 'lead_id', 'not-a-uuid'
    ),
    300
  ) THEN
    RAISE EXCEPTION 'Could not issue malformed lead-id fixture approval';
  END IF;

  BEGIN
    PERFORM public.execute_approved_task_action(
      repeat('c', 64),
      'legacy:73000000-0000-4000-8000-000000000009',
      v_bad_operation,
      jsonb_build_object(
        'type', 'create', 'operation_id', v_bad_operation,
        'title', 'Invalid lead id fixture', 'priority', 'normal',
        'due_at', NULL, 'notes', '', 'lead_id', 'not-a-uuid'
      )
    );
  EXCEPTION WHEN SQLSTATE '22023' THEN
    v_invalid_rejected := true;
  END;

  IF NOT v_invalid_rejected OR EXISTS (
    SELECT 1 FROM private.task_action_operations WHERE operation_id = v_bad_operation
  ) THEN
    RAISE EXCEPTION 'Malformed lead_id was not rejected before operation creation';
  END IF;

  DELETE FROM public.tasks
   WHERE operation_id IN (v_first_operation, v_second_operation, v_third_operation);
  DELETE FROM private.task_action_operations
   WHERE operation_id IN (v_first_operation, v_second_operation, v_third_operation);
  DELETE FROM private.task_approvals
   WHERE token_hash IN (repeat('7', 64), repeat('8', 64), repeat('9', 64), repeat('c', 64));
  DELETE FROM public.leads WHERE id = v_lead;
END
$lead_linked_task$;
