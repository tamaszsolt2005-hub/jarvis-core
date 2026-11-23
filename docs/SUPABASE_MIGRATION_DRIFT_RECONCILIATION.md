# Supabase migration drift reconciliation plan

**Status:** investigation / planning only  
**Baseline reviewed:** 2026-11-23  
**Production writes performed:** none  
**New Supabase projects or Supabase branches created:** none

## Goal

Reconcile the repository's incomplete migration source history with the existing
Supabase production schema without guessing at missing SQL, rewriting live data,
or applying an unreviewed migration.

This document is a guarded recovery plan. It is not authorization to change the
production database.

## Verified repository and production facts

The current `main` branch contains these migration files:

- `20261117_add_leads_website.sql`
- `20261117_add_logs_level.sql`
- `20261120090000_expand_logs_audit_fields.sql`
- `20261123093000_admin_audit_access_and_hash_chain.sql`

The production migration history previously inspected read-only records five
additional applied versions whose source files are absent from the repository:

| Version | Recorded name |
|---|---|
| `20261119191911` | `create_jarvis_memory_and_fk_indexes` |
| `20261119192040` | `complete_jarvis_runtime_schema` |
| `20261119192145` | `enable_rls_on_legacy_posts` |
| `20261119192412` | `revoke_anon_authenticated_public_table_and_sequence_privileges` |
| `20261119192559` | `secure_postgres_default_privileges_public_schema` |

Exact-name searches of repository files and commit history did not locate
original SQL for these five versions. The migration names are metadata only;
they are not sufficient evidence to reconstruct their statements or intent.

A read-only production inventory on 2026-11-23 found:

- Eight tables in `public`: `leads`, `tasks`, `email_drafts`, `logs`,
  `settings`, `jarvis_memory`, `jarvis_proactive_state`, and `posts`.
- RLS enabled on all eight tables; no RLS policies were present.
- Direct table privileges were held only by `postgres` and `service_role`.
- All eight tables were owned by `postgres`.
- `logs` still had only legacy columns; structured audit columns were absent.
- Live `settings` used integer `id` as primary key and a unique `key`, unlike
  the repository schema snapshot, which defines `key` as the primary key.
- Live `posts` was not represented in `supabase/schema.sql`.
- Live `tasks` and `email_drafts` had lead-ID indexes not represented in the
  schema snapshot.
- The default-privilege catalog contained a `supabase_admin` default ACL
  involving `anon` and `authenticated`; the inspected application tables
  were `postgres`-owned and did not inherit that ACL.

The repository's `supabase/schema.sql` is therefore not an exact production
snapshot and must not be treated as migration history or as a safe replacement
for the missing migration files.

## Non-negotiable safety rules

1. Do not run `supabase db push` while migration-source and schema drift remain
   unresolved.
2. Do not recreate the five missing historical files from their names or from
   assumptions about intended behavior.
3. Do not delete, reorder, or rewrite rows in `supabase_migrations.schema_migrations`.
4. Do not use `migration repair` merely to make local and remote version lists
   look equal. A history edit does not prove schema equivalence.
5. Do not apply the audit migrations to production until their prerequisite
   migration state and schema have been reconciled.
6. Do not run SQL Editor changes, production DDL, data updates, grants, revokes,
   or policy changes as part of this investigation.
7. Do not create a new Supabase cloud project or Supabase development branch.
8. Do not expose connection strings, access tokens, passwords, service-role
   keys, or raw secrets in logs or documentation.
9. Do not claim production backup/restore readiness until a backup and restore
   have both been verified.

## Proposed recovery sequence

### Phase 1 — Preserve evidence

- Keep the five recorded migration versions as historical facts.
- Retain the current repository schema snapshot and all existing migration files.
- Record the inspected schema facts and the date of inspection.
- Before any future production work, require a separately verified backup and
  a tested restore path. The AWS backup stack is currently not deployed, so it
  cannot be treated as an available production backup.

**Exit condition:** evidence and backup prerequisites are documented; no
production changes have occurred.

### Phase 2 — Obtain an authoritative schema-only snapshot

Only after explicit operator approval, use a read-only schema extraction path
against the existing project. Review the current Supabase CLI documentation
and the exact installed command help before selecting a command.

For the currently documented Supabase CLI v3 workflow:

```bash
supabase --version
supabase db dump --help
supabase migration list --help
supabase db dump --remote -f /tmp/jarvis-production-schema.sql
```

The CLI v3 `db dump` defaults to the local stack unless `--remote` is
provided. Its default dump is schema-only (it excludes application row data
and custom role definitions); it does not ask for hosted-mutation confirmation.
It requires Docker/a running Docker daemon and a linked project. Verify the
printed `Target:` line before accepting the artifact. Do not put connection
strings or passwords in shell history, CI logs, or committed files.

Do not use `db pull` as a substitute for this first evidence capture: it
creates a migration file and can interact with migration history. Do not use
`db push`, `migration repair`, or any hosted write command during this phase.

- Capture schema definitions, constraints, indexes, triggers, functions,
  policies, grants, and ownership as represented by the dump.
- Separately inventory role definitions and default privileges, because the
  default dump excludes custom role definitions and managed Supabase schemas.
- Exclude application row data and secrets.
- Save the output locally or in a protected review artifact; do not apply it.
- Compare it with `supabase/schema.sql` and the four existing repository
  migrations.
- Confirm whether the five historical migration effects are present, absent,
  or only partially represented. Do not infer exact original SQL from names.

The CLI v3 migration guide documents that database commands default to the
local stack and require `--remote` for hosted targets. Re-check the guide and
`--help` output at execution time because CLI behavior can change.

**Exit condition:** a reviewed, schema-only production baseline with a
per-object difference report.

### Phase 3 — Build a reconciliation matrix

For every object, record:

- production definition and owner;
- repository definition, if any;
- relevant recorded migration version(s);
- exact observed difference;
- whether the difference is intentional, legacy, or unexplained;
- proposed forward-only correction, if any;
- data-loss, locking, privilege, and application-compatibility risks;
- verification query and rollback/forward-recovery strategy.

Pay particular attention to `settings`, `posts`, `logs`, the lead foreign-key
indexes, table grants, default privileges, and RLS policies.

**Exit condition:** every discrepancy has an evidence-backed disposition;
unexplained differences remain blocked rather than guessed.

### Phase 4 — Author forward-only migrations

If a real correction is required, create a new migration using the documented
Supabase CLI workflow (after checking `supabase migration new --help`). Do not
reuse the missing historical timestamps or pretend that a newly authored file
is the original migration.

- Preserve existing production rows and legacy table semantics.
- Use explicit preconditions and fail safely if the live schema is unexpected.
- Separate privilege/RLS changes from structural changes where practical.
- Ensure every exposed table has intentional, tested RLS policies and grants.
- Review function security mode, search paths, and EXECUTE privileges.
- Include verification queries and a documented forward-recovery plan.
- Do not include destructive drops, broad grants, or data rewrites without a
  separately reviewed requirement.

**Exit condition:** migration source, diff, tests, and operational plan have
independent review. This plan alone does not authorize production execution.

### Phase 5 — Validate before any production rollout

The audit migration tests require an isolated database and test identities.
No new Supabase cloud project or branch is authorized. Therefore, do not claim
the pgTAP suite or production RLS behavior is validated until an approved,
non-production validation target is available. Static checks alone are not
equivalent to database execution.

After an approved validation target exists:

- run the SQL/pgTAP tests;
- verify anon, authenticated reader, admin, and service-role behavior;
- verify append-only triggers and hash-chain integrity;
- run Supabase security advisors;
- verify the application against the reconciled schema.

**Exit condition:** reproducible passing database tests and a reviewed rollout
checklist.

### Phase 6 — Production rollout (separate approval required)

Production rollout is a separate change window and requires explicit approval.
Before it starts, verify the backup and restore path, confirm the exact target
project, review the final migration diff, and record a recovery operator.
Apply only the reviewed forward migration(s), then run the documented
post-migration verification queries. Never use `db push` as a shortcut around
unresolved history.

## Current blockers

- Original SQL for five recorded migration versions is not present in the
  repository or its searchable commit history.
- The repository schema snapshot is not an exact production schema snapshot.
- No approved isolated Supabase test project or branch is available.
- Production backup/restore readiness has not been demonstrated.
- The audit schema and RLS migrations have not been applied to production.

## Current decision

**No database operation is authorized by this document.** The next safe
technical action, after explicit approval, is to capture and review a
schema-only snapshot of the existing production database. Until then, keep
production unchanged and do not run `supabase db push`.
