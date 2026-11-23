# JARVIS test coverage matrix

## Verified baseline

The final coverage run for PR #9 used head
`c3dfddfd1ae7b049c61c6aa3b2636541c9b092ba` (2026-11-23; Actions run `45132352299`):

- Application Python modules in the repository: 31
- Test Python files: 59
- Tests: 594 passed, 2 skipped, 0 failed
- Statement coverage: 97.70%
- Required minimum: 80%
- `python -m compileall -q .`: successful
- CI command: `python -m pytest -q --cov --cov-report=term-missing:skip-covered --cov-report=xml`

Four fully covered files are omitted by the CI `skip-covered` report. The table
below lists the remaining files reported by coverage.

## Per-module coverage

| Module | Coverage | Notes |
|---|---:|---|
| `business_learning.py` | 99% | Evidence-based learning and memory inputs |
| `daily_briefing.py` | 98% | Read-only report, consent-gated overdue follow-ups |
| `dashboard.py` | 97% | Streamlit AppTest covers login/chat/email, analytics navigation and period selection, empty/populated analytics, DB outage, task create/close/update approval, task rejection, diagnostics, market/research approval and executive report. Chromium/Firefox/WebKit E2E covers responsive chat and analytics at five viewports |
| `email_inbox.py` | 99% | Mocked IMAP reply, opt-out, and UID checkpoint processing |
| `email_sender.py` | 98% | Consent recheck, atomic state claims, pending audit, SMTP failure and follow-up limit paths |
| `follow_up.py` | 97% | Consent recheck, opt-out race, uncertain delivery, audit failure and recovery paths |
| `global_lead_research.py` | 97% | Grounding validation, malformed model output, deduplication, evidence quality and no-contact-permission invariants |
| `global_lead_research_job.py` | 94% | Scheduled-job orchestration and error reporting |
| `health_check.py` | 96% | Configuration, table/column probes, Gemini and safety-lock failures |
| `inbox_monitor.py` | 98% | Inbox monitoring and error paths |
| `intelligent_lead_scoring.py` | 97% | Lead scoring |
| `jarvis_analytics.py` | 97% | Empty/populated analytics rendering and database failure |
| `jarvis_common.py` | 96% | Shared configuration, DB, audit sanitization, truncation and persistence failures |
| `jarvis_errors.py` | 96% | Centralized error reporting and sanitization |
| `jarvis_memory.py` | 98% | Explicit save/list/forget, bounded retrieval and sensitive-data rejection |
| `jarvis_status.py` | 95% | Status helpers |
| `lead_gen.py` | 98% | Reviewed CSV validation, duplicate detection and error handling |
| `lead_scoring.py` | 96% | Lead score calculations |
| `proactive_monitor.py` | 94% | Read-only monitoring |
| `safe_http.py` | 99% | DNS-pinned HTTP transport, private/mixed DNS rejection, proxy and TLS hostname restrictions |
| `scripts/supabase_backup.py` | 98% | Mocked backup/restore, archive checks and external-tool failures |
| `stats.py` | 96% | Operational counts and sanitized log reporting |
| `task_actions.py` | 99% | Strict payload validation, explicit approval, create/update/close, concurrency paths, and failed completion-audit reporting |
| `web_auditor.py` | 96% | SSRF checks, redirects, transport and parser errors |

Coverage is a statement-level signal, not proof that every business scenario,
authorization boundary, external integration, or production configuration is
correct. AppTest and browser tests use fake/read-only database data and mocked
AI/SMTP dependencies; they do not contact a production Supabase project or send
real email.

## Dashboard UI test commands

Install the browser-test dependencies and all three Playwright browser engines:

```bash
python -m pip install -r requirements-test.txt
python -m playwright install chromium firefox webkit
```

Run the focused UI tests:

```bash
python -m pytest -q tests/test_dashboard_app.py tests/test_dashboard_browser.py
```

Each Chromium, Firefox and WebKit run launches a local Streamlit process with a test-only read-only
database shim and mocked AI output. Browser requests are restricted to the local
server; Plotly.js is served from the locally installed Python package. It checks
chat and analytics rendering, the analytics period selector, hidden chat input
on the analytics page, no horizontal overflow, and readable KPI widths at
1440×960, 1024×768, 768×1024, 390×844, and 320×720. CI uploads the screenshots
as the `jarvis-dashboard-responsive-screenshots` workflow artifact, grouped by browser engine.

## Safety boundaries

- Unit tests block DNS and outbound socket connection methods by default.
- Only `tests/test_live_integrations.py` with `live_integration` marker and
  `JARVIS_LIVE_INTEGRATION_TESTS=1` can opt into live read-only integration checks.
- SMTP and IMAP behavior in unit tests is mocked. No real email is sent.
- Supabase writes in unit tests use fake clients. No production business records
  or schema are changed by the test suite.
- The network fixture is a Python-process test guard, not an OS sandbox; it does
  not guarantee that subprocesses or every possible native networking mechanism
  are blocked.

## Remaining security and authorization work

- Dashboard login still uses a shared password; it does not establish per-user
  identity or roles.
- `approved=True` is an internal application guard, not a cryptographic
  authorization token or RBAC implementation.
- The schema enables RLS on application tables but does not define the final
  role-specific `CREATE POLICY` rules.
- A service-role Supabase key can bypass RLS. Production RLS verification
  requires a separate isolated Supabase test project and an agreed role/access
  matrix.
- Do not treat these remaining items as completed until the access model is
  approved and tested.


## Coverage-gap remediation added on 2026-11-23

The expanded test suite adds explicit negative and recovery-path checks for:

- tests/test_dashboard_helpers.py: safe public redirects, missing redirect targets, redirect limits, DNS failures, malformed ports, and filtering malformed database rows.
- tests/test_dashboard_app.py: email audit fail-closed behavior, SMTP exception auditing, final-audit warnings, explicit recipient validation, task close/update approval, missing task IDs, and approved market/research actions.
- tests/test_email_sender_coverage_edges.py: consent recheck immediately before SMTP, lost atomic claims, pending-audit failure, SMTP failure recovery, and follow-up limits.
- tests/test_follow_up.py: opt-out after claim, ambiguous post-SMTP completion, failed success-audit, recovery failure, disabled feature gate, and batch-level exception propagation.
- tests/test_safe_http_coverage_edges.py: public/private IP validation, DNS failure and mixed answers, invalid URL rejection, pinned IP transport, proxy rejection, TLS hostname preservation, and session cleanup.
- tests/test_global_lead_research_edges.py: malformed model output, grounding validation, deduplication, evidence downgrades, and the invariant that research never grants contact permission.
- tests/test_jarvis_common_edge_coverage.py: audit result redaction/truncation, persistence failures, audit filtering, settings helpers, Supabase/Gemini client selection, and model fallback errors.
- tests/test_email_workflow.py and tests/test_inbox_analyzer.py: chat-email malformed/empty draft handling and inbound classifier provider failure/empty response.
- tests/test_business_learning.py: malformed research evidence, score clamping, and conservative decision matching.
- tests/test_lead_scoring.py and tests/test_proactive_monitor.py: malformed URLs, date parsing, and snapshot error propagation.
- tests/test_reply_analyzer.py and tests/test_inbox_monitor.py: model-classification fallbacks, encoded headers, empty bodies, duplicate markers, and worker error propagation.

A defect found during this review was fixed in jarvis_errors.sanitize_log_text: CR/LF and other ASCII control characters are now replaced before log or audit persistence, preventing log-record injection. The regression is exercised through the shared logging helper tests.

## Final coverage pass (2026-11-23)

The final test additions focused on the remaining meaningful failure, recovery, and authorization-adjacent paths:

- `tests/test_final_coverage_edges.py`: dashboard safe-row handling, backup failures, analytics empty/invalid data, research-market fallback, and web/inbox error handling.
- `tests/test_final_coverage_edges_shared.py`: response-token budgets, configuration fallbacks, model failures, audit depth limits, malformed consent timestamps, and invalid email leads.
- `tests/test_final_coverage_edges_diagnostics.py`: business-learning matching, health-check safety lock, memory matching, lead scoring, status/statistics, task parsing, and HTTP response cleanup.
- `tests/test_final_dashboard_context.py`: website-profile success/failure paths, lead ranking without exposing private contact fields, and truthful handling of failed data sources.
- `tests/test_final_backup_success_edges.py`: successful backup command output, IPv6 host formatting, permission-hardening fallback, and CLI success paths.
- `tests/test_final_last_remaining.py`: SMTP-accepted/audit-failed recovery, critical state-recovery failure, disabled sender gate, research grounding rejection, redirect failures, and restore DB/identity/tool validation.
- `tests/test_dashboard_app.py`: explicit memory save/list/forget, failed executive analytics report, and outer chat failure handling.
- `tests/test_inbox_monitor.py`: IMAP search/fetch failures, sender mismatch, and logout error reporting.
- `tests/test_email_sender_coverage_edges.py`: consent recheck, atomic claim, audit failure, SMTP failure, and follow-up schedule handling.

No production-code change was required in this final pass: the new tests did not reveal a new application defect. The earlier CR/LF log-injection fix in `jarvis_errors.sanitize_log_text` remains covered by its regression test.

**Final validation:** GitHub Actions run [45132352299](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45132352299) passed on PR head `c3dfddfd1ae7b049c61c6aa3b2636541c9b092ba`: **594 passed, 2 skipped, 0 failed; 97.70% statement coverage; compileall successful**. Chromium, Firefox and WebKit browser tests passed. CI uploaded responsive screenshots and `coverage.xml` as separate artifacts.

The remaining 72 uncovered statements are documented by the CI `term-missing` report. They include defensive/rare exception branches and script-entry guards; this result is not 100% coverage and is not a claim that every production integration or authorization scenario has been exercised. Live integrations were not enabled, no real SMTP delivery occurred, and no production Supabase records or schema were modified.


## Central operational audit completion

The `tests/test_central_audit_completion.py` regression tests verify that:
- a reviewed CSV import does not write lead rows when its pending audit cannot be persisted;
- the global research automation does not start when its pending audit cannot be persisted;
- inbound email processing does not update lead state when its pending audit cannot be persisted.

The implementation reuses the existing `logs` table and `audit_event()` helper.
`tests/test_audit_pagination.py` covers bounded pages, stable composite cursors,
same-timestamp ordering, invalid cursors, and page-size caps. It does not apply a
live database migration or enable live SMTP/IMAP integration.
See [CENTRAL_AUDIT.md](CENTRAL_AUDIT.md) for the lifecycle matrix, retry behavior,
privacy boundaries, and rollout requirements.


## Audit-admin security and integrity tests

- `tests/test_audit_admin_auth.py`: trusted Supabase Auth admin claim, verified
  email requirement, non-admin rejection/sign-out, no fallback to ambiguous or
  service-role API keys, and refreshed-session validation.
- `tests/test_audit_actor_identity.py`: UUID actor attribution, invalid actor
  rejection, bounded cursor page size, and filter/cursor forwarding.
- `tests/test_audit_sql_contract.py`: admin-only `app_metadata` RLS contract,
  no authenticated mutation grants, append-only triggers, locked hash-chain
  head, and SECURITY INVOKER integrity verifier.
- `tests/test_dashboard_app.py`: shared dashboard password alone cannot open
  the audit data path or reuse the service-role read client.
- `supabase/tests/audit_access_and_integrity.test.sql`: pgTAP assertions for
  reader/admin visibility, denied writes, append-only triggers, hash chaining,
  and integrity verification. Must run against an isolated Supabase database
  with the two audit migrations applied; this SQL test is not executed by the
  Python-only GitHub CI workflow.
