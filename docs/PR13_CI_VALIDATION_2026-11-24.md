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
