# JARVIS production Supabase schema snapshot

**Captured:** 2026-11-25 09:13 UTC  
**Project:** \`Jarvis\` / \`kiutreccucbegskxowek\` / \`eu-west-1\`  
**Database:** PostgreSQL 17.11  
**Method:** Supabase catalog and schema metadata reads only. No application row contents, credentials, or secrets were selected. No production writes were performed.

## 1. Executive state

| Check | Observed result |
|---|---:|
| Public application tables | 8 |
| Tables with RLS enabled | 8 |
| Tables with FORCE RLS | 0 |
| Public RLS policies | 0 |
| Public triggers | 0 |
| Public functions | 0 |
| Supabase Auth users | 0 |
| Public sequences | 1 |
| Remote application migration versions | 5 |
| \`audit_chain_state\` | Absent |
| Structured audit/hash columns in \`logs\` | Absent |

The current Supabase Security Advisor reports **8 \`rls_enabled_no_policy\` findings**, one for each public application table. RLS being enabled without policies is not a completed authorization design; do not enable dashboard Auth until the RBAC migration is applied and verified in an isolated environment.

## 2. Public table inventory

All eight relations are owned by \`postgres\`; RLS is enabled and FORCE RLS is disabled.

| Table | Columns (name: type; * = nullable) | Primary key |
|---|---|---|
| \`leads\` | \`id: uuid\`, \`company_name: text\`, \`email: text*\`, \`status: text*\`, \`created_at: timestamptz\`, \`consent_basis: text*\`, \`approved_to_contact: bool\`, \`consent_confirmed_at: timestamptz*\`, \`opted_out: bool\`, \`first_sent_at: timestamptz*\`, \`next_follow_up_at: timestamptz*\`, \`follow_up_count: int\`, \`followed_up_at: timestamptz*\`, \`last_message_id: text*\`, \`last_inbound_message_id: text*\`, \`reply_category: text*\`, \`updated_at: timestamptz\`, \`website: text*\`, \`notes: text*\`, \`source: text*\` | \`id\` |
| \`posts\` | \`id: uuid\`, \`content: text\`, \`scheduled_for: timestamptz*\`, \`status: text*\`, \`created_at: timestamptz\` | \`id\` |
| \`logs\` | \`id: uuid\`, \`module: text\`, \`message: text\`, \`created_at: timestamptz\`, \`level: text\` | \`id\` |
| \`settings\` | \`id: integer\`, \`key: text\`, \`value: jsonb*\`, \`updated_at: timestamp*\` | \`id\` |
| \`tasks\` | \`id: uuid\`, \`lead_id: uuid*\`, \`title: text\`, \`notes: text*\`, \`priority: text\`, \`status: text\`, \`due_at: timestamptz*\`, \`completed_at: timestamptz*\`, \`created_at: timestamptz\`, \`updated_at: timestamptz\` | \`id\` |
| \`email_drafts\` | \`id: uuid\`, \`lead_id: uuid*\`, \`recipient: text\`, \`subject: text\`, \`body: text\`, \`status: text\`, \`created_at: timestamptz\`, \`updated_at: timestamptz\` | \`id\` |
| \`jarvis_memory\` | \`id: uuid\`, \`category: text\`, \`content: text\`, \`source: text\`, \`active: bool\`, \`created_at: timestamptz\` | \`id\` |
| \`jarvis_proactive_state\` | \`key: text\`, \`snapshot: jsonb\`, \`updated_at: timestamptz\` | \`key\` |

The table tool reported approximate/current row counts at capture: leads 11, logs 29, settings 1, jarvis_proactive_state 1; the other four tables were empty. These counts are operational metadata, not a data export.

### Production-specific shape that must be preserved

- \`settings.id\` is an integer primary key backed by \`public.settings_id_seq\`; \`key\` has a separate unique constraint. Do not replace this table with a key-primary-key bootstrap definition.
- \`posts\` is a live legacy table and must remain present.
- \`leads.website\` and \`logs.level\` exist even though the two corresponding repository migration versions are absent from the remote ledger.
- \`logs\` has only the five legacy columns listed above. It does not yet contain \`operation_id\`, \`action\`, \`status\`, \`result\`, \`error\`, \`approved\`, \`recipient\`, \`subject\`, \`delivery_id\`, \`previous_hash\`, \`entry_hash\`, or \`actor_user_id\`.
- \`public.audit_chain_state\` does not exist.

## 3. Constraints, indexes, and sequence

### Foreign keys and checks

| Table | Constraint | Definition |
|---|---|---|
| \`email_drafts\` | \`email_drafts_lead_id_fkey\` | \`FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE SET NULL\` |
| \`tasks\` | \`tasks_lead_id_fkey\` | \`FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE SET NULL\` |
| \`email_drafts\` | \`email_drafts_status_check\` | status in draft / approved / archived |
| \`jarvis_memory\` | \`jarvis_memory_content_check\` | content length 1..700 |
| \`tasks\` | \`tasks_priority_check\` | priority in normal / high / urgent |
| \`tasks\` | \`tasks_status_check\` | status in open / done / cancelled |
| \`settings\` | \`settings_key_key\` | UNIQUE (key) |

All tables also have their listed primary-key constraints.

### Indexes

- \`email_drafts_created_idx\` – \`email_drafts(created_at DESC)\`
- \`email_drafts_lead_id_idx\` – \`email_drafts(lead_id)\`
- \`email_drafts_pkey\`
- \`jarvis_memory_active_created_idx\` – \`jarvis_memory(active, created_at DESC)\`
- \`jarvis_memory_pkey\`
- \`jarvis_proactive_state_pkey\`
- \`leads_email_idx\` – \`lower(email)\`
- \`leads_next_follow_up_idx\` – \`next_follow_up_at\`
- \`leads_pkey\`
- \`leads_status_idx\` – \`status\`
- \`logs_pkey\`
- \`posts_pkey\`
- \`settings_key_key\`
- \`settings_pkey\`
- \`tasks_lead_id_idx\` – \`tasks(lead_id)\`
- \`tasks_pkey\`
- \`tasks_status_due_idx\` – \`tasks(status, due_at)\`

Public sequence: \`settings_id_seq integer\`.

## 4. RLS, grants, and default ACLs

- Every existing public application table has RLS enabled; none has FORCE RLS.
- The catalog returned zero public RLS policies, triggers, or functions.
- Existing direct table grants are restricted to \`postgres\` and \`service_role\`; no direct \`anon\` or \`authenticated\` table grants were returned.
- The \`postgres\` owner-specific public-schema default ACLs are restricted to \`postgres\` and \`service_role\` for tables, sequences, and functions.
- Catalog entries for platform-managed \`supabase_admin\` show default grants to \`anon\` and \`authenticated\` for tables, sequences, and function execution. This is a Supabase-reserved owner context; do not try to change its defaults using a project migration. Ensure project migrations create objects under the intended project-controlled owner and verify resulting object ownership/ACLs.
- Installed extensions reported: \`pg_stat_statements 1.11\`, \`pgcrypto 1.3\`, \`plpgsql 1.0\`, \`supabase_vault 0.3.2\`, \`uuid-ossp 1.1\`.

## 5. Remote migration ledger versus repository

Remote ledger (exact five versions):

1. \`20261119191911_create_jarvis_memory_and_fk_indexes\`
2. \`20261119192040_complete_jarvis_runtime_schema\`
3. \`20261119192145_enable_rls_on_legacy_posts\`
4. \`20261119192412_revoke_anon_authenticated_public_table_and_sequence_privileges\`
5. \`20261119192559_secure_postgres_default_privileges_public_schema\`

Repository-only migration files not present in this remote ledger:

- \`20261117_add_leads_website.sql\` – its column effect is already present.
- \`20261117_add_logs_level.sql\` – its column effect is already present.
- \`20261120090000_expand_logs_audit_fields.sql\` – not applied; expected audit columns are absent.
- \`20261123093000_admin_audit_access_and_hash_chain.sql\` – not applied; hash columns, chain table, and triggers are absent.
- \`20261124130000_shared_workspace_role_access.sql\` – not applied; requires the audit schema above.

The two 20261117 effects being present does **not** prove when or by which migration they were applied. Do not execute them again in production or silently rewrite the ledger. Their history reconciliation requires a separately reviewed, evidence-backed baseline/repair decision.

## 6. Safe migration order and recovery

1. Preserve this snapshot and obtain a fresh encrypted backup.
2. In an isolated PostgreSQL 17 / Supabase test branch, verify the two 20261117 idempotent effects and record the test branch's ledger behavior. Do not modify production history yet.
3. Apply/validate audit-field expansion (\`20261120090000\`).
4. Apply/validate hash-chain/admin audit access (\`20261123093000\`).
5. Apply/validate shared-workspace RBAC (\`20261124130000\`).
6. Check exact table/column/constraint/index state, grants, owner/default ACLs, policies, function execution ACLs, triggers, legacy log preservation, and audit-chain verification.
7. Prepare a forward-only recovery plan. The five recovered historical migrations have NULL rollback fields; do not assume automatic rollback exists.
8. Only after a fresh backup, exact SQL review, controlled change window, and separate explicit production approval may production migration history or schema be changed.
9. After deployment, repeat read-only catalog checks and real JWT tests; keep dashboard Auth disabled until all checks pass.

## 7. Evidence boundary

This snapshot is a schema/catalog snapshot, not a full \`pg_dump\`, not a production backup, and not an authorization test. It deliberately excludes application row contents, Auth secrets, and Storage object binaries. The separate backup workflow must verify the encrypted S3 object and restore it into a clean, isolated PostgreSQL 17 target. Real JWT tests must use a disposable Supabase branch with real Auth-issued tokens and PostgREST requests.

**Safety:** no production DDL/DML, migration repair, Auth-user provisioning, RLS policy change, or feature-flag activation was performed.
