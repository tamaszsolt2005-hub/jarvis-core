# Supabase production audit — 2026-11-23

**Scope:** read-only inspection of the existing Jarvis Supabase project and GitHub repository.
**Database writes:** none.
**Application row contents:** not queried for this report.
**Native SQL schema dump:** not produced; the connected tools exposed catalog metadata, not a native `pg_dump --schema-only` artifact.
**New Supabase project/branch:** none.

## Project and platform

- Project status: `ACTIVE_HEALTHY`.
- Region: `eu-west-1`.
- PostgreSQL: `17.11.0.019` (major version 17).
- Supabase development branches: none.
- Edge Functions: none listed.

## Migration ledger versus repository

The remote migration ledger contains five versions:

| Version | Recorded name |
|---|---|
| `20261119191911` | `create_jarvis_memory_and_fk_indexes` |
| `20261119192040` | `complete_jarvis_runtime_schema` |
| `20261119192145` | `enable_rls_on_legacy_posts` |
| `20261119192412` | `revoke_anon_authenticated_public_table_and_sequence_privileges` |
| `20261119192559` | `secure_postgres_default_privileges_public_schema` |

The repository's migration directory contains only the two 2026-11-17 migrations and the two audit migrations from 2026-11-20 and 2026-11-23. The five historical source files are still absent. The ledger's names do not prove the SQL statements that were applied.

## Current public schema findings

Eight application tables were found: `leads`, `tasks`, `email_drafts`, `logs`, `settings`, `jarvis_memory`, `jarvis_proactive_state`, and `posts`.

- RLS is enabled on all eight tables.
- No RLS policies exist on any of the eight tables.
- Current direct table grants were only observed for `postgres` and `service_role`; `anon` and `authenticated` had no direct table grants in the inspected ACLs.
- All eight application tables are owned by `postgres`.
- The live `logs` table has only the legacy columns `id`, `module`, `message`, `created_at`, and `level`. Structured audit and hash-chain columns are absent.
- The repository's audit migrations add structured audit fields, admin-only read policy, chain state, hash-chain triggers, and append-only protection. They are not reflected in the inspected production schema.
- Live `settings` has integer `id` primary key, unique `key`, JSONB `value`, and `updated_at`; repository schema defines `key` as the primary key.
- Live `posts` exists but is not represented in `supabase/schema.sql`.
- Live `tasks` and `email_drafts` contain lead-ID indexes not represented in the repository snapshot.
- The inspected public default ACL catalog contains entries for both `supabase_admin` and `postgres`; the existing application tables are postgres-owned. Future object privileges must be reviewed by object owner and creation path.

## Supabase Advisors

### Security

The Security Advisor reported one INFO-level lint category, `rls_enabled_no_policy`, affecting all eight public tables. This is consistent with the catalog inspection. It is not evidence that RLS should be disabled: the correct policies and grants must be designed from the actual application access model.

### Performance

The Performance Advisor reported seven INFO-level unused-index findings:

- `leads_status_idx`
- `leads_next_follow_up_idx`
- `leads_email_idx`
- `tasks_status_due_idx`
- `tasks_lead_id_idx`
- `email_drafts_created_idx`
- `email_drafts_lead_id_idx`

These are candidates for workload review, not automatic drop recommendations. Low or absent usage may reflect a quiet workload or recent index creation. Do not remove them without query-plan and workload evidence.

### Health

The Health Advisor returned no findings at the time of inspection. This does not replace application-level monitoring or backup/restore verification.

## Application integration findings

- The shared server-side helper initializes the Supabase client using `SUPABASE_SERVICE_ROLE_KEY`, with a fallback to `SUPABASE_KEY`. The service-role key bypasses RLS and must remain server-side.
- The separate audit-admin client uses a publishable/anon key and a verified Auth session, then reads `logs` through the user's JWT and admin `app_metadata` claim.
- The production audit schema currently lacks the columns and policy that this UI expects. Therefore the audit UI cannot be considered production-ready against the inspected schema.
- The repository RBAC design document explicitly says the full admin/operator/reader model is not active; the main application modules still use the service-role client.
- Prior read-only inventory found no Auth users. No Auth users or secrets were inspected or changed during this audit.

## Required remediation gates

1. Obtain a native schema-only dump using a reviewed, supported workflow. Do not treat this catalog report as a complete SQL export.
2. Build a per-object reconciliation matrix using the dump, repository schema, migrations, and ledger. Do not recreate the five missing migrations from their names.
3. Decide and document the intended access model for each table and each application pathway. Do not add blanket `TO authenticated USING (true)` policies.
4. Separate service-role backend operations from user-JWT operations. Keep service-role credentials out of browser/client contexts.
5. Design forward-only migrations only after the schema and access model are reconciled. Generate migration files with the supported Supabase CLI workflow.
6. Validate RLS with real role/JWT tests and negative cases. No isolated Supabase test project or branch was created; database-level policy validation remains blocked.
7. Verify an encrypted backup and a restore into a separate approved target before production rollout. The AWS backup stack and successful backup/restore remain unverified.
8. Apply production changes only in a reviewed change window with a verified recovery path and explicit approval of the exact migration set.

## Current disposition

This report records findings; it does not authorize production changes. Do not run `supabase db push`, rewrite migration history, apply unreviewed DDL, change grants/policies, remove indexes, or claim backup/restore readiness on the basis of this inspection alone.
