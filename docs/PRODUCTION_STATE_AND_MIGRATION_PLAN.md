# Production állapot és migrációs terv

**Állapot dátuma:** 2026-11-26. A JARVIS app nincs telepítve; az app-host kiválasztása későbbi release döntés. A Supabase production DB snapshot 2026-11-26-i read-only megfigyelés; az alkalmazás-host státuszát a legfrissebb felhasználói pontosítás külön tisztázta. A lentebbi friss read-only snapshot a PR #21 merge után készült; a production backup/restore sikeres, production séma módosítás nélkül.
**Production adatbázis:** Supabase PostgreSQL 17, project ref: `kiutreccucbegskxowek`.

## 1. Rövid állapot

- A production projekt elérhető, de a repositoryban lévő audit/RBAC migrációk nincsenek productionben alkalmazva.
- A megfigyelt 8 public tábla RLS-e engedélyezett, de a read-only lekérdezés 0 policy-t talált.
- A megfigyelt production `auth.users` tábla üres volt.
- A `logs` tábla legacy szerkezetű; a strukturált audit- és hash mezők, valamint az `audit_chain_state` hiányoztak.
- A shared-workspace RBAC migráció csak a repositoryban van; productionben nem futott.
- A dashboard Auth/RBAC feature flag maradjon OFF.
- A production változtatásokhoz szükséges migrációs előzmény nincs biztonságosan reconciliálva.

Ezek időponthoz kötött megfigyelések, nem örök érvényű állítások. Módosítás előtt új read-only ellenőrzés szükséges.

## 2. Migration drift

A production remote migration ledger öt olyan korábbi verziót tartalmaz, amelyek SQL-forrása visszakerült a repositoryba:

- `20261119191911_create_jarvis_memory_and_fk_indexes`
- `20261119192040_complete_jarvis_runtime_schema`
- `20261119192145_enable_rls_on_legacy_posts`
- `20261119192412_revoke_anon_authenticated_public_table_and_sequence_privileges`
- `20261119192559_secure_postgres_default_privileges_public_schema`

További eltérések:
- A `20261117090000_add_leads_website.sql` és `20261117100000_add_logs_level.sql` hatásai a production sémában látszottak, de a verzióik nem szerepeltek a megfigyelt remote ledgerben.
- A strukturált audit, hash-chain, shared-workspace RBAC és task-create idempotencia migrációk repository-only állapotúak; productionben nem alkalmazottak.
- A production `settings` integer ID/sequence modellt és legacy `posts` táblát tartalmazott; a történeti adatokat meg kell őrizni.

A CI PostgreSQL 17 fixture a migrációs láncot és a katalógus-postconditionöket teszteli. Ez nem oldja meg a remote ledger és a live séma eltérését.

## 3. Kötelező rendezési sorrend

1. Friss, read-only production schema + migration ledger snapshot készítése.
2. A két 20261117 verzió hiányzó ledger-bejegyzésének okát és biztonságos kezelését pontosan megállapítani. Ne futtasd újra vakon a már látható hatású SQL-t.
3. Az öt visszanyert történeti SQL-forrást, a live postconditionöket és a repo migrációkat függetlenül összevetni.
4. A teljes migrációs láncot production-shape izolált PostgreSQL 17 környezetben próbálni, meglévő adatok megőrzésével.
5. Az audit/RBAC/idempotencia migrációkat és az alkalmazási sorrendet külön SQL review-val jóváhagyni.
6. Valós Auth/JWT/RLS smoke tesztet csak már létező, kifejezetten engedélyezett izolált Supabase környezetben futtatni. Új projektet vagy branch-et ne hozz létre.
7. Csak mindezek után készíts pontos production változtatási tervet, friss ellenőrzött backup mellett. A production DDL végrehajtásához külön, konkrét jóváhagyás kell.
8. Read-only postcondition ellenőrzés, admin Auth user provisioning és feature flag aktiválás külön release lépés, külön engedéllyel.

## 4. Backup állapot

**Friss eredmény (2026-11-25):** a main commit `2e2a97e` alatti workflow-dispatch run `45655512387` teljesen sikeres. A workflow létrehozta az age titkosított production logikai dumpot, feltöltötte privát S3-ba SSE-KMS titkosítással, ellenőrizte a S3 objektum KMS kulcsát és méretét, letöltötte az objektumot, visszafejtette és ellenőrizte a manifest SHA-256 hash-eket, majd az archívumot egy külön, eldobható PostgreSQL 17 konténerbe állította vissza. Az ellenőrzés 8 várt public táblát és a leads/logs/settings rekordszám-lekérdezéseit igazolta. A workflow summary szerint production DB írás nem történt. [Részletes workflow](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45655512387).

Ez a sikeres futás a korábbi, hibás #45652336576 / #45654544915 próbálkozásokat felülírja a backup gate szempontjából. A korábbi sikertelenségek történeti hibák, nem a jelenlegi workflow állapota.



A korábbi, 2026-11-25-i `45611038142` workflow sikeresen titkosította a production logikai adatbázis-dumpot age segítségével, S3-ba töltötte SSE-KMS titkosítással, majd letöltés/visszafejtés/hash ellenőrzést végzett. Ez történeti siker, nem igazolja a legutóbbi main futás eredményét.

A PR #13 merge után indult `45624735241` backup workflow **FAILED**: a `scripts/supabase_backup.py` indításakor `ModuleNotFoundError: No module named 'jarvis_errors'` történt. Emiatt a backup létrehozása, S3-feltöltése és restore lépései nem futottak le. A hiba kódjavítást és új futást igényel.

A sikeres logikai dump sem teljes Supabase platform-mentés: nem tekinthető a Storage bináris objektumok, Auth/Realtime platformadatok, projektbeállítások és titkos platformkulcsok teljes mentésének. A tényleges production archívum külön adatbázisba történő restore-ját külön kell bizonyítani.

## 5. CI állapot a merge után

- Aktuális main commit: `2e2a97e182687c9b9d018da99b87095b75a21054` (PR #20 squash merge).
- Main CI run `45655131500`: sikeres.
- PR #20 CI run `45654575685`: sikeres.
- Main push backup run `45655131449` és kézi workflow-dispatch backup run `45655512387`: sikeres; utóbbi minden ellenőrzési és restore lépése zöld.



- Main commit: `bb5788e94b60a11185c45502b45d351ab2b2189b`.
- A merge utáni CI `45624735367`: mindkét job (`test`, `backup-restore-integration`) befejeződött és sikeres. [GitHub Actions](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45624735367).
- A merge utáni production backup workflow `45624735241`: sikertelen, a fenti importhiba miatt.
- A CI eredményeket mindig a pontos commit SHA-hoz kösd; ne másold át a korábbi branch vagy régi main futás eredményét.

## 6. Tilos külön jóváhagyás nélkül

- `supabase db push`, `supabase migration repair`, migration ledger kézi módosítása;
- production DDL/DML, GRANT/REVOKE, RLS policy változtatás;
- Auth user létrehozás, szerepkör kiosztás, production Auth/RBAC flag bekapcsolása;
- AWS production deploy vagy backup infrastruktúra módosítása;
- új Supabase projekt vagy branch létrehozása.

A sikeres backup nem oldja meg a migration driftet, és nem engedélyez production DDL-t. A részletes release-engedélyezési feltételek a [release gate dokumentumban](REMAINING_WORK_AND_RELEASE_GATES.md) vannak.


## 7. Friss production read-only snapshot – 2026-11-25, PR #21 után

A PR #21 merge után ismételt, read-only Supabase audit pontosította a korábbi megfigyeléseket:

- A productionben csak a `public` schema létezik a vizsgált alkalmazási sémák közül; a `private` schema **nem létezik**.
- A nyolc public tábla mindegyikén RLS enabled, de a policy-k száma nulla.
- A remote migration ledger továbbra is öt verzió: `20261119191911`, `20261119192040`, `20261119192145`, `20261119192412`, `20261119192559`.
- A `leads.website` és `logs.level` oszlopok jelen vannak, de a `20261117090000` és `20261117100000` ledger-bejegyzések hiányoznak. A `20261119192040` migráció nem tartalmazza ezek létrehozását.
- A `logs` csak legacy mezőket tartalmaz; strukturált audit- és hash-chain mezők nincsenek. A `tasks.operation_id`, `public.audit_chain_state`, a private approval táblák és a kapcsolódó RPC-k hiányoznak.
- `anon` és `authenticated` közvetlen DML-jogosultságai vissza vannak vonva; a `service_role` teljes táblajogosultság-készlettel rendelkezik legalább a `tasks` és `logs` táblákon.
- Security Advisor: 8 INFO RLS-policy jelzés; Performance Advisor: 7 INFO unused-index jelzés; Health Advisor: nincs találat.

A CI #45656372633 és #45656331519 sikeresen futtatta a 20261117 drift fixture, az audit/RBAC pgTAP, katalógus-postcondition és backup–restore ellenőrzéseket. Ez izolált PG17 teszt, nem production ledger repair vagy migráció.

**Következmény:** a repositoryban előkészített audit/approval/task RPC migrációs lánc productionben nincs telepítve. Az alkalmazás RPC útvonala és az éles auditírás ezért még nem tekinthető productionben igazoltnak. A `20261125170000_enforce_atomic_task_write_privileges.sql` csak RPC-alapú app deploy és sikeres smoke teszt után alkalmazható.

Az audit nem módosította a production adatbázist. Ne futtass `supabase db push`-t, `migration repair`-t, DDL/DML-t vagy GRANT/REVOKE műveletet a drift független egyeztetése és külön jóváhagyás nélkül.

## 2026-11-25 – alacsony nehézségű auditcsomag eredménye

- **JARVIS app host:** a README Streamlit alkalmazást és `streamlit run dashboard.py --server.port 8501` indítást dokumentál; production URL/host nincs a repo-ban igazolva. A hozzáférhető Railway szolgáltatás nem JARVIS, ezért nem használható JARVIS URL-ként.
- **Build/runtime:** Python 3.11; fő függőségek a `requirements.txt` fájlban. A Streamlit secrets példa kulcsnevei: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY`, `JARVIS_DASHBOARD_PASSWORD`, e-mail fiókhoz `EMAIL_USER` és `EMAIL_PASSWORD`; titokértékek nem kerültek kiolvasásra vagy dokumentálásra.
- **Health check:** a repository `health_check.run_self_diagnostics()` read-only diagnosztikát ad, beleértve Supabase táblák/oszlopok, Gemini konfiguráció és SMTP biztonsági zár vizsgálatát. Ez nem igazolja a production host futó példányát.
- **SMTP:** a `email_utils.py` hard-disable konstansa `False`; a `send_email()` az Auth/DB/secret/SMTP hívások előtt RuntimeErrorral leáll. Az `.github/workflows/email-automation.yml` kimenő küldési lépése `if: ${{ false }}`. Ez kód- és workflow-bizonyíték, nem production runtime-bizonyíték.
- **Production Supabase read-only állapot:** 8 public tábla RLS-enabled, policy nincs; `service_role` INSERT/UPDATE/DELETE jog mind a nyolcon true. Security Advisor: 8 INFO `rls_enabled_no_policy`. A `service_role` production task DML negatív tesztjét ezért nem futtattam éles adatírással.
- **Izolált jogosultsági teszt:** a PR #26 CI `backup-restore-integration` jobja PostgreSQL 17 + pgTAP környezetben sikeres; benne a structured audit/RBAC katalógus- és task service-role tesztek lefutottak.
- **GitHub main védelem:** `main.protected=false`; required checks enforcement `off`, üres checklista; repository rulesets üres. A branch protection beállítása még szükséges.

Egyik ellenőrzés sem változtatott production adatbázison, alkalmazáson, secrets értéken vagy GitHub branch protection beállításon.

## SQL migrációs kód előzetes statikus áttekintése

A `20261123093000`, `20261124130000`, `20261125150000`, `20261125160000` és `20261125170000` migrációk statikus olvasása alapján a fő biztonsági sorrend helyesnek tűnik: append-only audit trigger és hash-chain; trusted `app_metadata.role` alapú RLS; hashed, rövid életű approval; tranzakciós idempotens RPC; végső task DML revoke csak az RPC-enabled app deployja után. A migrációs lánc kódja nem módosult.

**Production előtti kötelező bizonyítékok:** (1) PostgreSQL 17 tiszta és production-shape replay; (2) security-definer függvények tényleges ownerének és EXECUTE-grantjeinek ellenőrzése; (3) párhuzamos azonos operation_id és token replay teszt; (4) audit insert/trigger hiba esetén task tranzakció rollback bizonyítása; (5) legacy logs sorok és settings kulcs/érték adatmegőrzés; (6) migration ledger drift explicit reconciliation. Ez az áttekintés nem helyettesít független SQL review-t és nem engedélyez production alkalmazást.


## 2026-11-25 – alkalmazás-host felderítés

A GitHub repository metadata alapján nincs homepage URL és GitHub Pages sincs engedélyezve. A repository Streamlit `dashboard.py` alkalmazást tartalmaz, de nem tartalmaz igazolt Streamlit Cloud/Railway/Render/Fly/Vercel deployment hivatkozást. A hozzáférhető Railway accountban csak a `VolleyForm` projekt (`volleyform-api` szolgáltatás, `volleyform-api-production.up.railway.app` domain) látható; ez nem JARVIS és nem szabad JARVIS production hostként kezelni. A Supabase projekt URL adatbázis/API végpont, nem alkalmazás-host.

**Állapotkorrekció – 2026-11-26:** a JARVIS alkalmazás még nincs telepítve semmilyen app-hostra. Ezért nincs production JARVIS app-host/URL, nem pusztán ismeretlen a már létező host. A korábbi Railway `VolleyForm` projekt nem JARVIS. Jelenleg helyi Streamlit fejlesztés folyik; a host kiválasztása későbbi release döntés. A Supabase production adatbázis ettől külön létező szolgáltatás. Eddig semmilyen új app deploy, domain/DNS, secrets vagy infrastruktúra-módosítás nem történt.


## 2026-11-25 – migration ledger reconciliation and full-chain read-only review

A fresh production check was performed against Supabase project `kiutreccucbegskxowek` (PostgreSQL 17.11).

### Reconciled historical ledger entries

The live schema was checked before touching the migration ledger:

- `public.leads.website` exists as nullable `text`, matching `20261117090000_add_leads_website.sql`.
- `public.logs.level` exists as non-null `text` with default `'info'::text`, matching `20261117100000_add_logs_level.sql`.

Only after those postconditions and the expected migration names were verified, the two missing rows were inserted into `supabase_migrations.schema_migrations`:

- `20261117090000 / add_leads_website`
- `20261117100000 / add_logs_level`

A fresh `list_migrations` read confirmed both rows, seven total ledger entries, and no duplicate versions. The two schema migrations were **not rerun**. No other production schema, data, grant, RLS, or application change was made.

### Complete repository migration inventory

The branch contains 13 migration files. Seven are now represented in the production ledger; six remain unapplied:

1. `20261120090000_expand_logs_audit_fields`
2. `20261123093000_admin_audit_access_and_hash_chain`
3. `20261124130000_shared_workspace_role_access`
4. `20261125150000_task_creation_idempotency`
5. `20261125160000_atomic_task_approvals_and_operations`
6. `20261125170000_enforce_atomic_task_write_privileges`

The earlier 20261117 effects are present and reconciled. The production read-only snapshot confirms the later audit columns, `audit_chain_state`, `tasks.operation_id`, private approval/operation tables, and task RPCs are still absent.

### Dependency and rollout review

- `20261120090000` must precede `20261123093000`, which adds the audit hash-chain schema and trigger.
- `20261124130000` requires the audit-chain table and the JARVIS workspace tables; it must follow the audit migrations.
- `20261125150000` adds the task operation key required by `20261125160000`.
- `20261125160000` depends on the structured audit fields, audit actor field, and task operation key.
- `20261125170000` removes direct `service_role` task DML. It must remain unapplied until the RPC-enabled application is deployed and a production smoke test proves the new write path works.

The repository directory contains 13 files; there is no `20261124150000` migration file in this branch. Do not invent or ledger an absent migration version.

**Current result:** the two historical ledger gaps are reconciled and verified. The complete file inventory and dependency order are reviewed, but the six later migrations are intentionally not applied. No CI was run, in accordance with the agreed batch-testing workflow. The app host is still unidentified, so the required application deploy/smoke gate for the final privilege-lock migration remains blocked.


## 2026-11-25 – RBAC task-read coverage review

A follow-up static review confirmed that the shared-workspace policy-generation loop in `20261124130000_shared_workspace_role_access.sql` already includes `public.tasks`; it creates the `tasks_shared_read` policy for authenticated admin/operator/reader roles. The migration itself did not need a change.

The test suite did not explicitly prove that task rows are visible to reader and operator roles. Added two behavioral assertions to `supabase/tests/shared_workspace_role_access.test.sql` and a catalog postcondition requiring the `tasks_shared_read` SELECT policy. The pgTAP plan was increased from 34 to 36 assertions.

No production changes were made. No CI or database tests were run, in accordance with the agreed batch-testing sequence; the tests remain queued for the consolidated run after the full implementation/review batch.


## Branch és production állapot szétválasztása – 2026-11-25, PR #26

A [PR #26](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26) fejlesztési ágán új audit/approval/task RPC migrációk, privilege-lock SQL és hozzájuk tartozó tesztek szerepelnek. Ezek **repository/branch állapotúak**, nem production állapotúak. A aktuális PR-head `a PR oldalon látható aktuális head`; a kód- és tesztváltozások CI-vel igazolt commitja `38693f2f93b790608aef37a33f190a86e611ff0d`; a PR nincs merge-ölve.

A korábbi production snapshot a két `20261117` ledger gap reconciliation után hét migrációs ledger bejegyzést rögzít, míg hat későbbi migráció továbbra is unapplied. A `20261125160000_atomic_task_approvals_and_operations.sql` és `20261125170000_enforce_atomic_task_write_privileges.sql` nem tekinthető productionben telepítettnek. A CI PostgreSQL 17 fixture tesztje nem ír a Supabase production adatbázisba.

**Végrehajtási sorrend változatlan:** független SQL review és teljes izolált PG17 CI siker → a tényleges app host azonosítása → külön jóváhagyott app/RPC rollout és smoke → külön jóváhagyott production migráció/ellenőrzés → csak ezt követően a végső service-role task DML revoke. A production Auth/RBAC flag OFF marad. Sem migration push/repair, sem GRANT/REVOKE, sem deploy nem történt a PR #26 dokumentációs frissítésével.


## Email provider státusz – 2026-11-25

A Resend API adapter a PR #26 branchben van, de productionben nincs aktiválva. A GitHub email workflow a RESEND_API_KEY secretet várja és EMAIL_PROVIDER=resend értéket ad át, miközben a küldési lépés if: false és a kódbeli EMAIL_DELIVERY_ENABLED konstans False. Nem történt API-hívás, secretmódosítás vagy levélküldés. A Resend 24 órás idempotencia-retenciója miatt az unknown küldéseket provider-oldalon kell egyeztetni; a hard-disable feloldása külön jóváhagyás nélkül tilos.



## 2026-11-26 – production bizonyítékok frissessége és PR #26 határ

**Fontos frissességi megjegyzés:** a dokumentum korábbi, 2026-11-25-i Supabase read-only snapshotja történeti megfigyelés. Ebben a munkamenetben nem történt új production Supabase-lekérdezés, ezért a korábbi hét ledger-bejegyzésre, hiányzó objektumokra, RLS/policy állapotra és privilege-ekre vonatkozó számok nem tekinthetők 2026-11-26-i állapotigazolásnak. Production módosítás nem történt.

A PR #26 branch legutóbbi ellenőrzött CI-je (head `6ef4020bba3949e02440e97583fc907b6bcb1f00`) sikeres: 838 passed, 3 skipped, 91.29% coverage; PostgreSQL 17 izolált migráció/pgTAP/backup-restore, CodeQL és pip-audit szintén sikeres. Ezek kizárólag branch/CI bizonyítékok, nem production séma vagy migrációs állapot.

A PR-ben szereplő `20261125180000_unique_normalized_lead_email.sql` és audit/approval/RPC/privilege-lock migrációk productionben történő alkalmazása nincs igazolva, és nem történt meg ebben a munkában. A production migráció előtt friss read-only schema + ledger snapshot, email duplikációs preflight, független SQL review, izolált teljes PG17 replay és külön konkrét jóváhagyás szükséges. A service_role task DML revoke továbbra is csak a tényleges RPC app path deployja és sikeres smoke után jöhet szóba.

A global lead research cég/domain konkurenciakockázatát a PR #26 tranzakciós `upsert_company_lead` RPC-je kezeli; a két-session CI teszt sikeres. Ez branch-kód, nem production telepítés. Ez branchben is nyitott fejlesztési feladat, nem production hotfix.

## 2026-11-26 – release readiness újraellenőrzés

A PR #26 aktuális headjén (a README frissítése előtti `79dfb5b85afaa3ae21405b295bb23880019ec54d` commiton) a GitHub Actions eredményei:

- JARVIS CI: sikeres; 838 passed, 3 skipped; 91,29% coverage.
- PostgreSQL 17 backup–restore integráció: sikeres.
- CodeQL: sikeres.
- Dependency vulnerability audit: sikeres.

Ez kizárólag a repository és az izolált CI bizonyítéka. **2026-11-26-án friss, kizárólag read-only Supabase production audit készült** a `kiutreccucbegskxowek` projekten (PostgreSQL 17.11). A remote migration ledger 7 migrációt tartalmaz, benne a két korábban hiányzónak jelölt 20261117 verzióval. A 8 public tábla mindegyikén RLS enabled, de 0 policy van. `anon` és `authenticated` szerepköröknek nincs közvetlen public táblajogosultságuk; a `service_role` mind a nyolc táblán SELECT/INSERT/UPDATE/DELETE joggal rendelkezik. A `private` schema nem létezik, a public/private alkalmazási RPC-k hiányoznak, az `auth.users` rekordszáma 0. A `leads` táblában 11 rekord van és a normalizált email-duplikációs preflight 0 csoportot talált; a `leads_email_normalized_uidx` index nincs telepítve, és a 20261125180000 migráció nem szerepel a remote ledgerben. Security Advisor: 8 INFO policy nélküli RLS jelzés; Performance Advisor: 7 INFO nem használt index; Health Advisor: nincs találat. Nem történt Auth/RLS smoke, production host ellenőrzés vagy deploy. A 2026-11-25-i snapshot történeti adat, a 2026-11-26-i audit a jelenlegi read-only DB-állapot pillanatképe.

A JARVIS alkalmazás még nincs telepítve, ezért nincs app-hostja vagy URL-je; a hostválasztás későbbi release feladat. A production release ezért blokkolt a host és runtime bizonyíték megszerzéséig, a migration drift független egyeztetéséig, a teljes PG17 replay és SQL review lezárásáig, az Auth/RLS hozzáférési modell rendezéséig, valamint a külön production jóváhagyásig. A read-only audit nem változtatott semmilyen production objektumon vagy adaton. A PR nyitva maradt; production rendszeren nem történt változtatás.


## 2026-11-26 – új lead identity migration: PR-ág, nem production

A PR #26 új `20261126120000_atomic_company_lead_identity_and_contact_priority.sql` migrációja létrehozza a cégazonosság-alias registryt és a consenthez kötött kontaktjelölt-táblát, valamint a rögzített search_path-ú SECURITY DEFINER RPC-t. A kompatibilis rollout érdekében ez az első migráció átmenetileg nem vonja vissza a régi app lead INSERT-jogát. A külön `20261126130000_enforce_atomic_company_lead_writes.sql` migrációt csak az RPC-t használó app telepítése és smoke tesztje után szabad futtatni: ez zárolja és újra-backfill-eli a leadeket, majd visszavonja a service_role közvetlen INSERT/DELETE jogait. Mindkét migráció duplikált név/domain/email esetén leáll, meglévő rekordot nem töröl és nem olvaszt össze. A személyes webmail címek prioritása a szerepkörös címek fölé kerül, de csak az adott emailre igazolt, külön consent alapján. Outreach megkezdése után a címválasztás befagy.

Ez a két migráció jelenleg csak a PR-ágban található. **Productionben nem futott le**, és a korábbi 2026-11-26-i read-only snapshotot nem változtatta meg. A `96d4aa48a312b1942e61bb7c659dce6cdd790b0f` commiton az izolált PostgreSQL 17 migráció replay, SQL tesztek, két-session race teszt, teljes Python/AppTest/browser CI, CodeQL és dependency audit sikeres. Production alkalmazás előtt ettől függetlenül szükséges a host/runtime azonosítása, Auth/RLS hozzáférési modell, app deploy és a kétfázisú rollout külön jóváhagyása. A két migrációt nem szabad egyetlen rollout-lépésként futtatni: a write-lockdown kizárólag az új app verzió és a régi worker-ek leállásának igazolása után következhet. Production deploy vagy adatbázis-módosítás külön jóváhagyás nélkül továbbra is tilos.
