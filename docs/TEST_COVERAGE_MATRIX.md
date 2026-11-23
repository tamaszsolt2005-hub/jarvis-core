# JARVIS test coverage matrix

## Verified baseline

The following numbers are from the successful GitHub Actions run for PR #9, head
`a3a2f8adc0c6807d5241015e855ee01229fb00c5` (2026-11-23):

- Application Python modules in the repository: 31
- Test Python files: 45
- Tests: 341 passed, 2 skipped, 0 failed
- Statement coverage: 83.18%
- Required minimum: 75%
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
| `dashboard.py` | 45% | Authentication/retrieval/security helpers tested; Streamlit presentation and chat UI remain the largest gap |
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
| `task_actions.py` | 79% | Strict payload validation, explicit approval, create/update/close and concurrency paths |
| `web_auditor.py` | 92% | SSRF checks, redirects, transport and parser errors |

Coverage is a statement-level signal, not proof that every business scenario,
authorization boundary, external integration, or production configuration is
correct. In particular, dashboard UI behavior still needs more isolated tests.

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
