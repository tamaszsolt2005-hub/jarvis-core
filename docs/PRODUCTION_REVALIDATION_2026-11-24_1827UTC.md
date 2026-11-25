# Jarvis production revalidation — 2026-11-24 18:27 UTC

This is a read-only recheck of the existing Jarvis Supabase project after the
latest repository-side Auth/RBAC and test changes. No SQL was executed through
the database query tool, and no DDL, DML, Auth provisioning, migration repair,
or production configuration change was performed.

## Project and schema

- Project `kiutreccucbegskxowek`: `ACTIVE_HEALTHY`, PostgreSQL 17.11.
- The remote migration ledger still contains only the same five historical
  versions recorded in `production-migration-recovery.md`.
- The public schema still has the same eight application tables:
  `leads`, `tasks`, `email_drafts`, `logs`, `settings`,
  `jarvis_memory`, `jarvis_proactive_state`, and `posts`.
- All eight tables still have RLS enabled.
- Current row counts returned by the table inventory: 11 leads, 28 logs,
  1 settings row, 1 proactive-state row; tasks, email drafts, memory, and posts
  are empty.
- The production-specific legacy shapes remain: `logs` has only
  `id, module, message, created_at, level`; `settings` retains its integer
  sequence-backed primary key and unique `key`; `posts` remains the legacy
  five-column table.
- The security advisor still reports eight `rls_enabled_no_policy` findings.
  This is consistent with the previously observed lack of direct
  `anon`/`authenticated` table grants; it is not by itself proof of public
  row exposure. The missing policies remain a blocker for enabling the new
  authenticated application path.

## Decision

The production schema and migration history have not changed since the prior
inspection. The RBAC migration and structured audit/hash-chain migrations are
still repository-only and must not be applied until the migration-history
reconciliation and backup gates are satisfied.

The CI encrypted backup/restore test is an isolated local PostgreSQL test. It
is not a verified backup of this production project. No production DDL/DML,
migration repair, user provisioning, or Auth/RLS activation was attempted.

## Repository validation status at this snapshot

- The previous production-shaped fixture run 45458719047 passed: 692 passed,
  3 skipped, 92.87% total coverage; 31 pgTAP RBAC/audit assertions and one
  encrypted local backup/restore integration test passed.
- Additional audit-admin negative-path tests were added in commit
  `35c263047f0bd0c30257b3c2ab69a2ff3adf7945`. Its initial run was superseded
  before the Python/browser test phase completed.
- CI action references were then upgraded to Node 24-compatible releases:
  checkout v7, setup-python v7, upload-artifact v7, and
  configure-aws-credentials v6. The new run
  [45459683655](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45459683655)
  was queued at the time of this note. Do not treat the new audit-admin tests
  or action upgrade as validated until that run completes successfully.

PR #13 remains open and draft. This note does not authorize merging the PR or
activating production Auth/RLS.
