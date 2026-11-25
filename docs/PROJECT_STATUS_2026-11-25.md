# JARVIS – projektállapot, hátralévő feladatok és lefedettség

**Állapotfelvétel:** 2026-11-25 (frissítve a PR #20 merge és backup/restore után)  
**Repository:** `tamaszsolt2005-hub/jarvis-core`  
**Main:** `71d6a1cdc755607a9598bf9b2c19c50730f5e036` (PR #21 squash merge)  
**Production Supabase:** `kiutreccucbegskxowek` (PostgreSQL 17.11)

> Ez a jelentés külön kezeli a kódbeli implementációt, CI-t, production backupot, production sémamódosítást és deployt. A sikeres backup/restore nem jelent production migrációt vagy deployt.

## 1. Vezetői összefoglaló

- PR #18, #19 és #20 squash merge-elve a `main` ágba.
- Aktuális main: `2e2a97e`; main CI run `45655131500` sikeres.
- PR #20 javította a S3 objektumellenőrző Python-blokk behúzását.
- **Production backup + ellenőrzés + restore: sikeres**, workflow-dispatch run `45655512387`.
- A backup futás minden lépése sikeres: age titkosított logikai dump, privát S3 feltöltés, SSE-KMS és KMS kulcs ellenőrzés, S3 objektum letöltés, age visszafejtés és manifest SHA-256 ellenőrzés, külön PostgreSQL 17 restore, 8 public tábla és kijelölt rekordszámok ellenőrzése.
- A restore izolált, eldobható runner konténerbe történt; a workflow summary szerint production DB írás nem történt.
- Production migration ledger/séma drift továbbra sincs rendezve; production DDL/DML, ledger repair, Auth/RBAC és deploy nem történt/engedélyezett.

## 2. Legutóbbi bizonyítékok

| Bizonyíték | Állapot | Mit igazol |
|---|---|---|
| Main CI `45655131500` | Sikeres | A `2e2a97e` main commit CI-je |
| PR #20 CI `45654575685` | Sikeres | A Python indentation javítás tesztjei |
| Backup workflow `45655512387` | Sikeres | Production dump → S3/KMS → letöltés/hash → izolált PG17 restore |
| Korábbi hibás backup `45654544915` | Sikertelen, már javított | PR #20 előtti indentation hiba; nem a jelenlegi eredmény |

Hivatkozások: [Main CI](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45655131500) · [PR #20](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/20) · [Sikeres backup+restore](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45655512387).

## 3. Az öt fő fejlesztési terület állapota

| # | Terület | Állapot |
|---|---|---|
| 1 | Megbízhatóság és biztonság | Kódjavítások és CI zöld; production backup+restore igazolt. Külső SMTP szolgáltatói idempotencia és teljes audit fail-closed lefedettség még nem igazolt. |
| 2 | Supabase és jogosultságkezelés | Részben előkészítve. Production drift friss read-only felmérése, migrációs rendezés, SQL review, deploy utáni RPC smoke és Auth/RLS validáció hátra van. |
| 3 | Önállóbb üzleti asszisztens | Részben implementálva. Leadkutatás, scoring, proaktív monitor és javaslati alapok vannak; minőségi mérés és éles működés nincs lezárva. |
| 4 | Üzleti munkafolyamatok automatizálása | Részben implementálva. Task és approval építőelemek vannak; teljes lead→eredménymérés E2E folyamat és üzleti KPI-k hiányoznak. |
| 5 | Tudás és hosszú távú memória | Alapok implementálva. Memória és analitika van; forrásolt, jogosultságkezelt, életciklus-kezelt tudásréteg minőségi bizonyítása hátra van. |

## 4. Elkészült és tesztekkel igazolt fejlesztések

- Backup CLI közvetlen futtatás importútvonalának javítása.
- S3 verification shell quoting és Python indentation javítása (PR #19/#20).
- DB-szintű egyszer használatos approval: principal/payload kötés, expiry/replay védelem, atomikus consume.
- Atomikus task+audit+operation RPC, operation ID és concurrency védelem.
- SMTP-attempt utáni bizonytalan kimenetel `unknown`; automatikus retry kizárása.
- Audit/hash-chain SQL és fix `search_path` hardening.
- Authenticated közvetlen task DML korlátozása; a service-role végső lockdown későbbre ütemezve.
- PostgreSQL 17 CI migrációs, pgTAP, katalógus és backup–restore integrációs tesztek.
- A tényleges production archívum külön PostgreSQL 17 restore próbája sikeres a run #45655512387-ben.

A legutóbbi korábban mért coverage: 90.75% line coverage, 759 passed / 3 skipped; ez a PR #20 utáni friss runból még nem újramért adat. Branch coverage nincs mérve. Korábbi artifact: [coverage XML](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45652611537/artifacts/15041113174).

## 5. Hátralévő feladatok és sorrend

| Prioritás | Feladat | Állapot | Következő bizonyíték |
|---|---|---|---|
| P0 | Production backup és restore | **Kész** | Run #45655512387 |
| P0 | Friss production schema + migration ledger read-only snapshot | Hátra / frissítendő | Új schema és remote ledger snapshot |
| P0 | 20261117 ledger drift rendezési terv | Hátra | A tényleges postcondition és a két verzió eredetének egyeztetése |
| P0 | Teljes migration lánc production-shape PG17 replay + adatmegőrzés | Részben kész | Friss, teljes lánc teszt és független SQL review |
| P0 | Audit/RBAC/idempotencia/approval production migrációs terv | Hátra | Pontos SQL review és külön production engedély |
| P1 | RPC-alapú app production deploy | Nem igazolt | Deploy target, secret-ek, health check |
| P1 | Deploy utáni task RPC smoke | Hátra | Élő RPC végrehajtás és régi write path kizárása |
| P1 | `20261125170000_enforce_atomic_task_write_privileges.sql` | Blokkolt, szándékosan | Csak deploy + RPC smoke után |
| P1 | Live Auth/JWT/RLS smoke | Hátra | Már létező, engedélyezett izolált Supabase környezet |
| P2 | Storage/Auth/Realtime/platform backup scope | Hátra | Logikai PostgreSQL backupon túli scope és runbook |
| P2 | Alacsony coverage modulok célzott tesztjei | Hátra | Új coverage artifact és célzott tesztek |
| P2 | Main branch protection / required checks | Ellenőrizendő | GitHub ruleset/branch protection read-only állapot |

## 6. Production Supabase – ismert korábbi állapot

A legutóbbi dokumentált read-only auditban:
- projekt `ACTIVE_HEALTHY`, PostgreSQL 17.11.0.019, régió `eu-west-1`;
- remote migration ledger öt visszanyert verziót tartalmazott;
- a két `20261117` migráció hatása látszott a sémában, de verzióik hiányoztak a ledgerből;
- 8 public tábla RLS-e engedélyezett volt, 0 policy-t talált a lekérdezés;
- `auth.users` üres volt;
- audit/hash-chain/RBAC/approval migrációk production alkalmazása nem volt igazolt.

**Fontos:** ez a 2026-11-25-i korábbi snapshot, nem friss ellenőrzés a backup után. Production módosítás előtt újra kell kérdezni.

## 7. Production tiltások és sorrend

Továbbra sem történt production DDL/DML, `supabase db push`, migration repair, ledger átírás, GRANT/REVOKE, RLS policy változtatás, Auth user provisioning vagy deploy. Auth/RBAC flag OFF.

Kötelező sorrend:
1. Backup+restore – **teljesült**.
2. Friss read-only production schema/ledger snapshot és drift egyeztetés.
3. SQL review és production migrációs terv jóváhagyása.
4. Engedélyezett migrációk szakaszos alkalmazása.
5. RPC-alapú app deploy és smoke.
6. Csak utána a végső service-role task DML lockdown.
7. Auth/RBAC bekapcsolás külön döntéssel.



## 8. Frissített ellenőrzési eredmények – 2026-11-25, PR #21 után

**Main:** PR #21 squash merge-elve; aktuális commit: `71d6a1cdc755607a9598bf9b2c19c50730f5e036`. A PR #21 mindkét workflow-futásában mindkét job sikeres: [run 45656372633](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45656372633) és [run 45656331519](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45656331519). A backup/restore job a 20261117 drift fixture-t, az audit/RBAC pgTAP- és katalógus-ellenőrzéseket, valamint a titkosított backup–restore kört is lefuttatta. Ezek izolált PostgreSQL 17 tesztek, nem production migrációk.

**Production read-only snapshot (2026-11-25, 16:44 UTC körüli lekérdezések):**
- A projekt elérhető; a public sémában 8 tábla található, mindegyiknél RLS enabled, de 0 RLS policy.
- A `private` séma nem létezik (nem pusztán üres).
- A remote migration ledger továbbra is pontosan 5 verziót tartalmaz: `20261119191911`, `20261119192040`, `20261119192145`, `20261119192412`, `20261119192559`.
- A `leads.website` és `logs.level` oszlop létezik, de a két `20261117` migráció verziója nincs a ledgerben. A `20261119192040_complete_jarvis_runtime_schema.sql` nem hozza létre ezeket az oszlopokat.
- A `public.logs` továbbra is legacy oszlopkészletű (`id`, `module`, `message`, `created_at`, `level`); hiányoznak a strukturált auditmezők és a hash-chain mezők.
- A `public.tasks.operation_id` hiányzik; a `public.audit_chain_state` tábla nincs jelen.
- A `private.task_approvals`, `private.task_action_operations` táblák és az approval/task RPC-k productionben nem találhatók.
- A közvetlen `anon` és `authenticated` DML-jogok a public táblákon vissza vannak vonva; a `service_role` a `tasks` és `logs` táblákon teljes DML/DDL-jellegű táblajogokat tartalmazó grantkészlettel rendelkezik (SELECT/INSERT/UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER).
- Security Advisor: 8 INFO jelzés, mind RLS policy nélküli táblákra. Performance Advisor: 7 használatlan indexre vonatkozó INFO jelzés. Health Advisor: nincs találat.

**Kód- és működési következtetések:**
- A `task_actions.py` egyetlen `execute_approved_task_action` RPC-t hív; mivel ez a RPC productionben hiányzik, a kód jelenlegi production adatbázissal nem tekinthető élesben működőképesnek. A végső `20261125170000` service-role task DML-lockdown migráció továbbra is blokkolt.
- Az `audit_event` strukturált mezőket ír a `logs` táblába, és hiba esetén `False`-t ad. A jelenlegi production oszlopkészlet ezeket nem tartalmazza, ezért az auditot előfeltételként használó érzékeny műveleteknek fail-closed módon meg kell állniuk; az éles RPC/audit működés ettől még nincs bizonyítva.
- A kimenő SMTP-küldés külön kódmódosításig hard-disabled: `email_utils.EMAIL_DELIVERY_ENABLED = False`, nem környezeti változóból olvasott kapcsoló. A `send_email()` azonnal, Auth/DB/secret elérés előtt hibával leáll; a scheduled outbound workflow-lépés is explicit módon ki van kapcsolva. A chatből készített tervezet és jóváhagyási UI megmarad, de a tényleges küldés nem lehetséges. A bejövő IMAP-válaszok és leiratkozások figyelése külön konfigurációval tovább működhet. A `send_unknown` állapot és az automatikus retry tiltása továbbra is tesztelt; a külső SMTP-szolgáltató idempotenciája és a live E2E nincs igazolva.
- A fail-closed audit és SMTP-állapotkezelés regressziós tesztjei léteznek, de ezek izolált unit/CI tesztek; nem helyettesítik a production schema és a külső szolgáltató validálását.

**Változtatási határ:** az audit során nem történt production DDL/DML, migration repair, GRANT/REVOKE, RLS-módosítás, Auth provisioning vagy deploy. A következő lépés kizárólag drift-egyeztetés, SQL review és production-shape migrációs replay; éles módosítás külön jóváhagyás nélkül továbbra sem végezhető.


**Kimenő e-mail biztonsági kapu – PR #23:** a kimenő SMTP-küldés kódszinten letiltva, a környezeti `EMAIL_DELIVERY_ENABLED` érték nem képes aktiválni. A scheduled küldési lépés workflow-szinten is tiltott; az inbound IMAP monitor külön maradt. Újraengedélyezés kizárólag külön security review, szolgáltatói idempotencia-bizonyíték és célzott E2E tesztek után történhet.


## 9. Friss biztonsági állapot – 2026-11-25 17:06 UTC

**Main / SMTP:** PR #23 squash merge-elve (`c1364e8aaf0741ba2c8ef33360799c744bf1b688`). A `send_email()` hard-disabled, az outbound workflow sender step letiltott. A merge utáni main CI `45661201562`: backup–restore sikeres, test job a frissítéskor futott. Production alkalmazásdeploy nem történt, ezért a main kódbeli állapot nem azonos a futó production runtime-mal.

**Production read-only audit:** PostgreSQL 17.11; 8 public tábla, mind a 8 RLS enabled, 0 policy. `anon` és `authenticated` SELECT/INSERT/UPDATE/DELETE jogosultsága mind a 8 táblán false; `service_role` mind a 8 táblán teljes DML jogosultsággal rendelkezik. `private` schema, `public.audit_chain_state`, `private.task_approvals`, `private.task_action_operations`, `private.execute_approved_task_action(...)` hiányzik. `tasks.operation_id` hiányzik. `auth.users` 0 sor. Migration ledger pontosan 5 bejegyzést tartalmaz, mind 20261119-es. `leads.website` text nullable; `logs.level` text NOT NULL default `'info'`. Security Advisor: 8 INFO `rls_enabled_no_policy` finding.

**Értékelés:** a public Data API szerepkörök közvetlen DML hozzáférése tiltott; a policy nélküli RLS táblák biztonsága a grantszintű tiltáson alapul. A service_role továbbra is közvetlen task DML-joggal rendelkezik. Az audit/hash-chain és task approval RPC-k production működése nem bizonyított, mert az objektumok hiányoznak. Production DDL/DML, migration repair, GRANT/REVOKE, Auth provisioning és deploy nem történt.

## 10. ÚJ FUNKCIÓK ELŐTTI KÖTELEZŐ KÉSZÜLTSÉGI ÁLLAPOT – 2026-11-25

**Döntés: JARVIS új üzleti funkcióinak fejlesztése még nem kezdhető el biztonságosan.** A következő lista a jelenlegi repo-, CI-, Supabase- és deploy-felmérés alapján készült. A `main` legutóbbi igazolt commitja: `c5cf1ded6d5ee3ef5635ef5dbad743073bff73e1` (PR #25); a PR #25 utáni main CI `45663296144` mindkét jobja sikeres.

### A. Megbízhatóság és biztonság – lezárandó
1. [ ] A JARVIS tényleges production alkalmazás-hostjának és URL-jének azonosítása. A GitHub repo nem tartalmazott deploy workflow-t vagy app URL-t; az elérhető Railway-fiókban csak a nem JARVIS VolleyForm található. A Streamlit Cloud / más külső host még nincs igazolva.
2. [ ] A main SMTP hard-disable változásának deployja a valódi production appba, majd futó runtime-bizonyíték, hogy outbound SMTP küldés nem lehetséges. A main kód és workflow tiltása önmagában nem bizonyítja a production runtime állapotát.
3. [ ] Az audit fail-closed működés teljes érzékeny műveleti útvonal-leltárának lezárása: minden kritikus task/approval/módosító útvonalnál auditírási hiba esetén a művelet álljon le.
4. [ ] Az atomikus task/approval és audit DB objektumok production-ready migrációs készletének véglegesítése, izolált PostgreSQL 17 replay és független SQL review.
5. [ ] Külső e-mail idempotencia megoldása csak választott providerrel. Stabil event idempotency key, változatlan request body, provider response ID tartós mentése, bizonytalan kimenetel `unknown`, automatikus retry tiltása a provider idempotenciaablak után, E2E teszt. Provider még nincs kiválasztva; SMTP maradjon tiltva.

### B. Supabase, migrációk és jogosultságok – lezárandó
6. [ ] A production migration ledgerben hiányzó két `20261117` bejegyzés eredetének és pontos postconditionjeinek egyeztetése; csak dokumentált, review-zott reconciliation tervvel.
7. [ ] A teljes repository migration lánc production-shape PostgreSQL 17 replay-je, meglévő adatok megőrzésének ellenőrzésével.
8. [ ] A productionben hiányzó `private` schema, structured audit mezők, `audit_chain_state`, `tasks.operation_id`, approval/operation táblák és RPC-k pontos migrációs tervének ellenőrzése.
9. [ ] A production SQL-készlet független review-ja, előre definiált pre/post-checkekkel és rollback/recovery tervvel.
10. [ ] Külön, konkrét jóváhagyás után a production migrációk szakaszos alkalmazása; remote ledger és katalógus utóellenőrzése.
11. [ ] Az alkalmazás RPC-alapú task write pathjának deployja és smoke tesztje; csak ennek sikere után a `20261125170000_enforce_atomic_task_write_privileges.sql` végső service_role közvetlen task DML tiltás.
12. [ ] A service_role közvetlen task DML tiltásának negatív tesztje, az atomikus RPC engedélyezett működésének és a régi write path kizárásának bizonyítása.
13. [ ] Live Auth/JWT/session refresh/RLS/role smoke egy már létező, külön engedélyezett izolált Supabase környezetben; invalid/expired token és admin/operator/reader negatív jogosultsági esetekkel. Production Auth/RBAC csak külön döntésre kapcsolható be.
14. [ ] A jelenlegi RLS állapot felülvizsgálata: 8 public tábla RLS-enabled, de 0 policy; anon/authenticated DML grant tiltása igazolt, ezt ne lazítsuk fel policy és teszt nélkül.

### C. Alkalmazás kiadhatósága és üzemeltetés
15. [ ] A valódi app host, build/start parancs, health check, környezeti változók és titokkezelés dokumentálása; secret értékek nem kerülhetnek a repo-ba vagy logba.
16. [ ] Production app deploy és smoke: indulás, DB kapcsolat, alap dashboard oldalak, task/approval RPC, audit, hibakezelés; SMTP tiltás runtime bizonyítéka.
17. [ ] Rollback/restore eljárás és üzemeltetési felelősség ellenőrzése. A PostgreSQL logikai backup és izolált PG17 restore már sikeres; Storage/Auth/Realtime/platform konfiguráció mentési scope-ja még tisztázandó.
18. [ ] GitHub main branch protection / required checks tényleges állapotának ellenőrzése és szükséges minimum beállítása.

### D. Funkcionális termékterületek – új funkciók előtt minimálisan szükséges lezárás
19. [ ] Önálló üzleti asszisztens: a proaktív lead- és üzletiváltozás-figyelés minőségének, forrásainak, bizonytalansági jelzésének és duplikációmentességének mérése.
20. [ ] Jóváhagyás nélkül ne legyen külső vagy üzleti hatású végrehajtás – ezt a fő útvonalakon negatív tesztek igazolják.
21. [ ] Üzleti munkafolyamat: Leadkutatás → minősítés → stratégia → task → approval → utánkövetés → eredménymérés állapotmodellje; megszakítás/folytatás/idempotencia és E2E bizonyíték.
22. [ ] Tudás/memória: forrásolt és jogosultságkezelt üzleti kontextus, frissesség/bizonytalanság, megőrzés/törlés, valamint tény és modellkövetkeztetés elkülönítése.

**Fontos határ:** production DDL/DML, migration push/repair, ledger módosítás, GRANT/REVOKE, RLS/Auth változtatás és production deploy csak külön, konkrét jóváhagyás után végezhető. A jelenlegi felhatalmazás nem helyettesíti ezt. Külső provider kiválasztását sem szabad feltételezni.

**Új funkciók indításának kapuja:** az A–C blokk valamennyi P0/P1 pontja zöld és bizonyítékkal lezárt; a D blokkhoz tartozó alapvető biztonsági és E2E kapuk teljesülnek. A nem kritikus P2 üzemeltetési fejlesztések külön backlogban maradhatnak, nem szabad végtelen tesztelési listává bővíteni a kaput. A fenti pontok lezárása után új funkciók behozhatók.


### Nehézségi becslés és párhuzamos végrehajtási szabály

Skála: **1 = nagyon könnyű, 10 = nagyon nehéz**. A pontszám a várható mérnöki munkát, bizonytalanságot és integrációs kockázatot becsüli; nem naptári idő. A **5/10 alatti** feladatokat egy közös, összehangolt munkacsomagban végzem el, amennyiben nincs köztük biztonsági vagy függőségi akadály. Az 5/10-es és afeletti feladatokat a szükséges sorrendben, külön ellenőrzési pontokkal végzem. Production művelethez ettől függetlenül továbbra is külön konkrét jóváhagyás kell.

| # | Feladat röviden | Nehézség |
|---:|---|:---:|
| 1 | Production app host/URL felderítése | **3/10** |
| 2 | SMTP hard-disable deploy és runtime bizonyíték | **4/10** |
| 3 | Audit fail-closed útvonal-leltár | **5/10** |
| 4 | DB migrációs készlet, PG17 replay, SQL review | **7/10** |
| 5 | Provider idempotencia és E2E | **8/10** |
| 6 | Két 20261117 ledger eltérés rendezési terve | **5/10** |
| 7 | Teljes migrációs lánc PG17 replay/adatmegőrzés | **6/10** |
| 8 | Hiányzó production audit/approval objektumok migrációs terve | **5/10** |
| 9 | SQL review, pre/post-check és rollback terv | **4/10** |
| 10 | Production migrációk szakaszos alkalmazása | **8/10** |
| 11 | RPC write path deploy és smoke | **7/10** |
| 12 | Service-role direkt DML negatív és RPC pozitív teszt | **4/10** |
| 13 | Auth/JWT/session/RLS/role smoke | **6/10** |
| 14 | RLS/grant állapot felülvizsgálata | **3/10** |
| 15 | Host/build/health/env/secret dokumentáció | **3/10** |
| 16 | Production app deploy és teljes smoke | **6/10** |
| 17 | Rollback/restore és üzemeltetési felelősség | **5/10** |
| 18 | Branch protection/required checks ellenőrzése | **2/10** |
| 19 | Proaktív üzleti monitor minőségmérése | **6/10** |
| 20 | Jóváhagyás nélküli végrehajtás kizárása | **6/10** |
| 21 | Lead→eredmény workflow E2E | **7/10** |
| 22 | Forrásolt és jogosultságkezelt memória | **7/10** |

**Együtt végzendő, 5/10 alatti csomag:** 1, 2, 9, 12, 14, 15, 18. Ezeket egy menetben készítem el, de a 2. pont éles deploy része csak a host igazolása és külön jóváhagyás után történhet. A 9. pont review-ja nem helyettesíti a production módosítás jóváhagyását.

## 2026-11-25 – az alacsony nehézségű feladatcsomag ellenőrzésének eredménye

A hét feladatot egy közös auditkörben ellenőriztem. Ez read-only vizsgálatokat és izolált CI-teszteket tartalmaz; production deploy, adatírás, GRANT/REVOKE, titokmódosítás és PR merge nem történt.

| Feladat | Eredmény | Állapot |
|---|---|---|
| Production host/URL felderítése | A repo Streamlit appot ír le, de nincs igazolt production URL vagy JARVIS deployment. A hozzáférhető Railway projekt nem JARVIS. | **Nyitott** |
| SMTP hard-disable | `EMAIL_DELIVERY_ENABLED = False`; a küldő az Auth/DB/secrets/SMTP elérése előtt hibával leáll; az email workflow outbound lépése `if: false`. | **Kódban ellenőrizve; production runtime/deploy nyitott** |
| SQL review/ellenőrzőlista | Előkészítési kapuk: migrációs sorrend, pre/post-check, adatmegőrzés, rollback/recovery, ledger reconciliation. | **Előkészítve; független SQL review nyitott** |
| Service-role negatív teszt | A PR CI izolált PostgreSQL 17 + pgTAP security jobja sikeres; a task service-role teszt a lockdown migráció után fut. Productionben a `service_role` INSERT/UPDATE/DELETE továbbra is engedélyezett. | **Izolált teszt sikeres; production ellenőrzés lockdown után nyitott** |
| RLS és grant felülvizsgálat | Friss read-only lekérdezés: mind a 8 public tábla RLS-enabled, 0 policy; `service_role` DML true; anon/authenticated DML revoke korábban igazolt. Security Advisor: 8 INFO `rls_enabled_no_policy`. | **Felülvizsgálat kész; policy/RBAC döntés és telepítés nyitott** |
| Host/build/health/secret dokumentáció | Megerősítve: Python 3.11, `streamlit run dashboard.py --server.port 8501`; health diagnosztika `health_check.run_self_diagnostics`; szükséges secretnevek dokumentálva, értékek nélkül. | **Ismert tények dokumentálva; host-specifikus runtime értékek nyitottak** |
| Branch protection ellenőrzése | GitHub branch API: `main.protected=false`; required checks enforcement `off`, contexts/checks üres; repository rulesets: üres lista. | **Audit kész; védelem beállítása nyitott** |

**Fontos production korlát:** a service_role production jogosultságát nem próbáltam éles DML-lel negatívan tesztelni, mert a jelenlegi grant még engedi az írást, és a rollback sem teszi kockázatmentessé az éles műveletet. A valós production negatív teszt csak a task RPC appverzió deployja és a külön jóváhagyott lockdown után futhat.

A PR #26 CI `45665466795` futásában a `backup-restore-integration` job sikeres; a `test` job eredménye a dokumentum frissítésekor még futott.

## További előrelépés – coverage célzás

A sikeres CI coverage artifactja (run `45666323123`) összesített **90,75% line coverage**-et mutatott (3729/4109 sor). A releváns gyenge pontok:
- `task_actions.py`: **81,4%** (136/167 sor).
- `scripts/supabase_auth_rls_smoke.py`: **17,3%** (42/243 sor); ez élő Supabase/Auth smoke CLI, amelynek nagy része külső környezethez és credentialshez kötött, ezért nem szabad vakon unit coverage célként kezelni.

A `tests/test_task_actions.py` fájlhoz további parser, payload-validáció, approval, hibás RPC-válasz és auth enforcement edge teszteket adtam hozzá. Az új PR-head CI eredménye még ellenőrzés alatt áll; a coverage javulását csak az új artifact alapján lehet kijelenteni.



## 2026-11-25 – produkciós alkalmazás-host felderítés (3. feladat)

Read-only ellenőrzés a `main` ágon és a hozzáférhető infrastruktúrában:
- A README Streamlit appot dokumentál (`dashboard.py`, Python 3.11, `streamlit run dashboard.py --server.port 8501`), de nem nevez meg production szolgáltatót vagy URL-t.
- A GitHub repository `homepage` mezője üres, GitHub Pages nincs bekapcsolva. A vizsgált repositoryban nem találtam Streamlit Cloud, Railway, Render, Fly.io, Vercel vagy más app-host URL-t / deployment konfigurációt.
- A hozzáférhető Railway workspace-ben egyetlen projekt van: `VolleyForm`; egyetlen szolgáltatása `volleyform-api`, domainje `volleyform-api-production.up.railway.app`. Ez másik repository/projekt, tehát **nem JARVIS host**.
- A production Supabase projekt csak adatbázis/API végpont; nem azonos a Streamlit dashboard hostjával.
- Nyilvános webes keresés sem adott ellenőrizhető JARVIS production URL-t.

**Eredmény: a host/URL nem azonosítható a jelenleg hozzáférhető bizonyítékokból.** Nem próbáltam a JARVIS-t a VolleyForm Railway szolgáltatásra telepíteni, nem hoztam létre új szolgáltatást, nem módosítottam DNS-t, változókat vagy secrets értékeket. A feladat blokkoló bemenete: a tényleges host/projekt megnevezése vagy a szolgáltatóhoz tartozó dashboard/deployment hivatkozás megadása.


## Legfrissebb állapot – PR #26, 2026-11-25

**Aktív fejlesztési ág:** `docs/pre-feature-readiness-gates` · **PR:** [#26](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26) (open, not merged) · **aktuális PR-head:** `a későbbi dokumentációs frissítéskor már elavult helyőrző (az aktuális headet a dokumentum végi friss állapotblokk rögzíti)` · **kód-CI-vel igazolt commit:** `38693f2f93b790608aef37a33f190a86e611ff0d`.

### Kód és tesztállapot
- SMTP hard-disable és bizonytalan kézbesítési kimenetel kezelése a branchben; az unknown státusz automatikus retry-ja tiltott.
- DB approval, atomikus task RPC/operation ID, replay/revoke és audit fail-closed SQL regressziós tesztek hozzáadva.
- Két-session concurrency teszt bekerült a PostgreSQL 17 audit/security CI lépésbe.
- Migration drift fixture, service-role negatív DML teszt és végső privilege-lock migráció a branchben; a privilege lock productionre blokkolt.
- A dokumentáció frissítésekor a `38693f2` kódcommiton a `45689264377` mindkét jobja sikeres; a párhuzamos `45689247826` futás megszakadt. Az aktuális dokumentációs PR-head CI-je még nincs zöldként igazolva.

### Production állapot
A branchben lévő változtatások nincsenek productionbe telepítve. A legutóbbi dokumentált production read-only snapshot változatlan kiindulópont; a későbbi audit/approval/RPC és privilege-lock migrációk nincsenek alkalmazva. A JARVIS app host nem azonosított; a csatlakoztatott Railway projekt VolleyForm, nem JARVIS. Nincs production DDL/DML, ledger repair, GRANT/REVOKE, Auth flag aktiválás, app deploy vagy PR merge.

**Aktuális értékelés:** a megbízhatóság/biztonság munkacsomag jelentős kódbeli része elkészült, de CI-véglegesítés, provider oldali e-mail idempotencia, production host/deploy és production DB integráció hiányában nem zárható le. A teljes JARVIS projekt nem kész.


## Resend adapter és legutóbbi CI – 2026-11-25

A PR #26 branchben elkészült a Resend HTTPS API adapter. A stabil lead + sequence operation ID az Idempotency-Key fejlécben kerül átadásra mind az első kapcsolat, mind a follow-up küldés során. A workflow EMAIL_PROVIDER=resend és RESEND_API_KEY secret bindinggal elő van készítve. A kimenő küldés továbbra is hard-disabled; live provider hitelesítés és küldés nem történt.

A kódcommit (1cd45b89e2acb05da773aa19f8d8a884a450b11f) CI-je 805 passed, 3 skipped; 91,20% line coverage eredménnyel zárult. A dokumentációs és biztonsági terminológiai frissítéseket tartalmazó be2a1fe commiton mindkét job sikeres: 805 passed, 3 skipped; 91,19% coverage, valamint PostgreSQL 17 backup/restore/security siker. [Push CI](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45692241435) · [PR CI](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45692250485).

A Resend idempotenciakulcsok 24 órás megőrzése korlátozza a deduplikációt. A send_unknown / followup_unknown állapot nem automatikusan újrapróbálható; kézi beavatkozás előtt provider-oldali egyeztetés kell. A secret/domain és live E2E még nyitott.


A legfrissebb headen (d83b016) mind a push, mind a PR workflow minden jobja sikeres: 806 passed, 3 skipped, 91,19% line coverage; a PostgreSQL 17 backup/restore/security job is zöld. [Push CI](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45692894757) · [PR CI](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45692878860). A Resend provider hard-disable külön regressziós tesztje is sikeres.


## Frissített állapot – 2026-11-25, PR #26 aktuális head

Ez a szakasz felülírja a dokumentum korábbi, PR #26-ra vonatkozó „CI még fut / aktuális head ismeretlen” mondatait. A korábbi időbélyeges production snapshotok történeti bizonyítékok maradnak, nem friss production auditok.

- PR #26: [GitHub](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26), állapot: open, `merged=false`.
- Branch: `docs/pre-feature-readiness-gates`.
- Legutóbbi dokumentációs head: `4e53eb19acb1d4859a7e0964a8d0e10cdc0f6322`.
- Teljesen ellenőrzött CI/CodeQL/dependency-audit head: `7c8e6970a733884f4423821cddf3731f58e5b392`; az ezt követő commitok dokumentációs javítások, új workflow-eredmény még nincs visszaigazolva.
- JARVIS CI run [45697839295](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45697839295): `test` és `backup-restore-integration` sikeres.
- CodeQL run [45697839266](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45697839266): `Analyze Python` sikeres, az Initialize és Analyze lépések is sikeresen befejeződtek.
- Dependency audit run [45697839307](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45697839307): `pip-audit` sikeres a `requirements-test.txt` alapján, runtime és tesztfüggőségekre.
- A Dependabot heti Python- és GitHub Actions-frissítési konfigurációja bekerült a branchbe.

**Értelmezés:** a három workflow és mind a négy job sikeres. Ez a repo/CI állapotot igazolja; nem bizonyítja, hogy nincs mindenféle biztonsági kockázat, és nem helyettesít CodeQL/Dependabot riasztáslista-áttekintést.

**E-mail:** a GitHub workflow `EMAIL_PROVIDER=smtp` beállítással a meglévő Gmail SMTP utat választja. Az `EMAIL_USER` és `EMAIL_PASSWORD` secretnevek meglétét a repo tulajdonosa ellenőrizte; értékük és az SMTP hitelesítés nem lett ellenőrizve. A küldés kódszinten hard-disabled, az outbound workflow-lépés tiltott. Resend adapter csak alternatív kódútvonal.

**Production:** továbbra sincs igazolt JARVIS app host/URL. Production deploy, migráció, ledger repair, DDL/DML, GRANT/REVOKE, Auth/RBAC változtatás és live e-mail-küldés nem történt. A korábban dokumentált Supabase snapshot időponthoz kötött, read-only történeti állapot; friss lekérdezés nélkül nem szabad aktuálisnak tekinteni.
