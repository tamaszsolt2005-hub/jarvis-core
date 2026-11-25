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


### Final status of run 45462249173

A later status check found that the run did **not** complete fully:

- `backup-restore-integration`: **success**.
- `test`: **cancelled** during the combined unit/AppTest/browser test step.
- The workflow uploaded a coverage artifact before cancellation. Its XML reports
  3,500 / 3,732 lines, **93.78%** overall; `dashboard.py` 82.27%,
  `audit_admin.py` 96.19%, and `jarvis_auth.py` 96.55%.
- Because the test step's final result is cancelled, these coverage numbers are
  **provisional artifact data, not a successful CI validation**. No final
  passed/skipped/failed test count is claimed for this run.

The run was superseded while later commits were pushed to the PR branch. A new
complete CI run on the current PR head is required before the dashboard Auth
test additions or the current branch head can be called fully validated.


### Documentation head rerun

After the release-gate and production-recovery documentation updates, PR #13
head advanced to `02d3d9ab3834525cdf94d4c5f0801381528a0694`. New push and
pull-request workflow runs [45462966257](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45462966257)
and [45462977149](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45462977149)
were queued for this head at the time of this update. Their results are pending.
The earlier 45462875186 / 45462891101 runs were still in progress on the
previous documentation head and are not substitutes for a completed check on
the latest commit.


## Latest complete CI run — 2026-11-24

Workflow run [45463032568](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45463032568)
completed successfully on head `4945816b9010d899c1737a90ff3785ec1898acdd`.

- Python / Streamlit / AppTest / browser test job: **success**.
- Test result: **718 passed, 3 skipped**.
- Total Python line coverage: **93.78%** (3,500 / 3,732 lines).
- `dashboard.py`: **82.27%**.
- `jarvis_auth.py`: **96.55%**.
- `audit_admin.py`: **96.19%**.
- PostgreSQL 17 audit/RBAC integration job: **success**.
- Audit and shared-workspace RBAC pgTAP migrations/tests: **success**.
- Encrypted age backup/restore round-trip in isolated CI PostgreSQL: **success**.
- CloudFormation validation, Playwright browser installation, compileall: **success**.
- Coverage XML and 27 responsive dashboard screenshots uploaded as artifacts.

Artifacts:
- [Coverage report](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45463032568/artifacts/14953501639)
- [Responsive UI screenshots](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45463032568/artifacts/14954031342)

This is a complete green repository CI run. It does not prove a production AWS/S3 backup, production restore, or real Supabase Auth/JWT/RLS behavior.

## Latest complete CI run — 2026-11-24 19:12 UTC

Workflow run [45467211381](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45467211381) completed successfully on head 50ff914a67aa48906a96c1abe5983bb2b826dff3.

- Python / Streamlit / AppTest / browser job: **success**.
- **734 passed, 3 skipped**.
- Total Python line coverage: **93.67%** (3,553 / 3,793 statements; 80% minimum).
- dashboard.py: **82%**; audit_admin.py: **96%**; jarvis_auth.py: **97%**.
- PostgreSQL 17 migration/RBAC integration job: **success**.
- CI applied the two repository-only 20261117 migrations, all five SQL sources recovered from the remote migration ledger, then audit expansion, hash-chain and shared-workspace RBAC migrations in order.
- pgTAP security tests passed; encrypted age backup/restore round-trip passed in an isolated PostgreSQL database.
- CloudFormation validation, Playwright installation, compileall and all tests passed.
- Coverage and 27 responsive dashboard screenshots uploaded.

Artifacts:
- [Coverage XML](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45467211381/artifacts/14955532724) — 14-day retention.
- [Responsive UI screenshots](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45467211381/artifacts/14955985728) — 7-day retention.

This validates repository code and the migration chain against an isolated CI fixture. It is not a production backup, AWS/S3 deployment, production restore or real Supabase Auth/JWT/RLS validation.


## Legfrissebb branch-ellenőrzés – 2026-11-25

A PR #13 jelenlegi branch headje: `649f5796ec8f475d0a069d2e263669efbb290d1b`.
A legutóbbi teljesen zöld baseline továbbra is a [45467211381](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45467211381)
futás (734 passed, 3 skipped, 93.67% coverage); ez korábbi commiton futott,
így nem igazolja a jelenlegi headet.

A korábbi audit UI tesztfutás 751 passed, 11 failed, 3 skipped és 94.17%
coverage eredményt adott. Mind a 11 hiba a`tests/test_dashboard_audit_ui.py`
tesztjeiben jelentkezett. A dashboard audit-függőségeinek modulon keresztüli
hivatkozására és az importok korrekciójára javítások kerültek a branchre.
Ezek hatása csak a jelenlegi head teljes tesztfutása után tekinthető
igazoltnak; a korábbi 94.17% nem az új futás coverage-adata.

A jelenlegi head push CI futása [45509638790](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45509638790),
a PR CI futása [45509647393](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45509647393).
A push futásban a `backup-restore-integration` job sikeres; a `test` jobban
a függőségtelepítés, CloudFormation-validáció, Playwright telepítés és
`compileall` sikeres, a kombinált unit/AppTest/browser tesztlépés azonban az
dokumentum frissítésekor még futott. Végleges tesztszám és coverage ezért
még nincs közölve. A PR-futás eredményét is külön ellenőrizni kell.

**Értelmezés:** a lokális PostgreSQL 17 + pgTAP + age backup/restore sikeres
CI-eredménye továbbra sem production backup, és nem igazolja a valós
Supabase Auth/JWT/RLS működést. PR #13 nyitott és draft; merge és production
módosítás nem történt.


## Targeted repair after CI run 45510214369 — 2026-11-25

The run on PR head `3997f938cd3d3be497e62b9bed9bd4042372d85b` completed with **742 passed, 20 failed, 3 skipped** and **94.04%** line coverage. All 20 failures were grouped into three causes:

1. **Audit UI (11 tests):** the AppTest setup seeded an audit session and immediately reran the page before replacing the verified-session client. That setup rerun attempted real environment-backed Supabase validation and cleared the test session. The tests also selected the last generic button, which was a sidebar navigation control rather than the audit login form submit. The fixture now installs an isolated verified-client stub before its setup rerun, and login tests select the submit button by its label. Production authentication behavior is unchanged.
2. **Chat email audit-flow (3 tests):** source-contract tests and existing patch seams expect dashboard-level `audit_event` and `report_error` names. The dashboard now exposes small compatibility delegates that resolve the shared modules at call time, preserving monkeypatchability and the centralized implementation. All dashboard call sites use those delegates; pending-audit fail-closed ordering and the explicit approval / server-switch gates remain intact.
3. **Dashboard helpers (6 tests):** helper tests patch `dashboard.report_error`, but the module-level seam had been removed during the module-namespace refactor. The compatibility delegate restores that supported seam for safe database reads and website-profile transport/parser reporting, including when the reporter itself raises.

The changes are test-isolation and dependency-seam repairs; they do not weaken audit authorization, export expiry, logout cleanup, email approval, or fail-closed behavior. A new CI run on the resulting commit is required before these fixes can be called verified. No production Supabase data or configuration was changed.


## Aktuális head – teljes CI-igazolás (2026-11-25)

A branch head `e6736101405180c220d6b96b5a7a3c1d890813e0` a [45571463053 futásban](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45571463053) teljesen zöld eredményt adott.

- Python / Streamlit / AppTest / browser job: **success**.
- Tesztek: **762 passed, 3 skipped**.
- Python line coverage: **96.47%** (3,799 statement, 134 missed; 80% minimum).
- `compileall`, CloudFormation-validáció és Playwright Chromium/Firefox/WebKit telepítés: **success**.
- PostgreSQL 17 integráció: **success**.
- Audit/RBAC migrációk és pgTAP security tesztek: **success**.
- Age titkosítású backup/restore round-trip külön, izolált CI PostgreSQL adatbázisban: **success**.
- Coverage artifact: [15002127458](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45571463053/artifacts/15002127458).

A futás a `e6736101405180c220d6b96b5a7a3c1d890813e0` commitot tesztelte, így igazolja a korábbi 20 teszthiba célzott javítását. Egy másik, azonos headre indított [45571470452 futás](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45571470452) a dokumentáció frissítésekor még futott; a zöld 45571463053 ettől függetlenül teljes és sikeres.

**Fontos korlátok:** ez repository CI és izolált PostgreSQL integráció. Nem production backup, nem AWS/S3 deploy/restore, nem valós Supabase Auth/JWT/RLS teszt, és nem bizonyít SMTP/IMAP/Gemini éles kézbesítést. Production Auth flag OFF marad; production adatbázis nem módosult; PR #13 nyitott és draft.


## Második teljes CI-futás ugyanazon a kód-headen

A [45571470452 futás](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45571470452) ugyanazon a `e6736101405180c220d6b96b5a7a3c1d890813e0` commiton szintén teljesen sikeres:

- Python / Streamlit / AppTest / browser job: **success**.
- Tesztek: **762 passed, 3 skipped**.
- Line coverage: **96.47%** (3,799 statement, 134 missed).
- PostgreSQL 17 audit/RBAC + pgTAP és izolált age backup/restore integráció: **success**.

Két egymástól független, azonos kód-headen futó teljes CI tehát azonos teszt- és coverage-eredménnyel zárult. Ez megerősíti a kódszintű javítás stabilitását, de nem változtatja meg a production Auth/RLS, AWS backup és migration reconciliation kapukat.
