# Production Supabase migration recovery plan

## Scope and safety boundary

This document records a read-only inventory of the production Supabase project
`kiutreccucbegskxowek` (Jarvis, `eu-west-1`, PostgreSQL 17.11) and the safe
sequence for reconciling its migration history with this repository.

**No production DDL, DML, migration repair, or backup configuration is performed
by this plan.** Do not run `supabase db push` until the reconciliation is
reviewed and the exact migration state is proven.

## Verified production facts (2026-11-24 read-only audit)

- Project status: `ACTIVE_HEALTHY`.
- Eight `public` tables were listed: `leads`, `tasks`, `email_drafts`,
  `logs`, `settings`, `jarvis_memory`, `jarvis_proactive_state`, and
  `posts`.
- RLS is enabled on all eight tables; no RLS policies were returned for any
  public table by the catalog audit. The Supabase security advisor independently
  reports eight `rls_enabled_no_policy` findings.
- The live `logs` table contains only the legacy columns
  `id, module, message, created_at, level`. The structured audit fields
  (`operation_id`, `action`, `status`, `result`, `error`, `approved`,
  `recipient`, `subject`, `delivery_id`) and hash-chain fields
  (`previous_hash`, `entry_hash`, `actor_user_id`) were not present in the
  introspected column list.
- No `audit_chain_state` table and no public audit triggers were found in the
  read-only audit.
- The live `settings` table uses an integer identity/sequence primary key and
  a unique `key`; the repository schema describes a different key-based
  primary key. The live `posts` table is not represented in
  `supabase/schema.sql`.
- Existing production rows are present in `leads`, `logs`, and
  `settings`. Preserve them; do not drop/recreate or replace tables to align
  them with the repository schema.
- Direct table grants on all eight live public tables are currently limited to
  `postgres` and `service_role`; no direct `anon` or `authenticated` table
  grants were returned. This is consistent with the absence of RLS policies,
  and means the advisor findings alone do not establish current Data API row
  exposure.
- **A separate default-privilege issue remains:** `pg_default_acl` contains
  entries for objects created by `supabase_admin` in `public`. Its default ACLs
  include `anon` and `authenticated` privileges on future tables
  (`arwdDxtm`), sequences (`rwU`), and function execution (`X`). The current
  `postgres` owner defaults are restricted to `postgres` and `service_role`.
  These defaults apply to objects created by the corresponding owner; they do
  not retroactively grant access to the existing tables. Before creating new
  public objects, determine which role actually owns migration-created
  objects, then review and correct the `supabase_admin` defaults with a
  version-controlled migration and postcondition checks. Function defaults
  deserve particular care because PUBLIC execution can expose newly created
  privileged functions.
- All eight tables currently have RLS enabled, `FORCE ROW LEVEL SECURITY`
  disabled, zero policies, and zero non-internal triggers in the read-only
  catalog query.

## Migration inventory

### Present in this repository

- `supabase/migrations/20261117_add_leads_website.sql`
- `supabase/migrations/20261117_add_logs_level.sql`
- `supabase/migrations/20261120090000_expand_logs_audit_fields.sql`
- `supabase/migrations/20261123093000_admin_audit_access_and_hash_chain.sql`

The two `20261117` migrations are present in GitHub `main`; their effects
(`leads.website` and `logs.level`) are also visible in production. However,
their versions do not appear in the remote migration ledger observed during
this audit. This is a migration-history mismatch, not evidence that the SQL
should be executed again.

The two audit migrations are present in the repository and have passed the
PostgreSQL 17 CI integration suite, but their schema effects are not yet
present in production. They must not be assumed to have been applied.

### Present in the remote migration ledger, source files not found in this repo

The remote ledger reports these five versions:

1. `20261119191911_create_jarvis_memory_and_fk_indexes`
2. `20261119192040_complete_jarvis_runtime_schema`
3. `20261119192145_enable_rls_on_legacy_posts`
4. `20261119192412_revoke_anon_authenticated_public_table_and_sequence_privileges`
5. `20261119192559_secure_postgres_default_privileges_public_schema`

Their original SQL source files were not found in the repository's `main`
branch during the inventory. Do not recreate files under these exact historical
names and present guessed SQL as the originals. Do not mark versions applied
or reverted merely to make the CLI output look clean.

## Additional security finding: owner-specific default privileges

The production catalog query returned these defaults for objects created by
`supabase_admin` in `public`:

- Tables: `anon` and `authenticated` receive all ordinary table privileges.
- Sequences: `anon` and `authenticated` receive sequence usage/select/update.
- Functions: `anon` and `authenticated` receive EXECUTE.

By contrast, the `postgres` defaults grant these object privileges only to
`postgres` and `service_role`. This is an owner-specific PostgreSQL behavior:
changing defaults for `postgres` does not change defaults for objects created
by `supabase_admin`. The existing direct grants were checked separately and do
not currently include `anon` or `authenticated` on the eight listed tables.

Do not issue a blanket `ALTER DEFAULT PRIVILEGES` solely because the historical
`supabase_admin` entry exists. The current eight tables and `settings_id_seq`
are owned by `postgres`, whose defaults are already restricted. Before any
future migration creates public objects under `supabase_admin`, either ensure
that path is not used or add a separately reviewed owner-specific default-ACL
correction. Any such migration must preserve required `service_role` access and
verify resulting ACLs by catalog query.

## Required recovery sequence

1. **Freeze schema-changing automation.** Keep `supabase db push` and
   production migration workflows disabled until reconciliation is complete.
2. **Capture a complete, reviewable schema snapshot.** Export definitions for
   every production object in scope: tables and column attributes, constraints,
   indexes, sequences and ownership, policies, grants and default privileges,
   functions and function ACLs, triggers, views, extensions, enums, and
   migration ledger. Exclude application row contents and secrets.
3. **Resolve the five historical source files.** Check available deployment
   artifacts, CI logs, backups, and developer copies. If they cannot be
   recovered, record that the original SQL is unavailable; do not fabricate it.
4. **Compare state, not filenames.** For each historical version, map the
   expected effect to the current production catalog and repository history.
   Treat the two `20261117` files separately because they are in Git but absent
   from the remote ledger.
5. **Build a forward-only reconciliation proposal.** Use a newly named,
   version-controlled migration only for verified missing changes. Make every
   DDL operation additive/idempotent where possible, preserve the legacy
   `settings` and `posts` structures, and include explicit preconditions and
   postconditions. Do not bundle speculative RLS policies: policy predicates
   must reflect the application's actual authorization model.
6. **Test against PostgreSQL 17 in CI.** Test both a clean bootstrap path and a
   production-shaped legacy schema fixture, including existing rows, grants,
   RLS behavior, and audit append/hash-chain behavior.
7. **Review and approve the exact SQL.** Open a PR with the snapshot summary,
   migration diff, rollback/forward-recovery notes, and test results.
8. **Only after separate explicit production approval**, take/verify a fresh
   encrypted backup, apply the approved migration in a controlled window, and
   run read-only post-deployment checks. Do not run migration repair unless
   there is a separately reviewed, evidence-backed decision for each version.

## Audit migration deployment gates

Before applying the existing audit migrations in production:

- Confirm that the `logs` column expansion is compatible with the deployed
  application version and fallback logging path.
- Review the admin read policy against the real trusted JWT
  `app_metadata.role` provisioning process. Do not use user-editable
  `user_metadata` for authorization.
- Confirm that the application uses server-side `service_role` writes and
  never exposes that key to a client.
- Verify that append-only triggers will not break any legitimate maintenance
  or retention workflow; document a controlled privileged maintenance path if
  one is required.
- Confirm function execution privileges, `pgcrypto`/digest availability, and
  the hash-chain verification function's behavior for legacy rows.
- Verify policy behavior using real role/JWT test cases, not only as
  `postgres` or `service_role`.

## Separate production backup work

The CI backup/restore round-trip proves the repository's local PostgreSQL
backup path, not a production S3 backup. Production backup remains blocked
until the AWS stack is deployed and the GitHub Actions secrets/variables are
configured and verified. The private age identity must remain in GitHub
Secrets and must never be copied into source control or chat.

## Current decision

The current evidence is sufficient to prepare a reconciliation PR, but not
sufficient to safely mutate production or to reconstruct the five missing
historical migrations as if their original source had been recovered.
