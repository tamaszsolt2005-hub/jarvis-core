# PR #13 CI validation — 2026-11-24

## Latest verified run

Workflow run [45458719047](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45458719047) completed successfully on head `a7b15e7a5f4132356f1500d51ef7f54a13e5f869`.

- **Python / Streamlit / browser job:** passed.
- **Test suite:** 692 passed, 3 skipped.
- **Total Python coverage:** 92.87% (80% minimum).
- **PostgreSQL 17 integration job:** passed.
- **Audit/RBAC pgTAP assertions:** 31 passed.
- **Encrypted age backup/restore integration:** 1 passed.
- **CloudFormation validation, Playwright browser installation, compileall:** passed.

The updated CI fixture models the currently inventoried production table shapes and enables RLS on all eight application tables before applying the repository migrations. The fixture and tests are isolated CI resources; they do not connect to or modify the production Supabase project.

## Remaining gates

- PR #13 remains **open and draft**. This validation is not approval to merge or activate Auth/RBAC.
- Production still has no provisioned Auth user, no deployed RLS policies, and no structured audit/hash-chain schema.
- The five historical remote migration source files remain unrecovered; do not run `supabase db push` or migration repair to conceal the drift.
- The CI backup/restore test uses a temporary local PostgreSQL database and age identity. It is not a production backup and does not validate AWS/S3 configuration.
- Production DDL/DML remains gated on a fresh, encrypted, independently verified production backup and an exact reviewed migration sequence.

## Coverage follow-up

The latest run reports 92.87% total coverage. Individual areas still worth strengthening before production Auth activation include `audit_admin.py` (71%) and `dashboard.py` (81%). `jarvis_auth.py` improved to 97%.

The workflow logs also show Node.js 20 deprecation warnings for `actions/checkout@v4`, `actions/setup-python@v5`, and `actions/upload-artifact@v4`. Treat action-version maintenance as a separate compatibility-checked CI change.
