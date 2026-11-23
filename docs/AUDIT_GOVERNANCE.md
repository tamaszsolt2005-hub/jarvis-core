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
- Audit read access is bounded to 500 records, newest first, and can be
  exported as CSV.
- The migration grants authenticated users SELECT only, applies an
  admin-only `app_metadata.role` RLS policy, and revokes direct mutation
  privileges from `anon` and `authenticated`.
- Database triggers reject UPDATE, DELETE, and TRUNCATE on audit rows.
- New audit rows receive a SHA-256 hash linked to the previous hashed row.
  A private singleton chain-head row is locked during each insert, serializing
  writers even when multiple events share one transaction timestamp.
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
The live project's last read-only inspection showed the legacy `logs`
columns only and did not show the structured-audit migration in migration
history. Production therefore does not yet have the schema required by this
viewer or hash chain.

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
| Scheduled integrity verification | Not implemented as a production schedule. The SQL regression test verifies the chain in a disposable test transaction. |
| Export audit trail | CSV export is available to admins, but exporting itself is not yet written as a separate audit event. |
| Complete search and pagination UI | Not implemented. The viewer shows up to 500 newest records; the backend cursor API exists but the UI does not yet navigate cursors. |
| Production Auth/RLS test | Not run. Requires an isolated Supabase development branch/project and provisioned test users. |

## Security boundary

The service-role key bypasses RLS and must remain server-side. The
append-only triggers add a database guard against accidental/application-level
mutation, but a sufficiently privileged database owner can disable triggers,
change functions, or rewrite data. This is not WORM storage and must not be
represented as such.

No retention duration is selected by engineering guesswork. No destructive
purge, archive migration, or irreversible storage setting is enabled.
