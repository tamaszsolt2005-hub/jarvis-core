# Supabase production migration drift reconciliation

**Updated:** 2026-11-24 19:12 UTC  
**Project:** Jarvis / kiutreccucbegskxowek / eu-west-1 / PostgreSQL 17  
**Scope:** read-only production evidence plus repository/CI reconciliation. No production writes were performed.

## 1. Current production facts

The 2026-11-24 18:51 UTC read-only inspection and follow-up catalog queries found:

- 8 public tables; RLS enabled on all 8; FORCE RLS false.
- 0 public RLS policies; Supabase Security Advisor reports 8 rls_enabled_no_policy findings.
- auth.users contains 0 users.
- All 8 public tables are owned by postgres.
- Direct table grants are present for postgres and service_role only; anon/authenticated have no direct table grants.
- postgres default ACLs in public are restricted to postgres and service_role for tables, sequences and functions; no PUBLIC/anon/authenticated default grants were observed.
- No public-schema functions or triggers were present at inspection time; the only public sequence was settings_id_seq.
- public.audit_chain_state does not exist.
- The logs table has only legacy fields (id, module, message, created_at, level); none of the 12 checked structured audit/hash fields exists.
- settings has an integer primary key/sequence and a unique key; posts is a legacy table; leads.website and logs.level exist.

See PRODUCTION_REVALIDATION_2026-11-24_1851UTC.md for the table/column and catalog snapshot.

## 2. Remote migration ledger and recovered sources

The remote ledger contains five historical versions whose SQL files had been missing from Git. The exact SQL statement arrays were recovered with a read-only query against supabase_migrations.schema_migrations.statements and restored as versioned files:

1. 20261119191911_create_jarvis_memory_and_fk_indexes.sql
2. 20261119192040_complete_jarvis_runtime_schema.sql
3. 20261119192145_enable_rls_on_legacy_posts.sql
4. 20261119192412_revoke_anon_authenticated_public_table_and_sequence_privileges.sql
5. 20261119192559_secure_postgres_default_privileges_public_schema.sql

These were not reconstructed by guessing from the current schema. The remote ledger rollback field was NULL for all five, so the recovered migrations have no stored automatic rollback SQL. Use forward-only recovery planning.

## 3. Remaining ledger drift

- Repository files 20261117_add_leads_website.sql and 20261117_add_logs_level.sql are not recorded in the remote ledger, although their column effects are present in production.
- Audit migrations 20261120090000_expand_logs_audit_fields.sql and 20261123093000_admin_audit_access_and_hash_chain.sql are repository-only and remain unapplied in production.
- Shared-workspace RBAC migration 20261124130000_shared_workspace_role_access.sql is also repository-only and unapplied.
- The repo bootstrap schema was aligned to include the legacy posts table and an integer identity settings ID with unique key. This does not alter the live database.

## 4. CI evidence

Workflow [45467211381](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45467211381) is fully green on PR head 50ff914a67aa48906a96c1abe5983bb2b826dff3:

- 734 passed, 3 skipped, 93.67% Python line coverage.
- PostgreSQL 17 integration job passed.
- CI replayed the two repository-only 20261117 migrations, all five recovered historical migrations, then audit expansion, hash-chain/admin access and shared-workspace RBAC in order.
- pgTAP security assertions passed.
- Encrypted age backup/restore round-trip passed in an isolated CI PostgreSQL database.

This is test-fixture evidence only. It is not a production backup, S3 upload, production restore or production migration.

## 5. Safe next steps

1. Deploy and verify the AWS backup stack; configure the required GitHub Actions secrets and variables without placing private keys in chat or Git.
2. Produce a fresh encrypted production dump; verify the uploaded S3 object by download/decrypt/hash/manifest; restore to a separate isolated PostgreSQL database.
3. Reconcile the two 20261117 repository-only versions with the remote ledger. Validate Supabase CLI treatment of these version names in a non-production environment; do not guess or silently repair the ledger.
4. Compare the exact production schema snapshot with the audit/hash-chain/RBAC migrations and finalize a forward-only sequence plus postcondition queries.
5. Run the full migration sequence in an isolated PostgreSQL 17 production-shape fixture (already covered in CI); separately validate real Supabase Auth/JWT/RLS in an already-existing, explicitly authorized isolated Supabase environment.
6. Only after the above, prepare a specific production change plan and perform production DDL with a fresh verified backup and explicit approval of the exact SQL/migration set.
7. Provision a trusted admin Auth user and role, perform read-only post-deploy validation, and only then enable the dashboard Auth/RBAC flags.

## 6. Prohibited until gates close

- No supabase db push.
- No supabase migration repair or manual migration-ledger edits.
- No production DDL/DML, policy changes or Auth-user provisioning.
- No new Supabase test project or branch.
- No production Auth/RBAC feature flag activation.

The five-source recovery gap is closed in the repository. The remaining blockers are the two 20261117 ledger discrepancies, production backup, unapplied audit/RBAC migrations and real Auth/RLS validation.


## Fresh production catalog revalidation (2026-11-25 09:13 UTC)

The Jarvis project `kiutreccucbegskxowek` was re-inspected through read-only Supabase catalog tools. The full object/column/index/constraint snapshot is in [PRODUCTION_SCHEMA_SNAPSHOT_2026-11-25.md](PRODUCTION_SCHEMA_SNAPSHOT_2026-11-25.md).

Confirmed:
- PostgreSQL 17.11, project `ACTIVE_HEALTHY`, region `eu-west-1`.
- Exactly eight public tables, all owned by `postgres`; RLS enabled on all eight, FORCE RLS disabled.
- Zero public policies, triggers and functions; `auth.users` contains zero users.
- Security Advisor at 2026-11-25 09:17:56 UTC reports eight `rls_enabled_no_policy` findings.
- The live migration ledger contains exactly five versions: `20261119191911`, `20261119192040`, `20261119192145`, `20261119192412`, `20261119192559`.
- `leads.website` and `logs.level` are present; the two `20261117` repository migration filenames remain absent from the remote ledger.
- The three later repository-only migrations remain unapplied: audit-field expansion, audit hash-chain/admin access, and shared-workspace RBAC.
- `settings` remains integer-ID/sequence-backed with unique `key`; `posts` remains a live legacy table; `logs` still has only the five legacy fields.
- Existing direct public-table grants remain restricted to `postgres` and `service_role`. `postgres` public default ACLs are restricted. Catalog entries for platform-managed `supabase_admin` include API-role defaults, but that reserved owner context is not a project migration target.

### Reconciliation status and exact sequence

The snapshot resolves the *unknown schema inventory* but does not silently repair the remote ledger. The two 20261117 migration effects already exist; re-running them in production is not the right fix. Their ledger discrepancy needs a separately reviewed baseline/repair operation after the exact effects and version syntax have been verified on an isolated branch.

The proposed isolated sequence is:
1. Create a disposable Supabase branch from Jarvis production (branch receives no production data).
2. Confirm the two 20261117 column effects; replay the two idempotent migration statements only on the branch and verify the branch ledger.
3. Apply `20261120090000_expand_logs_audit_fields.sql`.
4. Apply `20261123093000_admin_audit_access_and_hash_chain.sql`.
5. Apply `20261124130000_shared_workspace_role_access.sql`.
6. Verify object owners, grants, policies, function ACLs, triggers, audit append actor binding, hash-chain integrity and admin/operator/reader allow/deny matrix.
7. Only after the branch tests pass, prepare a production migration-history reconciliation proposal and obtain explicit approval for the exact production operation.

No production migration, migration repair, DDL/DML, Auth user provisioning, or feature flag change was performed during this revalidation.

## Execution constraint update (2026-11-25): existing Jarvis project only

The operator explicitly prohibited creating a new Supabase test account or a new Supabase
development branch. This instruction supersedes the earlier branch-based proposal above.

The only connected Supabase project discovered for this account is the existing Jarvis
project `kiutreccucbegskxowek` (PostgreSQL 17.11, `ACTIVE_HEALTHY`). Its development
branch list is empty. No second Supabase project or pre-existing branch was found.

Accordingly, migration validation must use the existing repository CI's isolated local
PostgreSQL 17 service and production-shape fixture. Do not call Supabase branch creation,
project creation, branch reset/rebase/merge, `supabase db push`, `supabase migration repair`,
or any production DDL/DML as part of this work.

### Current read-only recheck

A fresh read-only Supabase inspection on 2026-11-25 reconfirmed:

- Remote ledger: exactly five versions:
  `20261119191911`, `20261119192040`, `20261119192145`,
  `20261119192412`, `20261119192559`.
- No development branches exist.
- The eight public tables still exist with RLS enabled.
- `leads.website` and `logs.level` are present.
- `logs` still has only its five legacy columns; the structured audit/hash-chain
  columns and `audit_chain_state` are absent.
- The live schema still has the legacy integer-ID `settings` table and `posts`.
- Current row counts returned by the table inventory include 11 leads, 29 logs,
  one settings row, one proactive-state row, and zero posts/tasks/email drafts/memory.
  Counts are observational and can change as the application runs.

No production migration, ledger edit, DDL/DML, policy change, Auth provisioning, or
feature-flag change was performed.

### Required local-only validation sequence

The existing `.github/workflows/ci.yml` PostgreSQL 17 integration job already creates
an isolated production-shape fixture and replays, in order:

1. `20261117_add_leads_website.sql`
2. `20261117_add_logs_level.sql`
3. the five recovered historical migrations in timestamp order
4. `20261120090000_expand_logs_audit_fields.sql`
5. `20261123093000_admin_audit_access_and_hash_chain.sql`
6. `20261124130000_shared_workspace_role_access.sql`

It then runs the audit and shared-workspace pgTAP suites. This proves schema replay
against the fixture; it does **not** reconcile the live Supabase migration ledger.

Before declaring migration drift resolved, extend the local-only validation to cover:

- a production-like ledger fixture seeded with the five observed remote versions;
- a separate representation of the two 20261117 repository-only versions whose
  schema effects already exist;
- exact Supabase CLI migration-version/repair semantics documented without invoking
  repair against the live project;
- idempotent replay of the two additive 20261117 statements against a fixture where
  their columns already exist;
- preservation assertions for pre-existing leads/logs/settings/posts rows and legacy
  settings primary-key/sequence shape;
- failure injection between each audit/RBAC migration and a rerun/forward-recovery
  assertion proving the next safe action;
- postconditions for policies, grants, function ACLs, triggers, owners and indexes.

The 20261117 ledger discrepancy must remain classified as **unresolved** until the
exact CLI-compatible reconciliation action is proven using local fixture evidence.
Do not infer that the two migration versions can safely be marked applied solely
because their columns exist.

### Decision boundary

This repository work may prepare and test the exact reconciliation proposal. It may
not execute that proposal against the existing Jarvis Supabase project. Any future
production ledger repair or schema migration requires a separate approval naming
the exact operation and SQL. Production Auth remains OFF.

## Local migration-drift regression coverage added (2026-11-25)

Commits:
- `c9cc6c00eac8b96996420b708cf068dfddd56351`: added
  `supabase/tests/migration_drift_recovery.test.sql`.
- `d995fe5e577e7bdc455aec67083c6fd894f982c4`: added a dedicated PostgreSQL 17
  CI step, "Validate 20261117 migration drift and legacy data preservation".

The new CI fixture creates a separate local database and seeds the five observed
remote ledger versions. It separately represents the already-present effects of
`20261117_add_leads_website.sql` and `20261117_add_logs_level.sql`, then replays
both migrations twice. Assertions check:
- the five seeded ledger rows are unchanged (the test does not invent a repair);
- existing lead website and log level values survive;
- the legacy settings row and posts row survive;
- `settings.id` remains integer and sequence-backed;
- the two additive columns remain present after repeated replay.

This specifically proves additive/idempotent schema replay against an already-upgraded
local fixture. It does **not** prove that the two versions may be inserted into the live
Supabase migration ledger, nor does it emulate the full Supabase CLI repair command.

### CI status for the new regression step

The push workflow for commit `d995fe5e577e7bdc455aec67083c6fd894f982c4` was queued
at the time this document was updated:
https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45586358598

The corresponding PR workflow was pending:
https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45586327045

Do not mark the new regression test as passed until these runs complete successfully.

### Remaining unresolved work

- Obtain and document authoritative Supabase CLI semantics for reconciling the two
  historical versions; no live `migration repair` or ledger edit is authorized.
- Add failure-injection/forward-recovery coverage for the audit and RBAC migrations.
- Add catalog assertions for grants, function ACLs, owners, policies and trigger state.
- Keep production read-only, do not create Supabase projects/branches, and keep Auth OFF.


## Forward-recovery failure-injection coverage (2026-11-25)

Commit `cb77420b9686935a0554cc8ded3eb8bf7f1c7b83` extends the isolated PostgreSQL 17
integration workflow with two deliberate interruption points in the audit/RBAC chain:

1. Apply `20261120090000_expand_logs_audit_fields.sql`, force a separate psql
   statement to fail (`SELECT 1/0`), then replay the expansion migration before
   continuing.
2. Apply `20261123093000_admin_audit_access_and_hash_chain.sql`, force the same
   interruption before RBAC, then replay the hash-chain migration before continuing.
3. Apply `20261124130000_shared_workspace_role_access.sql` and replay it once more.
4. Run the existing audit and shared-workspace pgTAP assertions after recovery.

The injected failures are expected and caught by the workflow; an unexpected
successful failpoint causes the job to fail. The test verifies recovery when the
process stops **between committed migration files**, plus idempotent reapplication
of each migration. It does not simulate interruption halfway through an individual
migration file, nor does it establish Supabase CLI migration-repair semantics.

The workflow uses only its disposable PostgreSQL 17 CI service. No Supabase project,
branch, production database, Auth user, migration ledger, or production feature flag
is changed. Production Auth remains OFF.

CI runs for this commit are pending at the time of this documentation update:
- Push: https://github.com/tamaszsolt2005-hub/jarvis-core/actions
- PR: https://github.com/tamaszsolt2005-hub/jarvis-core/pull/13


## Partial-file recovery and legacy sequence assertions (2026-11-25)

Commit `1ca6e679507339f13885a86d8c56e1acc9f88170` extends the isolated PostgreSQL 17 drift fixture:

- Before replaying the full audit-expansion migration, CI now commits a prefix of its DDL separately: the first three audit columns and the `logs_created_at_desc_idx` index. It then replays the complete migration twice. This exercises recovery from a partially applied migration file, not merely interruption between migration files.
- The postconditions verify all nine audit-expansion columns and the pre-created index exist after recovery.
- The legacy `settings.id` check now calls `nextval(pg_get_serial_sequence(...))` and asserts the generated value advances beyond the existing maximum ID. This verifies the sequence remains operational, not just attached.

All of this runs in the disposable local PostgreSQL 17 CI database. It does not change or repair the live Supabase migration ledger and does not authorize production DDL. The exact Supabase CLI migration-repair semantics remain unverified unless a local CLI executable is explicitly exercised; no production repair is performed.


## JWT role spoofing and fail-closed RBAC assertions (2026-11-25)

The shared-workspace pgTAP suite now includes an explicit trust-boundary check: a token with `user_metadata.role = admin` but `app_metadata.role = reader` remains a reader, and an unknown `app_metadata.role` remains denied even when user metadata claims admin. The assertion plan is now 32 and the CI output guard was updated accordingly. These checks run only in the isolated PostgreSQL 17 fixture.


## CLI repair and catalog postcondition regression coverage (2026-11-25)

The PR branch now adds two CI-only checks; they run against the existing GitHub Actions
PostgreSQL 17 service and never connect to the Jarvis Supabase project:

- `supabase/tests/catalog_postconditions.test.sql` verifies the post-migration catalog:
  nine expected table owners and RLS flags, the 15-policy set, absence of
  `user_metadata` authorization, anon/authenticated table grants, settings sequence
  privileges, audit function owners and SECURITY DEFINER/INVOKER boundaries, function
  EXECUTE ACLs, three enabled audit triggers, four valid audit indexes, and owner-specific
  default ACLs.
- CI installs Supabase CLI `3.4.0` and runs the real `supabase migration repair`
  command only against the disposable `migration_drift_test` PostgreSQL database.
  The test verifies `--status applied` inserts the version row and `--status reverted`
  removes it, then re-applies it and checks that the command did not alter the existing
  schema effects or legacy rows. It uses CLI v3's explicit `--remote=<database-url>`
  target and never links to or addresses production.

Important versioning detail: both legacy files
`20261117_add_leads_website.sql` and `20261117_add_logs_level.sql` share the same
8-digit migration version, `20261117`. The CLI migration history is keyed by version and
`migration list` compares timestamps, so a single ledger row cannot independently
identify which of those two SQL files was applied. CI therefore also captures the pinned
CLI's `migration list` behavior when both same-version files are present. The exact
output must be reviewed before any reconciliation recommendation is made. This is a
repository/history ambiguity, not permission to mark either version applied in production.

Supabase CLI v3 is local-target by default; a hosted target requires explicit `--remote`
and a hosted repair confirmation. In this CI test the explicit remote URL points only to
localhost, with `--yes` used for non-interactive execution. The repair operation changes
migration history only; it does not execute or reverse SQL. See the official
[CLI migration repair reference](https://supabase.com/docs/reference/cli/config) and
[CLI v3 breaking-change notice](https://supabase.com/changelog?tags=cli).

**Status at commit time:** CI implementation added; do not mark the new catalog or CLI
checks passed until the workflow run for the resulting PR head completes successfully.
No production ledger, schema, Auth user, policy, or feature flag was changed.
