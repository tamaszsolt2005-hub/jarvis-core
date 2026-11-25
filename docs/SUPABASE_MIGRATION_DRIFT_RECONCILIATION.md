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

The Jarvis project \`kiutreccucbegskxowek\` was re-inspected through read-only Supabase catalog tools. The full object/column/index/constraint snapshot is in [PRODUCTION_SCHEMA_SNAPSHOT_2026-11-25.md](PRODUCTION_SCHEMA_SNAPSHOT_2026-11-25.md).

Confirmed:
- PostgreSQL 17.11, project \`ACTIVE_HEALTHY\`, region \`eu-west-1\`.
- Exactly eight public tables, all owned by \`postgres\`; RLS enabled on all eight, FORCE RLS disabled.
- Zero public policies, triggers and functions; \`auth.users\` contains zero users.
- Security Advisor at 2026-11-25 09:17:56 UTC reports eight \`rls_enabled_no_policy\` findings.
- The live migration ledger contains exactly five versions: \`20261119191911\`, \`20261119192040\`, \`20261119192145\`, \`20261119192412\`, \`20261119192559\`.
- \`leads.website\` and \`logs.level\` are present; the two \`20261117\` repository migration filenames remain absent from the remote ledger.
- The three later repository-only migrations remain unapplied: audit-field expansion, audit hash-chain/admin access, and shared-workspace RBAC.
- \`settings\` remains integer-ID/sequence-backed with unique \`key\`; \`posts\` remains a live legacy table; \`logs\` still has only the five legacy fields.
- Existing direct public-table grants remain restricted to \`postgres\` and \`service_role\`. \`postgres\` public default ACLs are restricted. Catalog entries for platform-managed \`supabase_admin\` include API-role defaults, but that reserved owner context is not a project migration target.

### Reconciliation status and exact sequence

The snapshot resolves the *unknown schema inventory* but does not silently repair the remote ledger. The two 20261117 migration effects already exist; re-running them in production is not the right fix. Their ledger discrepancy needs a separately reviewed baseline/repair operation after the exact effects and version syntax have been verified on an isolated branch.

The proposed isolated sequence is:
1. Create a disposable Supabase branch from Jarvis production (branch receives no production data).
2. Confirm the two 20261117 column effects; replay the two idempotent migration statements only on the branch and verify the branch ledger.
3. Apply \`20261120090000_expand_logs_audit_fields.sql\`.
4. Apply \`20261123093000_admin_audit_access_and_hash_chain.sql\`.
5. Apply \`20261124130000_shared_workspace_role_access.sql\`.
6. Verify object owners, grants, policies, function ACLs, triggers, audit append actor binding, hash-chain integrity and admin/operator/reader allow/deny matrix.
7. Only after the branch tests pass, prepare a production migration-history reconciliation proposal and obtain explicit approval for the exact production operation.

No production migration, migration repair, DDL/DML, Auth user provisioning, or feature flag change was performed during this revalidation.
