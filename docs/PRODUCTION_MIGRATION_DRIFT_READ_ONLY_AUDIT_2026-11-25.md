# Production migration drift audit – read-only findings

**Date:** 2026-11-25  
**Project:** `Jarvis` (`kiutreccucbegskxowek`)  
**Database:** PostgreSQL 17.11, project status `ACTIVE_HEALTHY`  
**Repository:** `tamaszsolt2005-hub/jarvis-core`  
**Branch reviewed:** `feat/supabase-auth-rbac-foundation`

## Scope and safety

This is a read-only comparison of the production Supabase migration ledger, live catalog/schema, and repository migration files. No production DDL/DML, migration application, migration repair, privilege change, policy change, Auth provisioning, or flag change was performed.

## 1. Production migration ledger

The live `supabase_migrations.schema_migrations` ledger contains exactly:

| Version | Name | Repository file |
|---|---|---|
| `20261119191911` | `create_jarvis_memory_and_fk_indexes` | Present; ledger matches |
| `20261119192040` | `complete_jarvis_runtime_schema` | Present; ledger matches |
| `20261119192145` | `enable_rls_on_legacy_posts` | Present; ledger matches |
| `20261119192412` | `revoke_anon_authenticated_public_table_and_sequence_privileges` | Present; ledger matches |
| `20261119192559` | `secure_postgres_default_privileges_public_schema` | Present; ledger matches |

These five entries match the five corresponding repository migration filenames.

## 2. Confirmed drift: two migrations have effects but no ledger entries

The two original files shared the same eight-digit version prefix, `20261117`, which made their histories ambiguous: Supabase stores one unique ledger row per version and cannot distinguish two SQL files with the same version. The PR branch has now renamed them to distinct 14-digit versions:

- `20261117090000_add_leads_website.sql`
- `20261117100000_add_logs_level.sql`

Neither new version is present in the production migration ledger. However, live catalog inspection confirms both intended effects exist:

- `public.leads.website text` exists.
- `public.logs.level text NOT NULL DEFAULT 'info'` exists.

This is consistent with **schema changes applied outside tracked migration history**. It is not safe to re-run these files merely to repair history. The intended next action, after the renamed migration files pass the updated isolated CI checks and after explicit approval, is a ledger-only reconciliation marking versions `20261117090000` and `20261117100000` as applied, without executing either SQL file again. The CI workflow has been updated to test each distinct version, applied/reverted/applied behavior, migration-list visibility, and unchanged schema/data in its disposable PostgreSQL fixture. That new CI run is still required before production repair.

## 3. Confirmed pending repository migrations

The following four later migration files are present in the repository but absent from the production ledger. Their key postconditions are also absent from the live schema:

| Version | Migration | Live observation |
|---|---|---|
| `20261120090000` | `expand_logs_audit_fields` | `logs.operation_id/action/status/result/error/approved/recipient/subject/delivery_id` columns are absent |
| `20261123093000` | `admin_audit_access_and_hash_chain` | `logs.previous_hash/entry_hash/actor_user_id` and `public.audit_chain_state` are absent |
| `20261124130000` | `shared_workspace_role_access` | No public RLS policies exist; the migration's role-specific grants and policy set are not active |
| `20261125150000` | `task_creation_idempotency` | `tasks.operation_id` and `tasks_operation_id_uidx` are absent |

The intended dependency order is the listed order. In particular, the RBAC migration declares that the audit schema must exist first. Do not apply the later migrations until the complete chain has been reviewed against the actual production catalog and a verified backup/restore path is available.

## 4. Existing baseline postconditions

Read-only catalog checks confirmed:

- Eight public application tables exist and all eight have RLS enabled.
- `jarvis_memory` and `jarvis_proactive_state` exist.
- `leads.notes` and `leads.source` exist.
- `settings.key` is NOT NULL and `settings.value` is JSONB.
- The legacy `settings.id` integer/sequence model remains in place.
- The `leads.website` and `logs.level` additions exist as noted above.
- No public RLS policies currently exist.
- The checked public tables and `settings_id_seq` do not grant SELECT/INSERT/UPDATE to `anon` or `authenticated`; `service_role` has its expected privileged access.

### Default-privilege scope needs separate review

The default-privilege catalog currently shows restrictive defaults for role `postgres` in schema `public`, but it also shows existing `anon`/`authenticated` defaults for role `supabase_admin` on tables, sequences, and functions. The tracked `20261119192559` migration alters defaults for role `postgres` only. Current application tables are explicitly restricted, but future objects created under a different owner may inherit different defaults. This is a preflight item; do not assume the migration secured every possible object-creating role.

## 5. Recommended reconciliation sequence

1. **Repository version normalization:** the two duplicate `20261117` files have been renamed to `20261117090000` and `20261117100000`; wait for the updated isolated CI migration-repair test to pass.
2. **Ledger-only production repair:** after CI success and explicit approval, mark those two distinct versions as applied without rerunning SQL, then verify the ledger and schema postconditions.
3. **Production backup gate:** before any schema/policy migration, verify the production backup destination, encryption/key access, and a separate restore test. A local CI age round-trip is not a substitute.
4. **Review pending migrations:** inspect SQL and role ownership/default privileges, especially the audit trigger's narrowly scoped `SECURITY DEFINER` function and the RBAC grants/policies. Confirm the live `settings` legacy sequence assumptions.
5. **Apply pending migrations in order:** only after the backup gate and explicit approval. Apply one migration at a time, verify catalog postconditions and security tests, and stop on any unexpected drift.
6. **Keep Auth disabled:** do not provision users or enable the application Auth flag as part of this schema reconciliation. Real Auth/JWT/RLS validation remains a separate gate.

## 6. Approval boundary and status

This report does not authorize writes. The two `20261117` history repairs and the four later production migrations are separate write operations and require explicit approval before execution. Production Auth remains OFF. No new Supabase project, account, or branch was created.
