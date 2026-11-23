# Audit governance and production rollout

This document distinguishes implemented repository controls from controls that
still require production infrastructure, operator decisions, or an isolated
database verification.

## Implemented in this branch

- Structured and legacy events continue to share the existing `public.logs`
  table; no parallel audit table is introduced.
- `audit_admin.py` provides a separate Supabase Auth sign-in for the audit
  viewer. It uses only `SUPABASE_PUBLISHABLE_KEY` or `SUPABASE_ANON_KEY`,
  never the service-role key or the ambiguous legacy `SUPABASE_KEY`.
- The user is fetched again through Supabase Auth and must have the trusted
  `app_metadata.role = "admin"` claim. User-editable `user_metadata` is
  never used for authorization.
- The dashboard audit page revalidates/refreshes the Auth session on each
  render and reads records with that user's JWT, so the database RLS policy is
  the authorization boundary. The shared dashboard password alone cannot
  grant audit access.
- Audit read access uses stable cursor pagination (100 records per page),
  filters by module/status/operation ID, and can be exported as CSV. Export
  requires a persisted pending audit event and records a completion event
  with the verified admin user UUID.
- The migration grants authenticated users SELECT only, applies an
  admin-only `app_metadata.role` RLS policy, and revokes direct mutation
  privileges from `anon` and `authenticated`.
- Database triggers reject UPDATE, DELETE, and TRUNCATE on audit rows.
- New audit rows receive a SHA-256 hash linked to the previous hashed row.
  A private singleton chain-head row is locked during each insert, serializing
  writers even when multiple events share one transaction timestamp.
- A SECURITY INVOKER database function verifies row hashes, predecessor links,
  forks, disconnected entries, and the current chain head. Admins can run it
  manually from the audit page.
- Existing legacy rows are not rewritten. Their `previous_hash` and
  `entry_hash` remain null; the chain begins with the first insert after the
  migration is applied.

## Required configuration and bootstrap

1. Configure `SUPABASE_URL` and a publishable/anon key
   (`SUPABASE_PUBLISHABLE_KEY` or `SUPABASE_ANON_KEY`) in the server-side
   Streamlit secrets/environment.
2. Create/confirm the administrator account in Supabase Auth and require
   verified email according to the project's Auth settings.
3. Assign `app_metadata.role = "admin"` through a trusted Supabase
   administrator process. Do not let users self-assign this claim and do not
   put the role in `user_metadata`.
4. Apply the migrations in order:
   `20261120090000_expand_logs_audit_fields.sql`, then
   `20261123093000_admin_audit_access_and_hash_chain.sql`.
5. Run `supabase test db` against an isolated development database using
   `supabase/tests/audit_access_and_integrity.test.sql`, then run security
   advisors and verify anon, reader, admin, and service-role behavior.

The repository branch does not apply either migration to the live project.

A read-only comparison on 2026-11-23 found migration-history drift. The
live project reports these applied migration versions, but none of the matching
source files exists on either `main` or `feat/complete-central-audit`, and
Git history contains no matching path history:

| Version | Recorded migration name |
|---|---|
| `20261119191911` | `create_jarvis_memory_and_fk_indexes` |
| `20261119192040` | `complete_jarvis_runtime_schema` |
| `20261119192145` | `enable_rls_on_legacy_posts` |
| `20261119192412` | `revoke_anon_authenticated_public_table_and_sequence_privileges` |
| `20261119192559` | `secure_postgres_default_privileges_public_schema` |

Do not run `supabase db push` until the missing migration sources/history have
been reconciled with a reviewed remote schema snapshot and an approved
migration-repair workflow. The missing SQL must not be reconstructed by guess,
and `supabase/schema.sql` is a schema snapshot, not a substitute for the
missing migration history. It is not an exact copy of the inspected live schema:
for example, live `settings` has an integer `id` primary key and a unique `key`,
while the repository snapshot defines `key` as its primary key; live `posts` is
not defined in that snapshot; and the snapshot contains structured audit fields
that are not yet present in live `logs`. The live database also has lead-ID
indexes on `tasks` and `email_drafts` that are not represented in the snapshot.

The same read-only inspection found eight `public` tables. RLS is enabled on
all eight, no table has an RLS policy, and the current table ACLs grant direct
table privileges only to `postgres` and `service_role`; all eight tables
are owned by `postgres`. The `logs` table still has only its legacy columns,
so the structured audit and hash-chain migrations have not been applied to
production. The current business application therefore continues to depend on
server-side `service_role` access; this is not a per-user business RBAC model.

The default-privilege catalog also contains a broader `supabase_admin`
default ACL for `anon` and `authenticated`. The inspected application tables
are `postgres`-owned and do not inherit those grants, but future object
creation must use a controlled owner and be reviewed separately.

## Controls still not complete

| Control | Status / reason |
|---|---|
| Full business RBAC | Not implemented. Existing business modules still use the server-side service-role client behind the shared dashboard password. The new Auth gate protects only the audit viewer. |
| Operator/reader permissions | Not implemented across leads, tasks, drafts, settings, memory, and actions. |
| Tenant isolation | Not implemented. Existing business tables have no tenant ownership model or tenant_id. This remains a single-tenant application. |
| Actor identity on every event | Not implemented. Existing business actions still originate from the shared dashboard session; the audit schema does not yet reliably identify a human actor for every event. |
| Production migration | Pending approved deployment; repository SQL does not prove live schema state. |
| Retention duration and legal hold | Decision required. No automated deletion or purge job is enabled. |
| WORM/object-lock archive | Not implemented. Requires a separately provisioned storage provider, retention lock, and independent credentials. |
| Hash-chain external anchoring | Not implemented. The in-database chain is tamper-evident for ordinary application access, not immutable against a database owner or privileged operator. |
| Alert delivery | Not implemented as an end-to-end alert route. Audit failures are reported by application error handling, but no independently verified paging/notification destination is configured. |
| Scheduled integrity verification | Manual admin-triggered verification is implemented. A production schedule and independent alert route are not configured. |
| Export audit trail | Implemented for CSV export: pending and success events use the same operation ID and record the verified admin UUID. |
| Complete search and pagination UI | Cursor navigation and module/status/operation-ID filters are implemented; free-text and date-range search remain unavailable. |
| Production Auth/RLS test | Not run. Requires an isolated Supabase development branch/project and provisioned test users. |

## Security boundary

The service-role key bypasses RLS and must remain server-side. The
append-only triggers add a database guard against accidental/application-level
mutation, but a sufficiently privileged database owner can disable triggers,
change functions, or rewrite data. This is not WORM storage and must not be
represented as such.

No retention duration is selected by engineering guesswork. No destructive
purge, archive migration, or irreversible storage setting is enabled.
