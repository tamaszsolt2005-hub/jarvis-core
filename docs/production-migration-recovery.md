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

### Read-only postcondition mapping (2026-11-24 refresh)

A second read-only inventory confirmed the following current state. These are
**observed postconditions**, not proof that the named historical SQL was the
code that created them:

| Remote version name | Observable current-state evidence | What remains unproven |
|---|---|---|
| `create_jarvis_memory_and_fk_indexes` | `jarvis_memory` exists with its content-length check and active/created index; lead foreign keys and supporting `tasks_lead_id_idx` / `email_drafts_lead_id_idx` exist. | Exact original DDL, object creation order, and whether every intended index is present. |
| `complete_jarvis_runtime_schema` | `tasks`, `email_drafts`, and `jarvis_proactive_state` exist with their current columns, constraints, and indexes. | Exact original schema definition and whether it included additional statements not visible from current objects. |
| `enable_rls_on_legacy_posts` | `public.posts` exists and RLS is enabled; it currently has no policies. | Exact original statement and whether any additional protections were included. |
| `revoke_anon_authenticated_public_table_and_sequence_privileges` | Current direct table grants on the eight inventoried public tables are limited to `postgres` and `service_role`. | Historical grant/revoke statements and the complete privilege state for every object outside this table inventory. |
| `secure_postgres_default_privileges_public_schema` | Current `postgres` owner defaults are restricted to `postgres` and `service_role`; current public tables and `settings_id_seq` are owned by `postgres`. | Exact historical SQL and whether it addressed other owners or object classes. |

The refreshed table inventory also confirms the production-specific shape that
must be preserved: `settings` has integer `id` primary key plus unique
`key`; `posts` is a separate legacy table; `logs` still has only
`id, module, message, created_at, level`; and the existing lead/log/settings
rows remain present. The inventory returned the existing FK, check, unique,
and supporting indexes for the runtime tables. No DDL or DML was run.

This mapping narrows the reconciliation work but does not justify fabricating
the five source migrations or changing the remote migration ledger. The
forward-only migration proposal must be based on verified missing *current
state*, not on assumptions about the historical migration names.

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
   RLS behavior, and audit append/hash-chain behavior. The CI audit fixture now
   seeds a pre-migration legacy log row and asserts that both additive
   migrations preserve it without assigning it a fabricated hash-chain entry.
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
- The separate Auth/RBAC foundation in [PR #13](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/13) is still open and is not production activation: its own scope says the dashboard login has not switched, business modules still use the service-role client, and no production RLS policies or migrations have been applied. Reconcile/review that branch against current `main`, complete the trusted admin-role provisioning path, and test real JWT/RLS behavior before enabling the audit admin policy.
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
## Fresh read-only revalidation (2026-11-24)

The production project was rechecked through the Supabase project tools after the
RBAC migration and CI work were added to the repository. This was a read-only
check; no SQL migration, DDL, DML, migration repair, Auth-user creation, or
project/branch creation was performed.

- The remote migration ledger still contains exactly the five versions listed
  above. None of the two 20261117 repository migrations or the two audit
  migrations appears in that remote list.
- The live public schema still contains exactly these eight tables:
  leads, tasks, email_drafts, logs, settings, jarvis_memory,
  jarvis_proactive_state, and posts. The proposed audit_chain_state table is
  not present.
- RLS is enabled on all eight tables. The current security advisor still
  reports eight rls_enabled_no_policy findings.
- The live logs columns remain only
  id, module, message, created_at, level; there are 28 rows.
- The live settings table still uses integer id backed by settings_id_seq,
  unique key, nullable value jsonb, and updated_at timestamp without time zone;
  it has one row.
- The legacy posts table remains present with
  id, content, scheduled_for, status, created_at and zero rows.
- Current row counts include 11 leads, zero tasks, zero email_drafts, zero
  jarvis_memory, and one jarvis_proactive_state row. Existing rows must be
  preserved.
- The five exact historical migration filenames were not returned by GitHub
  code search on the default branch, and the path-specific commit history on
  the default branch returned no commits for any of the five files. The first
  missing filename was also checked directly across all 17 active repository
  branches and was absent. This does not prove that no external deployment
  artifact or developer backup exists; those remain the recovery sources to
  investigate.

The current RBAC migration
20261124130000_shared_workspace_role_access.sql is still repository-only.
Its PostgreSQL 17/pgTAP integration suite passed in CI, but the production
advisor findings and absent audit schema confirm that it has not been applied
and must not be activated against the current production schema.

The latest PR #13 head at this revalidation was
df3fb7bd8dd9d055d40f0cafd7075e086b0edd63. Both workflow runs
45387974804 and 45387986390 completed successfully, including the
Python/AppTest/browser test job and the PostgreSQL 17 encrypted
backup/restore integration job. These CI results validate the repository
fixtures, not the production database.

### Reconciliation decision after revalidation

The five missing SQL files have not been recovered from the checked GitHub
history. Do not create replacement files under their historical version
numbers, and do not run supabase migration repair merely to silence the
history mismatch. The next safe recovery action is to obtain the original
migration artifacts from the environment that ran the deployment (developer
working copies, deployment logs/artifacts, or a retained repository archive).
If those artifacts cannot be recovered, prepare a separately reviewed,
forward-only baseline/reconciliation proposal from a complete schema snapshot;
it must not claim to be the original historical SQL. Production execution
remains gated on explicit approval of the exact reviewed migration plan.


## Latest catalog snapshot and CI revalidation (2026-11-24 18:12 UTC)

A further read-only catalog snapshot was captured directly from the existing
Jarvis production project. It included object definitions/metadata only; no
application row contents or secrets were selected.

Observed current state:

- Exactly eight public tables, all owned by `postgres`: `leads`,
  `tasks`, `email_drafts`, `logs`, `settings`, `jarvis_memory`,
  `jarvis_proactive_state`, and `posts`.
- RLS is enabled and not forced on all eight tables.
- There are zero public-schema RLS policies, zero non-internal public
  triggers, and zero public-schema functions in this snapshot.
- No direct `anon` or `authenticated` table grants were returned for
  existing public tables.
- The current column inventory confirms the production-specific shapes:
  - `logs`: `id, module, message, created_at, level`
  - `settings`: `id, key, value, updated_at`; integer sequence-backed
    `id` and unique `key`
  - `posts`: `id, content, scheduled_for, status, created_at`
  - `leads`: includes `website`, `notes`, and `source`
  - `tasks`, `email_drafts`, `jarvis_memory`, and
    `jarvis_proactive_state` retain the previously inventoried runtime
    columns and constraints.
- Owner-specific default ACLs remain important: defaults for objects created
  by `postgres` grant only to `postgres` and `service_role`, while catalog
  entries for `supabase_admin` include `anon` and `authenticated` privileges
  for tables, sequences, and function execution. This is not evidence of
  direct grants on the eight existing tables. Supabase documents
  `supabase_admin` as an internal reserved role whose default privileges
  cannot be changed by the project `postgres` role; do not propose an
  `ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin` migration. Instead,
  ensure application migrations create their objects as the intended
  project-controlled role (normally `postgres`), verify the resulting
  ownership/ACLs, and avoid treating platform-managed `supabase_admin`
  defaults as a project-fixable setting.

### Forward-only reconciliation proposal (design only; not executable SQL)

Because the original five historical SQL files were not recovered from the
available GitHub repository history/branches or the two connected Supabase
projects, the safe next artifact is a reviewed proposal—not a fabricated
historical migration and not a production change.

1. **Freeze historical reconstruction.** Preserve the five remote migration
   ledger entries as evidence. Do not reuse their version numbers, mark them
   repaired, or run `supabase db push` while source/history drift remains.
2. **Treat live schema as the baseline.** Preserve all eight tables and their
   production-specific columns, constraints, owners, sequences, and existing
   rows. In particular, do not replace the integer-keyed `settings` table
   or remove the legacy `posts` table to match repository snapshots.
3. **Separate independently reviewable changes.** Any future migration set
   must split (a) owner-specific default-ACL hardening, (b) trusted Auth/RLS
   policy deployment, and (c) structured audit/hash-chain expansion. Do not
   mix them into one broad baseline operation.
4. **Require explicit preconditions.** Before each migration, assert the
   expected relation/column/constraint/owner/ACL state and stop on mismatch.
   Avoid broad `IF NOT EXISTS` statements that could silently accept an
   incompatible object definition.
5. **Require postconditions and data preservation checks.** Verify exact
   grants/default ACLs, policy expressions, trigger/function ownership and
   execution ACLs, and audit-chain behavior. Preserve legacy log rows without
   retroactively assigning hash-chain values.
6. **Test two paths in PostgreSQL 17 CI.** Test a clean bootstrap and a
   production-shaped legacy fixture populated with representative existing
   rows, owner-specific defaults, and the exact production table shapes.
   Assert both successful migration and deliberate failure on unexpected
   preconditions.
7. **Keep production deployment separately gated.** A fresh encrypted backup,
   exact SQL review, maintenance window, explicit approval, and read-only
   post-deployment verification are prerequisites. No such approval or
   deployment is implied by this design note.

### CI / pull request status at this snapshot

PR #13 remains open and draft at head
`a510699e16784f07fd6eb88dc7dc84a255e2ccfd`. Workflow run
[45391367059](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45391367059)
has now completed successfully: both `test` and
`backup-restore-integration` jobs passed. The latter ran PostgreSQL 17
audit/pgTAP checks and an encrypted backup/restore round trip. These results
validate CI fixtures and repository code; they do not validate or modify the
production database.

This section supersedes the older “latest PR #13 head” and in-progress CI
status recorded in the earlier 2026-11-24 revalidation note above.


### Supabase-managed role limitation (documentation correction)

The catalog snapshot above exposes `supabase_admin` default-ACL entries, but
these must not be treated as a normal project-owned migration target.
Supabase's guidance states that project users cannot alter
`supabase_admin` default privileges because the role is reserved and the
project `postgres` role is not a member of it. Therefore the reconciliation
proposal is limited to ensuring project-created objects use the intended
project-controlled owner and that `postgres` default ACLs are correct; it
does not attempt to revoke or rewrite `supabase_admin` defaults.
See [Supabase's explanation of the reserved-role limitation](https://supabase.com/kb/troubleshooting/cant-change-the-default-privileges-of-supabase_admin-in-the-public-schema-448af9)
and [PostgreSQL 17 ALTER DEFAULT PRIVILEGES](https://www.postgresql.org/docs/17/sql-alterdefaultprivileges.html).


## Full production revalidation (2026-11-24 19:14 CET)

A further read-only inspection was performed against the existing production project
after the PR head advanced to `8a2cfeda2d88802c1a792737af3ff3b3029b6b7a`.

Confirmed:

- Project remains `ACTIVE_HEALTHY`, PostgreSQL 17.11.
- The eight production tables and their previously documented legacy shapes remain
  present. Current counts: 11 leads, 28 logs, 1 settings row, 1 proactive-state
  row; tasks, email drafts, memory and posts are empty. `auth.users` remains empty.
- All eight tables have RLS enabled, zero policies, zero public-schema triggers,
  and zero public-schema functions. No public views were found in the prior
  inventory. The current security advisor still reports eight
  `rls_enabled_no_policy` findings.
- Existing direct table/sequence privileges remain limited to `postgres` and
  `service_role`; no `anon` or `authenticated` direct table access was found.
  The `postgres` default ACLs for public tables, sequences and functions remain
  restricted to `postgres` and `service_role`. Platform-managed
  `supabase_admin` defaults are not a project migration target.
- `pgcrypto` is already installed in the `extensions` schema, so the audit
  hash functions' `extensions.digest` dependency is available.
- The remote migration ledger remains the same five historical versions.
  The two `20261117` schema effects are present despite their versions being
  absent from the ledger. Audit and RBAC migrations remain unapplied in production.

The current PR head is `8a2cfeda2d88802c1a792737af3ff3b3029b6b7a`.
Workflow run [45457110039](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45457110039)
has its PostgreSQL 17 encrypted backup/restore integration job completed
successfully. At the time of this snapshot, the Python/AppTest/browser test job
was still in progress. The run has no uploaded artifacts.

**Deployment gate:** no verified fresh production backup is currently available
through the connected tools. The repository's backup workflow requires GitHub
secrets and AWS configuration that have not been verified as configured. No
production DDL/DML, migration repair, Auth user provisioning, or role/policy
activation was performed during this inspection. Do not apply the audit or RBAC
migrations until a fresh encrypted backup is taken and verified and the exact
migration sequence is reviewed against the live schema and app compatibility.

The repository RBAC migration is ordered after the two additive audit migrations:
it expects `audit_chain_state` and the audit columns to exist. The production
deployment sequence must therefore be: verified backup; apply the structured
audit expansion; apply the hash-chain migration; apply the RBAC migration; then
verify policies, grants, triggers, function ownership/ACLs, legacy-row
preservation, and hash-chain behavior. Keep dashboard Auth enforcement disabled
until a real admin account with trusted `app_metadata.role` is provisioned and
end-to-end JWT tests pass. The current `auth.users` count of zero means no
production Auth login can yet succeed.


### CI completion follow-up (2026-11-24)

A follow-up check of workflow run
[45457110039](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45457110039)
confirmed that both jobs completed successfully:

- `test`: Python unit, Streamlit AppTest, browser tests, compileall and CloudFormation lint.
- `backup-restore-integration`: PostgreSQL 17 audit migrations, 17 audit pgTAP assertions,
  31 shared-workspace RBAC pgTAP assertions, and encrypted age backup/restore round trip.

This validates the repository code and isolated CI fixtures for commit
`8a2cfeda2d88802c1a792737af3ff3b3029b6b7a`. It does not constitute a production
backup or production Auth/RLS verification. The documentation-only follow-up
commit does not change the tested application or migration SQL.


## PR #13 validation follow-up (2026-11-24 18:20 UTC)

The documentation-only head `63a50c656ae0f27fe0210d80771f64551dc938ee`
was validated by workflow run
[45457848935](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45457848935).
Both jobs completed successfully.

- Python/AppTest/browser suite: **682 passed, 3 skipped**.
- Total measured Python coverage: **92.44%** (required minimum 80%).
- PostgreSQL 17 audit/RBAC integration and pgTAP checks: successful.
- Encrypted age backup/restore round-trip: **1 passed**.
- Compileall and CloudFormation lint: successful.
- Dashboard responsive screenshots and coverage XML were uploaded as CI artifacts.

The backup integration uses an isolated loopback PostgreSQL test database,
a temporary age identity, and the `local-test` source marker. It is not a
backup of the live Jarvis Supabase project and does not verify AWS/S3
credentials or production restore readiness.

The test report highlights remaining coverage gaps in `audit_admin.py`
(71%), `jarvis_auth.py` (78%), and `dashboard.py` (81%), even though the
repository-wide threshold is met. These should be targeted by follow-up
negative-path tests before enabling production Auth.

The CI logs also report GitHub Actions Node.js 20 deprecation warnings for
`actions/checkout@v4`, `actions/setup-python@v5`, and
`actions/upload-artifact@v4`; update to compatible maintained action
versions in a separate CI maintenance change after validating runner
compatibility.

This run validates the repository commit and isolated fixtures only. It does
not resolve the production migration-ledger mismatch, create production Auth
users, apply live RLS policies, or establish a verified production backup.


## CI status note (2026-11-24, PR #13)

The dashboard Auth helper follow-up CI run
[45462249173](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45462249173)
completed its PostgreSQL 17 integration job successfully, including the
repository audit/RBAC migrations, pgTAP checks, and encrypted local age
backup/restore round-trip. Its Python test job was cancelled during the
combined unit/AppTest/browser step after subsequent branch pushes. The
uploaded coverage artifact is provisional and must not be cited as a completed
CI pass.

A new run
[45462875186](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45462875186)
is running on the current PR documentation head. Its outcome is pending at
the time of this update.

These are repository/CI checks only. They do not alter the production
migration ledger, apply RLS policies, provision Auth users, or create a
verified production backup. All production deployment gates in this document
remain in force.

## Current recovery state — 2026-11-24 19:12 UTC

The five historical SQL sources previously missing from the repository have now
been recovered from the read-only remote ledger field
supabase_migrations.schema_migrations.statements. The restored files preserve
the original version identifiers and SQL statement bodies. The ledger rollback
field was NULL for all five, so there is no stored automatic rollback SQL;
plan forward-only recovery.

The PostgreSQL 17 CI integration now replays, in order:
1. the two repository-only 20261117 idempotent column migrations;
2. the five recovered historical migrations;
3. audit-field expansion;
4. audit hash-chain/admin access;
5. shared-workspace RBAC.

The latest full CI run [45467211381](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45467211381)
passed both jobs: 734 passed, 3 skipped, 93.67% coverage; PostgreSQL 17,
pgTAP, migration replay and encrypted local age backup/restore all passed.

This is isolated CI evidence, not a production restore. Production still has
the two 20261117 versions missing from its migration ledger, and the audit/RBAC
migrations are not applied. The repository bootstrap schema has also been
corrected to include posts and an integer identity settings ID with a unique
key, but that does not alter the live production database.

Do not run supabase db push, migration repair or production DDL/DML until a
fresh encrypted production backup has been independently verified and the
two 20261117 ledger discrepancies plus exact migration order have a reviewed
forward-only plan.


## Fresh production schema snapshot and migration reconciliation (2026-11-25 09:13 UTC)

The latest read-only snapshot is maintained separately in [PRODUCTION_SCHEMA_SNAPSHOT_2026-11-25.md](PRODUCTION_SCHEMA_SNAPSHOT_2026-11-25.md). It supersedes earlier row-count and column-inventory notes in this document.

Current confirmed facts:
- PostgreSQL 17.11; project \`ACTIVE_HEALTHY\`.
- Eight public tables, all owned by \`postgres\`; RLS enabled on all eight, FORCE RLS disabled.
- Zero public RLS policies, triggers, or functions.
- Zero Auth users.
- Eight Security Advisor \`rls_enabled_no_policy\` findings.
- Five remote migration versions: \`20261119191911\`, \`20261119192040\`, \`20261119192145\`, \`20261119192412\`, \`20261119192559\`.
- Two \`20261117\` repository migration effects are present in production, but their versions are absent from the remote ledger.
- Audit-field, hash-chain/admin-access, and shared-workspace RBAC migrations remain repository-only and unapplied.
- Production \`logs\` remains the five-column legacy table; \`audit_chain_state\` is absent.
- Production \`settings\` is integer-sequence-backed and \`posts\` is a live legacy table; both must be preserved.
- \`postgres\` default ACLs in \`public\` are restricted to \`postgres\` and \`service_role\`. Platform-managed \`supabase_admin\` defaults must not be changed by project migrations.

### Production migration order proposal

This order is for the disposable test branch first; it is not authorization to execute in production:

1. Preserve the snapshot and complete a fresh encrypted production backup.
2. On the disposable branch, verify/replay the two idempotent 20261117 column migrations and observe the branch ledger behavior.
3. Apply \`20261120090000_expand_logs_audit_fields.sql\`.
4. Apply \`20261123093000_admin_audit_access_and_hash_chain.sql\`.
5. Apply \`20261124130000_shared_workspace_role_access.sql\`.
6. Verify all schema postconditions, owner/ACL state, policies, triggers, audit append and hash chain, plus admin/operator/reader JWT allow/deny behavior.
7. Only after review, prepare an exact production ledger reconciliation. Do not run \`supabase migration repair\` or \`supabase db push\` without separate explicit approval of the exact command and expected postconditions.

### Recovery semantics

The five historical migrations in the remote ledger have no stored rollback SQL. Treat them as forward-only history. For the three new audit/RBAC migrations, rollback is not assumed to be safe: dropping columns/tables or policies may lose audit evidence or reopen access. Prefer forward-fix migrations. A failed migration in the disposable branch should be discarded/recreated; production recovery must use the verified backup plus a separately reviewed forward-recovery plan.

### Live Auth/RLS test harness

Added:
- \`scripts/supabase_auth_rls_smoke.py\` – creates temporary Auth users in a non-production project, obtains real signed JWTs, and tests PostgREST policies.
- \`.github/workflows/supabase-auth-rls-live.yml\` – manual workflow bound to the \`supabase-integration\` GitHub Environment.
- Required environment secrets: \`JARVIS_TEST_SUPABASE_URL\`, \`JARVIS_TEST_SUPABASE_PUBLISHABLE_KEY\`, \`JARVIS_TEST_SUPABASE_SERVICE_ROLE_KEY\`.
- Required environment variable: \`JARVIS_TEST_SUPABASE_PROJECT_REF\`, which must not equal production project ref \`kiutreccucbegskxowek\`.

The test checks admin/operator/reader roles, rejects user_metadata role spoofing, checks shared-workspace lead access and settings visibility, operator audit append/actor binding, admin-only audit/hash-state reads, role change after token refresh, logout refresh-token revocation, and invalid JWT rejection. The workflow must only be run against a disposable Supabase branch/project. It creates Auth users and append-only audit rows; delete the test branch after evidence is captured.

### Production backup workflow enhancement

The backup workflow now includes a second verification stage: download the uploaded encrypted S3 object, verify/decrypt it, restore it into a fresh PostgreSQL 17 container, and assert the exact eight-table public schema inventory while recording lead/log/settings row counts. The workflow still requires the production GitHub secrets/variables and AWS OIDC role to be configured. It is manually dispatched or scheduled from the trusted \`main\` branch; the OIDC trust policy is intentionally restricted to \`main\`.

**Scope limitation:** \`scripts/supabase_backup.py\` backs up the JARVIS \`public\` schema. It does not include Supabase-managed \`auth\`, \`storage\`, \`realtime\` schemas or Storage object binaries. This is adequate for the current application-data snapshot, but is not a full Supabase platform backup. The current production Auth user count is zero; Storage object backup remains a separate operational requirement if the project begins using Storage.

### Current execution status

- [x] Fresh read-only schema/catalog snapshot captured.
- [x] Exact current remote migration ledger captured.
- [x] Production Security Advisor findings captured.
- [x] Restore-to-separate-PostgreSQL-17 workflow step implemented.
- [x] Real JWT/Auth/PostgREST smoke-test harness and manual workflow implemented.
- [ ] Disposable Supabase branch created and migrations replayed (cost confirmation required).
- [ ] Live Auth/RLS smoke test executed with branch-only credentials.
- [ ] Production backup workflow executed successfully from trusted \`main\` and S3 object/restore evidence captured.
- [ ] Production migration ledger reconciliation approved and applied (separate approval required).
- [ ] Production audit/RBAC migrations approved and applied (separate approval required).

No production schema or Auth changes were performed.
