-- Atomic one-use approvals and idempotent task execution.
-- Approval tokens are stored only as SHA-256 hashes. The raw token remains
-- in the server-side Streamlit session and is never persisted or logged.

CREATE SCHEMA IF NOT EXISTS private;
REVOKE ALL ON SCHEMA private FROM PUBLIC, anon, authenticated, service_role;

CREATE TABLE IF NOT EXISTS private.task_approvals (
  token_hash text PRIMARY KEY CHECK (token_hash ~ '^[0-9a-f]{64}$'),
  principal text NOT NULL,
  payload_hash text NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  expires_at timestamptz NOT NULL,
  consumed_at timestamptz,
  CHECK (expires_at > created_at)
);

CREATE INDEX IF NOT EXISTS task_approvals_expiry_idx
  ON private.task_approvals (expires_at);
CREATE INDEX IF NOT EXISTS task_approvals_consumed_idx
  ON private.task_approvals (consumed_at)
  WHERE consumed_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS private.task_action_operations (
  operation_id uuid PRIMARY KEY,
  principal text NOT NULL,
  payload_hash text NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
  result jsonb,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  completed_at timestamptz
);

ALTER TABLE private.task_approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE private.task_action_operations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE private.task_approvals, private.task_action_operations
  FROM PUBLIC, anon, authenticated, service_role;

CREATE OR REPLACE FUNCTION private.assert_task_approval_principal(
  p_principal text,
  p_require_writer boolean DEFAULT true
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
  caller_role text := COALESCE(auth.jwt() ->> 'role', '');
  caller_id uuid;
  trusted_role text := COALESCE(auth.jwt() -> 'app_metadata' ->> 'role', '');
BEGIN
  IF p_principal IS NULL OR p_require_writer IS NULL THEN
    RAISE EXCEPTION 'Approval principal and permission mode are required'
      USING ERRCODE = '42501';
  END IF;
  IF caller_role = 'authenticated' THEN
    caller_id := auth.uid();
    IF caller_id IS NULL OR p_principal IS DISTINCT FROM ('auth:' || caller_id::text) THEN
      RAISE EXCEPTION 'Approval principal does not match the authenticated user'
        USING ERRCODE = '42501';
    END IF;
    IF p_require_writer AND trusted_role NOT IN ('admin', 'operator') THEN
      RAISE EXCEPTION 'The current application role cannot approve task actions'
        USING ERRCODE = '42501';
    END IF;
    RETURN caller_id;
  ELSIF caller_role = 'service_role' THEN
    IF p_principal IS NULL OR p_principal !~* '^(legacy|auth):[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$' THEN
      RAISE EXCEPTION 'Invalid server-side approval principal'
        USING ERRCODE = '42501';
    END IF;
    RETURN NULL;
  END IF;

  RAISE EXCEPTION 'A verified user session or trusted service role is required'
    USING ERRCODE = '42501';
END;
$$;

REVOKE ALL ON FUNCTION private.assert_task_approval_principal(text, boolean)
  FROM PUBLIC, anon, authenticated, service_role;

CREATE OR REPLACE FUNCTION public.issue_pending_approval(
  p_token_hash text,
  p_principal text,
  p_payload jsonb,
  p_ttl_seconds integer DEFAULT 300
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
  v_actor uuid;
  v_payload_hash text;
  v_rows integer;
  v_existing private.task_approvals%ROWTYPE;
BEGIN
  v_actor := private.assert_task_approval_principal(p_principal, true);
  IF p_token_hash IS NULL OR p_token_hash !~ '^[0-9a-f]{64}$'
     OR p_payload IS NULL OR jsonb_typeof(p_payload) <> 'object'
     OR p_ttl_seconds IS NULL OR p_ttl_seconds < 30 OR p_ttl_seconds > 600 THEN
    RAISE EXCEPTION 'Invalid pending approval input' USING ERRCODE = '22023';
  END IF;

  v_payload_hash := encode(
    extensions.digest(convert_to(p_payload::text, 'UTF8'), 'sha256'),
    'hex'
  );

  DELETE FROM private.task_approvals
   WHERE expires_at < clock_timestamp() - interval '1 day'
      OR consumed_at < clock_timestamp() - interval '7 days';

  INSERT INTO private.task_approvals (
    token_hash, principal, payload_hash, expires_at
  )
  VALUES (
    p_token_hash, p_principal, v_payload_hash,
    clock_timestamp() + make_interval(secs => p_ttl_seconds)
  )
  ON CONFLICT (token_hash) DO NOTHING;

  GET DIAGNOSTICS v_rows = ROW_COUNT;
  IF v_rows = 1 THEN
    RETURN true;
  END IF;

  SELECT * INTO v_existing
    FROM private.task_approvals
   WHERE token_hash = p_token_hash;
  RETURN FOUND
     AND v_existing.principal = p_principal
     AND v_existing.payload_hash = v_payload_hash
     AND v_existing.consumed_at IS NULL
     AND v_existing.expires_at > clock_timestamp();
END;
$$;

CREATE OR REPLACE FUNCTION public.consume_pending_approval(
  p_token_hash text,
  p_principal text,
  p_payload jsonb
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
  v_payload_hash text;
  v_actor uuid;
BEGIN
  v_actor := private.assert_task_approval_principal(p_principal, true);
  IF p_token_hash IS NULL OR p_token_hash !~ '^[0-9a-f]{64}$'
     OR p_payload IS NULL OR jsonb_typeof(p_payload) <> 'object' THEN
    RAISE EXCEPTION 'Invalid pending approval input' USING ERRCODE = '22023';
  END IF;

  v_payload_hash := encode(
    extensions.digest(convert_to(p_payload::text, 'UTF8'), 'sha256'),
    'hex'
  );

  UPDATE private.task_approvals
     SET consumed_at = clock_timestamp()
   WHERE token_hash = p_token_hash
     AND principal = p_principal
     AND payload_hash = v_payload_hash
     AND consumed_at IS NULL
     AND expires_at > clock_timestamp();

  RETURN FOUND;
END;
$$;

CREATE OR REPLACE FUNCTION public.revoke_pending_approval(
  p_token_hash text,
  p_principal text
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
  v_actor uuid;
BEGIN
  v_actor := private.assert_task_approval_principal(p_principal, false);
  IF p_token_hash IS NULL OR p_token_hash !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION 'Invalid pending approval token' USING ERRCODE = '22023';
  END IF;

  UPDATE private.task_approvals
     SET consumed_at = clock_timestamp()
   WHERE token_hash = p_token_hash
     AND principal = p_principal
     AND consumed_at IS NULL;
  RETURN FOUND;
END;
$$;

CREATE OR REPLACE FUNCTION public.execute_approved_task_action(
  p_token_hash text,
  p_principal text,
  p_operation_id uuid,
  p_action jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
  v_actor uuid;
  v_type text;
  v_payload_hash text;
  v_stored_principal text;
  v_stored_hash text;
  v_stored_result jsonb;
  v_task_id uuid;
  v_lead_id uuid;
  v_title text;
  v_status text;
  v_result jsonb;
  v_rows integer;
  v_approval_consumed boolean := false;
BEGIN
  v_actor := private.assert_task_approval_principal(p_principal, true);

  IF p_token_hash IS NULL OR p_token_hash !~ '^[0-9a-f]{64}$'
     OR p_operation_id IS NULL
     OR p_action IS NULL
     OR jsonb_typeof(p_action) IS DISTINCT FROM 'object' THEN
    RAISE EXCEPTION 'Invalid task action input' USING ERRCODE = '22023';
  END IF;
  IF jsonb_typeof(p_action -> 'operation_id') IS DISTINCT FROM 'string'
     OR (p_action ->> 'operation_id')::uuid IS DISTINCT FROM p_operation_id THEN
    RAISE EXCEPTION 'Invalid task operation identifier' USING ERRCODE = '22023';
  END IF;

  v_type := p_action ->> 'type';
  IF v_type IS NULL OR v_type NOT IN ('create', 'update', 'close') THEN
    RAISE EXCEPTION 'Unsupported task action' USING ERRCODE = '22023';
  END IF;

  IF EXISTS (
    SELECT 1 FROM jsonb_object_keys(p_action) AS item(key)
     WHERE CASE
       WHEN key IN ('type', 'operation_id') THEN true
       WHEN v_type = 'create' THEN key IN ('title', 'priority', 'due_at', 'notes', 'lead_id')
       WHEN v_type = 'close' THEN key = 'id'
       WHEN v_type = 'update' THEN key IN ('id', 'updates')
       ELSE false
     END IS NOT TRUE
  ) THEN
    RAISE EXCEPTION 'Task action contains unsupported fields' USING ERRCODE = '22023';
  END IF;

  IF v_type = 'create' THEN
    IF jsonb_typeof(p_action -> 'title') IS DISTINCT FROM 'string'
       OR length(btrim(p_action ->> 'title')) NOT BETWEEN 1 AND 180
       OR COALESCE(p_action ->> 'priority', '') NOT IN ('normal', 'high', 'urgent')
       OR (p_action ? 'notes' AND (
         jsonb_typeof(p_action -> 'notes') <> 'string'
         OR length(p_action ->> 'notes') > 1000
       ))
       OR (p_action ? 'lead_id' AND (
         jsonb_typeof(p_action -> 'lead_id') IS DISTINCT FROM 'string'
         OR length(p_action ->> 'lead_id') <> 36
         OR (p_action ->> 'lead_id') !~ '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}'
       ))
       OR (p_action ? 'due_at' AND CASE
         WHEN jsonb_typeof(p_action -> 'due_at') = 'null' THEN false
         WHEN jsonb_typeof(p_action -> 'due_at') = 'string' THEN
           CASE
             WHEN (p_action ->> 'due_at') ~ '(Z|[+-][0-9]{2}:[0-9]{2})$'
               THEN (p_action ->> 'due_at')::timestamptz IS NULL
             ELSE true
           END
         ELSE true
       END) THEN
      RAISE EXCEPTION 'Invalid task creation payload' USING ERRCODE = '22023';
    END IF;
  ELSIF v_type = 'close' THEN
    IF jsonb_typeof(p_action -> 'id') IS DISTINCT FROM 'string'
       OR (p_action ->> 'id')::uuid IS NULL THEN
      RAISE EXCEPTION 'Invalid task identifier' USING ERRCODE = '22023';
    END IF;
  ELSE
    IF jsonb_typeof(p_action -> 'updates') IS DISTINCT FROM 'object' THEN
      RAISE EXCEPTION 'Invalid task update payload' USING ERRCODE = '22023';
    END IF;
    IF jsonb_typeof(p_action -> 'id') IS DISTINCT FROM 'string'
       OR (p_action ->> 'id')::uuid IS NULL
       OR p_action -> 'updates' = '{}'::jsonb
       OR EXISTS (
         SELECT 1 FROM jsonb_object_keys(p_action -> 'updates') AS item(key)
          WHERE key NOT IN ('title', 'priority', 'due_at', 'notes')
       )
       OR (p_action -> 'updates' ? 'title' AND (
         jsonb_typeof(p_action -> 'updates' -> 'title') IS DISTINCT FROM 'string'
         OR length(btrim(p_action -> 'updates' ->> 'title')) NOT BETWEEN 1 AND 180
       ))
       OR (p_action -> 'updates' ? 'priority' AND
         COALESCE(p_action -> 'updates' ->> 'priority', '') NOT IN ('normal', 'high', 'urgent'))
       OR (p_action -> 'updates' ? 'notes' AND (
         jsonb_typeof(p_action -> 'updates' -> 'notes') IS DISTINCT FROM 'string'
         OR length(btrim(p_action -> 'updates' ->> 'notes')) NOT BETWEEN 1 AND 1000
       ))
       OR (p_action -> 'updates' ? 'due_at' AND CASE
         WHEN jsonb_typeof(p_action -> 'updates' -> 'due_at') = 'string' THEN
           CASE
             WHEN (p_action -> 'updates' ->> 'due_at') ~ '(Z|[+-][0-9]{2}:[0-9]{2})$'
               THEN (p_action -> 'updates' ->> 'due_at')::timestamptz IS NULL
             ELSE true
           END
         ELSE true
       END) THEN
      RAISE EXCEPTION 'Invalid task update payload' USING ERRCODE = '22023';
    END IF;
  END IF;

  v_payload_hash := encode(
    extensions.digest(convert_to(p_action::text, 'UTF8'), 'sha256'),
    'hex'
  );

  -- This insert serializes concurrent submissions with the same operation ID.
  -- A competing transaction waits for the first one, then reads its result.
  INSERT INTO private.task_action_operations (
    operation_id, principal, payload_hash
  )
  VALUES (p_operation_id, p_principal, v_payload_hash)
  ON CONFLICT (operation_id) DO NOTHING;

  SELECT principal, payload_hash, result
    INTO v_stored_principal, v_stored_hash, v_stored_result
    FROM private.task_action_operations
   WHERE operation_id = p_operation_id
   FOR UPDATE;

  IF v_stored_principal IS DISTINCT FROM p_principal
     OR v_stored_hash IS DISTINCT FROM v_payload_hash THEN
    RAISE EXCEPTION 'Operation ID was already used for a different principal or payload'
      USING ERRCODE = '23505';
  END IF;

  IF v_stored_result IS NOT NULL THEN
    RETURN v_stored_result;
  END IF;

  UPDATE private.task_approvals
     SET consumed_at = clock_timestamp()
   WHERE token_hash = p_token_hash
     AND principal = p_principal
     AND payload_hash = v_payload_hash
     AND consumed_at IS NULL
     AND expires_at > clock_timestamp()
  RETURNING true INTO v_approval_consumed;

  IF NOT COALESCE(v_approval_consumed, false) THEN
    RAISE EXCEPTION 'Approval is missing, expired, already consumed, or bound to another payload'
      USING ERRCODE = '42501';
  END IF;

  -- Acquire the per-lead lock before the global audit-chain insert. This keeps
  -- concurrent attempts for one lead serialized without relying on audit-chain
  -- serialization, while preserving the transaction's fail-closed behavior.
  IF v_type = 'create' AND p_action ? 'lead_id' THEN
    v_lead_id := (p_action ->> 'lead_id')::uuid;
    PERFORM pg_advisory_xact_lock(hashtextextended(v_lead_id::text, 0));
    IF NOT EXISTS (SELECT 1 FROM public.leads WHERE id = v_lead_id) THEN
      v_status := 'blocked';
      v_result := jsonb_build_object(
        'ok', false, 'status', 'blocked',
        'message', 'A kapcsolódó lead nem található; nem történt feladat-létrehozás.',
        'lead_id', v_lead_id
      );
    ELSIF EXISTS (
      SELECT 1 FROM public.tasks
       WHERE lead_id = v_lead_id AND status = 'open'
    ) THEN
      v_status := 'blocked';
      v_result := jsonb_build_object(
        'ok', false, 'status', 'blocked',
        'message', 'Ehhez a leadhez már tartozik nyitott feladat; újabb első lépést nem hoztam létre.',
        'lead_id', v_lead_id
      );
    END IF;
  END IF;

  INSERT INTO public.logs (
    module, level, message, operation_id, action, status,
    result, approved, actor_user_id, created_at
  )
  VALUES (
    'task_actions', 'info', 'audit:task_' || v_type || '|status=pending',
    p_operation_id, 'task_' || v_type, 'pending',
    jsonb_build_object('task_id', p_action ->> 'id', 'title', p_action ->> 'title', 'lead_id', p_action ->> 'lead_id'),
    true, v_actor, clock_timestamp()
  );

  IF v_type = 'create' THEN
    v_title := p_action ->> 'title';

    IF v_status IS DISTINCT FROM 'blocked' THEN
      BEGIN
        INSERT INTO public.tasks (
          lead_id, title, priority, due_at, notes, status, operation_id
        )
        VALUES (
          v_lead_id,
          v_title,
          p_action ->> 'priority',
          CASE WHEN jsonb_typeof(p_action -> 'due_at') = 'string'
               THEN (p_action ->> 'due_at')::timestamptz ELSE NULL END,
          NULLIF(p_action ->> 'notes', ''),
          'open',
          p_operation_id
        )
        RETURNING id INTO v_task_id;
        v_status := 'success';
      EXCEPTION WHEN unique_violation THEN
        SELECT id, title INTO v_task_id, v_title
          FROM public.tasks
         WHERE operation_id = p_operation_id
           AND lead_id IS NOT DISTINCT FROM v_lead_id
           AND title = p_action ->> 'title'
           AND priority = p_action ->> 'priority'
           AND due_at IS NOT DISTINCT FROM
               CASE WHEN p_action ? 'due_at' THEN (p_action ->> 'due_at')::timestamptz ELSE NULL END
           AND notes IS NOT DISTINCT FROM NULLIF(p_action ->> 'notes', '');
        IF NOT FOUND THEN
          RAISE;
        END IF;
        v_status := 'success';
      END;
      v_result := jsonb_build_object(
        'ok', true, 'status', v_status,
        'message', 'Feladat létrehozva: ' || v_title || ' (azonosító: ' || v_task_id::text || ').',
        'task_id', v_task_id,
        'lead_id', v_lead_id
      );
    END IF;
  ELSE
    v_task_id := (p_action ->> 'id')::uuid;
    SELECT title, status INTO v_title, v_status
      FROM public.tasks
     WHERE id = v_task_id
     FOR UPDATE;

    IF NOT FOUND THEN
      v_status := 'blocked';
      v_result := jsonb_build_object(
        'ok', false, 'status', 'blocked',
        'message', 'A feladat nem található; nem történt módosítás.',
        'task_id', v_task_id
      );
    ELSIF v_status <> 'open' THEN
      v_status := 'blocked';
      v_result := jsonb_build_object(
        'ok', false, 'status', 'blocked',
        'message', 'A feladat már nem nyitott; az előkészített műveletet nem hajtottam végre.',
        'task_id', v_task_id
      );
    ELSIF v_type = 'close' THEN
      UPDATE public.tasks
         SET status = 'done',
             completed_at = clock_timestamp(),
             updated_at = clock_timestamp()
       WHERE id = v_task_id AND status = 'open';
      GET DIAGNOSTICS v_rows = ROW_COUNT;
      IF v_rows <> 1 THEN
        v_status := 'blocked';
        v_result := jsonb_build_object(
          'ok', false, 'status', 'blocked',
          'message', 'A feladat állapota időközben megváltozott; nem történt lezárás.',
          'task_id', v_task_id
        );
      ELSE
        v_status := 'success';
        v_result := jsonb_build_object(
          'ok', true, 'status', 'success',
          'message', 'Feladat lezárva: ' || COALESCE(v_title, v_task_id::text) || '.',
          'task_id', v_task_id
        );
      END IF;
    ELSE
      UPDATE public.tasks
         SET title = CASE WHEN p_action -> 'updates' ? 'title'
                          THEN p_action -> 'updates' ->> 'title' ELSE title END,
             priority = CASE WHEN p_action -> 'updates' ? 'priority'
                             THEN p_action -> 'updates' ->> 'priority' ELSE priority END,
             due_at = CASE WHEN p_action -> 'updates' ? 'due_at'
                           THEN (p_action -> 'updates' ->> 'due_at')::timestamptz ELSE due_at END,
             notes = CASE WHEN p_action -> 'updates' ? 'notes'
                          THEN p_action -> 'updates' ->> 'notes' ELSE notes END,
             updated_at = clock_timestamp()
       WHERE id = v_task_id AND status = 'open'
      RETURNING title INTO v_title;
      GET DIAGNOSTICS v_rows = ROW_COUNT;
      IF v_rows <> 1 THEN
        v_status := 'blocked';
        v_result := jsonb_build_object(
          'ok', false, 'status', 'blocked',
          'message', 'A feladat állapota időközben megváltozott; nem történt módosítás.',
          'task_id', v_task_id
        );
      ELSE
        v_status := 'success';
        v_result := jsonb_build_object(
          'ok', true, 'status', 'success',
          'message', 'Feladat módosítva: ' || COALESCE(v_title, v_task_id::text) || '.',
          'task_id', v_task_id
        );
      END IF;
    END IF;
  END IF;

  INSERT INTO public.logs (
    module, level, message, operation_id, action, status,
    result, approved, actor_user_id, created_at
  )
  VALUES (
    'task_actions', CASE WHEN v_status = 'success' THEN 'info' ELSE 'warning' END,
    'audit:task_' || v_type || '|status=' || v_status,
    p_operation_id, 'task_' || v_type, v_status,
    v_result, true, v_actor, clock_timestamp()
  );

  UPDATE private.task_action_operations
     SET result = v_result,
         completed_at = clock_timestamp()
   WHERE operation_id = p_operation_id;

  RETURN v_result;
END;
$$;

REVOKE ALL ON FUNCTION public.issue_pending_approval(text, text, jsonb, integer)
  FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION public.consume_pending_approval(text, text, jsonb)
  FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION public.revoke_pending_approval(text, text)
  FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION public.execute_approved_task_action(text, text, uuid, jsonb)
  FROM PUBLIC, anon, authenticated, service_role;

-- Approval issuance is a server-only operation. The dashboard verifies the
-- signed user session/role first, then calls this RPC with its server-side
-- service-role client. User JWTs can consume/revoke only their own issued token.
GRANT EXECUTE ON FUNCTION public.issue_pending_approval(text, text, jsonb, integer)
  TO service_role;
GRANT EXECUTE ON FUNCTION public.consume_pending_approval(text, text, jsonb)
  TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.revoke_pending_approval(text, text)
  TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.execute_approved_task_action(text, text, uuid, jsonb)
  TO authenticated, service_role;

COMMENT ON TABLE private.task_approvals IS
  'Hashed, principal-bound, short-lived one-use approvals. No client role has table access.';
COMMENT ON TABLE private.task_action_operations IS
  'Durable idempotency ledger for atomic task operations and their replay result.';
