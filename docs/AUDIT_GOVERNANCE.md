# Audit governance and production rollout

This document defines the controls that must exist before the audit trail is
used as a compliance-grade record. It deliberately does not choose a retention
period, enable a destructive cleanup job, or claim that the current shared
password is an administrator identity.

## Current application boundary

- Structured and legacy events share the existing `public.logs` table.
- Application writes use the server-side Supabase client. The service-role key
  bypasses RLS and must never be exposed to a browser or an untrusted client.
- RLS is enabled on `logs`. With no applicable policy, ordinary
  `anon`/`authenticated` Data API roles are denied by default. This does not
  constrain service-role access.
- The dashboard currently uses a shared password. It does not provide a
  trustworthy per-person identity, role membership, tenant boundary, or
  administrator principal. Do not render audit records in the shared dashboard
  until an independently authenticated and authorized admin path exists.
- Repository schema files describe intended schema, not the live Supabase
  project's applied migration state.

## Required controls before production audit administration

| Control | Required implementation / verification | Current status |
|---|---|---|
| Individual identity | Supabase Auth user identity validated server-side for each privileged action | Not implemented |
| Role authorization | Server-side role/permission mapping stored in trusted app metadata or a protected role table; never authorize from user-editable metadata | Not implemented |
| Audit read access | Admin-only server endpoint/query; deny by default; test with anon, ordinary user, and admin roles | Not implemented |
| Tenant isolation | Define tenant ownership and enforce it in every read/write policy if multiple organizations are supported | Not implemented / product model undefined |
| Service-role protection | Keep key server-side; restrict deployment secret access; never send it to client code | Application uses server-side key; deployment controls not independently verified |
| Retention | Approve retention duration, legal holds, archive format, and deletion authority before implementing cleanup | Decision required |
| Immutable archive | Select storage with retention lock/WORM controls and independently controlled credentials | Infrastructure decision required |
| Tamper evidence | Define signed batches or hash chaining, key custody, rotation, and verification procedure | Not implemented |
| Export | Admin-authorized export, bounded date range, redaction, and export audit event | Not implemented |
| Alerting | Alert on repeated audit-write failures, unusual blocked operations, and integrity verification failures | Not implemented |
| Operational checks | Scheduled read/write health probe with alert routing and documented ownership | Not implemented |

## Safe rollout sequence

1. Establish the identity and role model, including whether this is single-user
   or multi-tenant. Do not infer an admin from the shared dashboard password.
2. Implement and test authorization in an isolated Supabase project. Include
   anon, authenticated non-admin, admin, and service-role test cases.
3. Confirm the deployed `logs` columns and indexes against the additive
   repository schema. Apply a migration only through an approved deployment
   process and after a backup/rollback review.
4. Agree retention, legal-hold, archive, and deletion requirements. Do not
   create a scheduled deletion process before this decision.
5. Provision a separately controlled immutable archive and verify that the
   application runtime cannot shorten retention or delete locked objects.
6. Add integrity verification, alert delivery, and documented incident
   procedures; test them with simulated failures.
7. Only then expose an audit administration UI or export endpoint.

## Non-goals and safety constraints

- No production Supabase schema or record is changed by this document.
- No retention duration is selected by engineering guesswork.
- No destructive purge, archive migration, or irreversible storage setting is
  enabled.
- No audit UI is exposed through the current shared-password dashboard.
- WORM storage is an infrastructure property; a database trigger alone is not
  represented as WORM or as protection against a privileged database owner.
