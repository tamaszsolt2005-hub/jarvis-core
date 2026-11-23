# JARVIS test coverage matrix

## Verified baseline

The following numbers are from the successful GitHub Actions run for PR #9, head
`6d0b56d31279c909bfa57ef2819914646565291e` (2026-11-23; Actions run `45095248644`):

- Application Python modules in the repository: 31
- Test Python files: 48
- Tests: 429 passed, 2 skipped, 0 failed
- Statement coverage: 91.77%
- Required minimum: 80%
- `python -m compileall -q .`: successful
- CI command: `python -m pytest -q --cov --cov-report=term-missing:skip-covered --cov-report=xml`

Four fully covered files are omitted by the CI `skip-covered` report. The table
below lists the remaining files reported by coverage.

## Per-module coverage

| Module | Coverage | Notes |
|---|---:|---|
| `business_learning.py` | 96% | Evidence-based learning and memory inputs |
| `chat_email.py` | 88% | Explicit-recipient chat email parsing |
| `daily_briefing.py` | 98% | Read-only report, consent-gated overdue follow-ups |
| `dashboard.py` | 87% | Streamlit AppTest covers login/chat/email, analytics navigation and period selection, empty/populated analytics, DB outage, task approval/rejection, diagnostics and executive report. Chromium E2E covers responsive chat and analytics at five viewports |
| `email_inbox.py` | 91% | Mocked IMAP reply, opt-out, and UID checkpoint processing |
| `email_sender.py` | 88% | Consent, state claims, pending audit, SMTP and failure paths |
| `follow_up.py` | 87% | Consent recheck and uncertain-delivery no-retry state |
| `global_lead_research.py` | 87% | Research parsing, validation, and persistence |
| `global_lead_research_job.py` | 94% | Scheduled-job orchestration and error reporting |
| `health_check.py` | 96% | Configuration, table/column probes, Gemini and safety-lock failures |
| `inbox_analyzer.py` | 80% | Inbound classification |
| `inbox_monitor.py` | 88% | Inbox monitoring and error paths |
| `intelligent_lead_scoring.py` | 97% | Lead scoring |
| `jarvis_analytics.py` | 96% | Empty/populated analytics rendering and database failure |
| `jarvis_common.py` | 87% | Shared configuration, DB and audit helpers |
| `jarvis_errors.py` | 96% | Centralized error reporting and sanitization |
| `jarvis_memory.py` | 97% | Explicit save/list/forget, bounded retrieval and sensitive-data rejection |
| `jarvis_status.py` | 95% | Status helpers |
| `lead_gen.py` | 98% | Reviewed CSV validation, duplicate detection and error handling |
| `lead_scoring.py` | 88% | Lead score calculations |
| `proactive_monitor.py` | 94% | Read-only monitoring |
| `reply_analyzer.py` | 93% | Reply classification |
| `safe_http.py` | 88% | DNS-pinned HTTP transport and redirect restrictions |
| `scripts/supabase_backup.py` | 92% | Mocked backup/restore, archive checks and external-tool failures |
| `stats.py` | 93% | Operational counts and sanitized log reporting |
| `task_actions.py` | 99% | Strict payload validation, explicit approval, create/update/close, concurrency paths, and failed completion-audit reporting |
| `web_auditor.py` | 92% | SSRF checks, redirects, transport and parser errors |

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

The next test expansion adds explicit negative and recovery-path checks for:

- tests/test_dashboard_helpers.py: safe public redirects, missing redirect targets, redirect limits, DNS failures, malformed ports, and filtering malformed database rows.
- tests/test_dashboard_app.py: email audit fail-closed behavior, SMTP exception auditing, final-audit warnings, explicit recipient validation, task close/update approval, missing task IDs, and approved market/research actions.
- tests/test_email_sender_coverage_edges.py: consent recheck immediately before SMTP, lost atomic claims, pending-audit failure, SMTP failure recovery, and follow-up limits.
- tests/test_follow_up.py: opt-out after claim, ambiguous post-SMTP completion, failed success-audit, recovery failure, disabled feature gate, and batch-level exception propagation.
- tests/test_safe_http_coverage_edges.py: public/private IP validation, DNS failure and mixed answers, invalid URL rejection, pinned IP transport, proxy rejection, TLS hostname preservation, and session cleanup.
- tests/test_global_lead_research_edges.py: malformed model output, grounding validation, deduplication, evidence downgrades, and the invariant that research never grants contact permission.
- tests/test_jarvis_common_edge_coverage.py: audit result redaction/truncation, persistence failures, audit filtering, and settings helpers.

A defect found during this review was fixed in jarvis_errors.sanitize_log_text: CR/LF and other ASCII control characters are now replaced before log or audit persistence, preventing log-record injection. The regression is exercised through the shared logging helper tests.

**Validation status:** the expanded CI run is in progress. The final statement coverage and test count will be recorded only after the run for the latest PR head completes.
