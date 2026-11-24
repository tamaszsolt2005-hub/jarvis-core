# PR #13 CI validation — 2026-11-24

## Latest verified run

Workflow run [45460581824](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45460581824) completed successfully on head `fe76e1b4581959900b831fef4d2f3991f0196c54`.

- **Python / Streamlit / browser job:** passed, including unit, AppTest and browser tests.
- **Total Python line coverage:** 93.57% (3,492 of 3,732 lines; 80% minimum).
- **`audit_admin.py`:** 96.19% line coverage.
- **`dashboard.py`:** 81.25% line coverage.
- **`jarvis_auth.py`:** 96.55% line coverage.
- **PostgreSQL 17 integration job:** passed.
- **Audit/RBAC pgTAP assertions:** passed (31 assertions in this CI configuration).
- **Encrypted age backup/restore integration:** passed (isolated local PostgreSQL round-trip).
- **CloudFormation validation, Playwright browser installation, compileall:** passed.
- The workflow uploaded the coverage report and responsive UI screenshots.

The updated CI fixture models the currently inventoried production table shapes and enables RLS on all eight application tables before applying the repository migrations. The fixture and tests are isolated CI resources; they do not connect to or modify the production Supabase project.

The test workflow now uses the Node.js 24-compatible action major versions `actions/checkout@v7`, `actions/setup-python@v7`, and `actions/upload-artifact@v7` (and `aws-actions/configure-aws-credentials@v6` in the backup workflow).

## Remaining gates

- PR #13 remains **open and draft**. A green CI run is not approval to merge or activate Auth/RBAC.
- Production still has no provisioned Auth user, no deployed RLS policies, and no structured audit/hash-chain schema.
- The five historical remote migration source files remain unrecovered; do not run `supabase db push` or migration repair to conceal the drift.
- The CI backup/restore test uses a temporary local PostgreSQL database and age identity. It is not a production backup and does not validate AWS/S3 configuration.
- Production DDL/DML remains gated on a fresh, encrypted, independently verified production backup and an exact reviewed migration sequence.
- Real Supabase Auth/JWT/RLS behavior still needs validation in an already-existing, explicitly authorized isolated environment.

## Coverage follow-up

The latest run raises total line coverage to 93.57%. `audit_admin.py` is now at 96.19%; `jarvis_auth.py` is at 96.55%. `dashboard.py` remains at 81.25%, making dashboard Auth/session/UI branches the next useful test-coverage target.


## Dashboard Auth helper follow-up (2026-11-24)

The next test increment adds `tests/test_dashboard_auth_helpers.py` on PR #13.
It isolates and exercises the dashboard Auth helper functions and covers:

- the `JARVIS_SUPABASE_AUTH_LOGIN_ENABLED` opt-in flag;
- forwarding the authenticated session into the user-scoped DB client;
- allowing only the configured admin/operator/reader roles;
- refreshed token and role propagation into Streamlit session state;
- fail-closed behavior when the session is missing or revoked;
- clearing the cached DB client, role, Auth session, and pending action after
  verification failure;
- selecting the legacy shared-password client only while Auth is disabled.

The first run, [45461593492](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45461593492),
reported **717 passed, 1 failed, 3 skipped**. The failure was in the test
double, not the application behavior: after the revoked session was correctly
cleared, the fake Streamlit object did not implement the login form UI methods.
The test double was completed in commit
`c1d50154451c35f10d9f16094dbef7680b7e9fed`.

The follow-up run
[45462249173](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45462249173)
has the PostgreSQL 17 integration job **completed successfully**, including
audit/RBAC migrations, pgTAP checks, and encrypted local age backup/restore.
CloudFormation validation, Playwright browser installation, and compileall
also completed successfully in the Python job. At the latest inspection the
unit/AppTest/browser test step was still running; therefore no final test
count or updated coverage is claimed here. This section must be superseded
with the final results once the run completes.

The successful local backup/restore job is isolated CI evidence only. It is
not a backup of production and does not verify AWS/S3 deployment or secrets.
