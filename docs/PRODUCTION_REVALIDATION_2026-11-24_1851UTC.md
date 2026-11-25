# JARVIS production read-only revalidation — 2026-11-24 18:51 UTC

**Project:** `kiutreccucbegskxowek` (Jarvis, `eu-west-1`, PostgreSQL 17.11.0.019)  
**Project status:** `ACTIVE_HEALTHY`  
**Inspection type:** read-only metadata/catalog queries and Supabase project metadata. No DDL, DML, migration repair, Auth provisioning, or configuration change was executed.

## Current findings

### Auth and RLS

- `auth.users`: **0 rows**.
- `public`: **8 tables**.
- RLS is enabled on all 8 tables.
- `pg_policies`: **0 policies** in the public schema.
- Supabase Security Advisor reports **8 `rls_enabled_no_policy` findings**, one for each public table.
- This is a fail-closed posture for roles without direct grants, but it means the proposed user-JWT dashboard cannot perform its intended business operations yet.

### Current public table inventory

| Table | Rows | RLS | Important observed shape |
|---|---:|---|---|
| `leads` | 11 | enabled | Existing consent and follow-up fields; includes `website`, `notes`, `source` |
| `tasks` | 0 | enabled | UUID id, lead FK, title/status/priority and timestamps |
| `email_drafts` | 0 | enabled | UUID id, lead FK, recipient/subject/body/status |
| `logs` | 28 | enabled | Legacy columns only: `id`, `module`, `message`, `created_at`, `level` |
| `settings` | 1 | enabled | Legacy integer `id` backed by `settings_id_seq`, unique `key`, JSONB `value` |
| `jarvis_memory` | 0 | enabled | UUID id, category/content/source/active/created_at |
| `jarvis_proactive_state` | 1 | enabled | Machine-owned key/snapshot/updated_at |
| `posts` | 0 | enabled | Legacy UUID/content/scheduled_for/status/created_at table |

### Audit schema status

- `audit_chain_state`: **does not exist**.
- Structured audit columns on `public.logs` checked in this inspection:
  `operation_id`, `action`, `status`, `result`, `error`, `approved`,
  `recipient`, `subject`, `delivery_id`, `previous_hash`, `entry_hash`,
  `actor_user_id`: **0 of 12 present**.
- The repository's audit expansion, hash-chain, and shared-workspace RBAC migrations remain unapplied to production.

### Remote migration ledger

The remote ledger still contains exactly these five versions whose original SQL source files are not in the repository:

- `20261119191911_create_jarvis_memory_and_fk_indexes`
- `20261119192040_complete_jarvis_runtime_schema`
- `20261119192145_enable_rls_on_legacy_posts`
- `20261119192412_revoke_anon_authenticated_public_table_and_sequence_privileges`
- `20261119192559_secure_postgres_default_privileges_public_schema`

The previously documented `20261117` repository-vs-remote mismatch also remains unresolved. Do not invent historical SQL or use migration repair to hide the discrepancy.

## Consequences and required actions

1. Do not enable `JARVIS_SUPABASE_AUTH_LOGIN_ENABLED` or `JARVIS_AUTH_RBAC_ENFORCED` in production.
2. Do not apply the audit/RBAC migrations, run `supabase db push`, or edit the remote migration ledger until the historical sources and schema drift have been reconciled.
3. Obtain a fresh encrypted production backup, upload verification, decrypt/hash verification, and restore test in a separate isolated PostgreSQL database before any production schema write.
4. Recover the original historical migration files from an authorized developer working copy, deployment artifact, or backup. If unavailable, prepare a separately named, reviewed forward-only baseline/reconciliation proposal.
5. Preserve the legacy `logs`, `settings`, and `posts` structures when designing the forward migration plan.
6. After backup and migration reconciliation, test the user-JWT policies and real Supabase Auth lifecycle in an already-existing, explicitly authorized isolated environment. Do not create a new Supabase project and do not use production as a test environment.

## Change record

This report records the fresh read-only inspection at 18:51 UTC on 2026-11-24. The inspection did not modify the production database, Auth users, migration history, policies, secrets, or AWS resources.

## Follow-up catalog checks and migration-source recovery — 2026-11-24 19:10 UTC

Additional read-only catalog queries confirmed:

- All eight public tables are owned by postgres; RLS is enabled, FORCE ROW LEVEL SECURITY is false, and there are still zero public policies.
- Direct table privileges are present for postgres and service_role only; anon/authenticated have no direct table grants.
- PostgreSQL default privileges for postgres in public are restricted to postgres and service_role for tables, sequences and functions; no PUBLIC, anon or authenticated default grants were observed.
- No public-schema functions or triggers were present at this inspection; the only public sequence was settings_id_seq.
- The remote migration ledger stores the SQL statement arrays for all five historical versions previously missing from Git. Their exact SQL statements were recovered read-only and the versioned files restored to the repository. The ledger rollback field was NULL for these five versions.

Recovered sources:
- 20261119191911_create_jarvis_memory_and_fk_indexes.sql
- 20261119192040_complete_jarvis_runtime_schema.sql
- 20261119192145_enable_rls_on_legacy_posts.sql
- 20261119192412_revoke_anon_authenticated_public_table_and_sequence_privileges.sql
- 20261119192559_secure_postgres_default_privileges_public_schema.sql

No production DDL, DML, Auth provisioning, policy change or migration-ledger repair was performed. The two repo-only 20261117 versions remain absent from the remote ledger, and audit/RBAC migrations remain unapplied.
