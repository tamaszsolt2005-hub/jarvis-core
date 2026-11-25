# JARVIS – fejlesztési backlog

**Alapág:** `main`  
**Szabály:** ez a részletes technikai backlog az [elsődleges fejlesztési útitervet](JARVIS_DEVELOPMENT_ROADMAP.md) szolgálja ki. A munkát mindig a roadmap sorrendje vezérli; a backlog nem jogosít fel későbbi területek előrehozására.

## 1. Megbízhatóság és biztonság

1. **Backup workflow javítása és igazolása – KÉSZ.** A CLI importútvonal, S3 shell quoting és Python indentation hibák javítva PR #18–#20-ban. A `main` CI `45655131500` sikeres. A production backup workflow `45655512387` minden lépése sikeres: titkosított dump, S3/SSE-KMS feltöltés és ellenőrzés, letöltés/visszafejtés/hash, külön PostgreSQL 17 restore és táblainventár/rekordszám ellenőrzés. Ez a backup gate teljesült.
2. **Task approval race.** Az egyszer használatos jóváhagyás jelenlegi UI-session kezelése nem garantál atomikus, több processz közötti one-use fogyasztást. Vezess be DB-szintű atomikus consume műveletet, lejáratot, principal- és payload-kötést, konkurens teszteket.
3. **Teljes műveleti idempotencia.** A task approval/execute RPC operation ID-val és concurrency-védelemmel implementált és tesztelt. A task update/close teljes műveleti lefedettségét és a külső szolgáltatók idempotenciáját még külön igazolni kell.
4. **Audit fail-closed lefedettség.** Készíts érzékeny műveleti útvonal-leltárt, majd bizonyítsd teszttel, hogy auditírási hiba esetén minden kritikus művelet leáll.
5. **Külső e-mail integritás.** SMTP unknown kimenetel után nincs bizonyított szolgáltatói idempotencia; az automatikus retry duplikált küldést okozhat. Kimenő küldés maradjon tiltott, amíg a deduplikáció és a végponttól végpontig tesztek nincsenek készen.

## 2. Supabase és jogosultságkezelés

**Aktuális állapot:** a production backup/restore gate teljesült (`45655512387`), de a schema/ledger drift továbbra is nyitott. A következő feladat friss read-only snapshot, nem migrációfuttatás.

- A két 20261117 migration ledger eltérés rendezési tervének bizonyítása.
- Production-shape PostgreSQL 17 migrációs replay és adatmegőrzési ellenőrzés.
- Audit/hash-chain/RBAC/idempotencia migrációk független SQL review-ja.
- Auth/RLS live smoke teszt meglévő, engedélyezett izolált Supabase környezetben.
- Auth session refresh, szerepkörváltozás, invalid/lejárt JWT, reader/operator/admin negatív tesztjei.
- Különválasztani és dokumentálni a user-JWT dashboard klienst és a háttérfolyamat service-role kliensét; a service-role kulcs soha ne kerüljön felhasználói kliensbe.
- [KÉSZ] A production logikai backup tényleges külön PostgreSQL 17 adatbázisba restore-ja igazolt (`45655512387`).
- A Supabase platformon kívüli mentési igények (Storage objektumok, Auth/Realtime és konfiguráció) tisztázása.

## 3. Önállóbb üzleti asszisztens

- Proaktív lead- és üzletiváltozás-figyelés minőségének és megbízhatóságának javítása.
- Lehetőségfelismerés indoklással, forrásokkal és bizonytalansági jelzéssel.
- Jóváhagyásra váró feladat- és következőlépés-javaslatok.
- Bizonyítani, hogy jóváhagyás nélkül nem történik külső vagy üzleti hatású végrehajtás.

## 4. Üzleti munkafolyamatok automatizálása

- Leadkutatás → minősítés → stratégia → feladat → jóváhagyás → utánkövetés → eredménymérés folyamat állapotmodellje.
- Minden lépés bemenetének, kimenetének, felelősének, hibakezelésének és idempotenciájának meghatározása.
- Megszakítás, folytatás, audit és eredménymérés végponttól végpontig tesztelése.

## 5. Tudás és hosszú távú memória

- Forrásolt, jogosultságkezelt üzleti kontextus és tartós visszakeresés.
- Leadek, ügyfelek, interakciók, döntések, feladatok és eredmények közötti kapcsolatok.
- Korábbi döntések és eredmények alapján visszakereshető tanulságok.
- Frissesség, bizonytalanság, megőrzés és törlés kezelése.
- Tények, források és modellkövetkeztetések világos elkülönítése.

## Közös mérnöki követelmények

- A tartós ág `main`; rövid életű feature ág csak integrációhoz.
- Egy változtatás = célzott kód + teszt + releváns dokumentáció.
- Production változtatás csak a külön dokumentált release gate-ek és konkrét jóváhagyás után.
- SMTP kimenő küldés maradjon tiltva, amíg az idempotencia és a végponttól végpontig tesztek nem teljesek.


## Friss audit és külső e-mail idempotencia – 2026-11-25

Production read-only audit: 8 public tábla, mind RLS enabled, 0 policy; anon/authenticated DML jog false, service_role teljes DML jog true. `private` schema, audit chain state, approval táblák/RPC és `tasks.operation_id` hiányzik; migration ledgerben 5 (20261119) bejegyzés van. Nincs production írás vagy deploy.

Provider idempotencia követelmények: stabil üzleti eseményhez kötött kulcs, request body tartós tárolása és változatlan újraküldése, provider válaszazonosító mentése, 24 órás provider-key lejárat után automatikus retry tiltása / manuális egyeztetés. Resend API hivatalosan dokumentálja az `Idempotency-Key` fejlécet, azonos payload elvárást és 24 órás időablakot: https://resend.com/blog/engineering-idempotency-keys. SMTP hard-disable maradjon aktív, amíg ez és a teljes E2E nincs tesztelve.

## ÚJ FUNKCIÓK ELŐTTI VÉGES BACKLOG – 2026-11-25

Az alábbi pontok a jelenlegi tényleges állapotot tükrözik; a már kész kódot nem kell újraimplementálni. Csak a hiányzó production integrációt, döntést és bizonyítékot kell lezárni.

### P0 – biztonságos production alap
- [ ] JARVIS tényleges production host/URL felderítése. A repo-ban nincs app URL/deploy workflow; az elérhető Railway projekt másik termék. Ne deployoljunk találomra.
- [ ] PR #23 SMTP hard-disable deployja a valós app hostra, runtime ellenőrzéssel. Main CI zöld, de production runtime nincs bizonyítva.
- [ ] Production schema/ledger drift reconciliation: a két `20261117` migráció eredetének tisztázása; teljes PG17 migration replay és adatmegőrzés; független SQL review.
- [ ] A hiányzó production audit/approval/operation DB objektumok migrációs csomagja és deployja: private schema, structured audit/hash-chain, `tasks.operation_id`, approval/operation táblák és RPC-k.
- [ ] Érzékeny műveleti útvonal-leltár és audit fail-closed bizonyítása.
- [ ] RPC-alapú task write path deploy + smoke; utána `20261125170000` service_role task DML lockdown, majd negatív direct-DML és pozitív RPC teszt.
- [ ] Live Auth/JWT/session/RLS/role smoke már létező, engedélyezett izolált Supabase környezetben.
- [ ] Production release: health check, task/approval/audit/RPC smoke és rollback ellenőrzés.

### P1 – külső integritás és termék-alapok
- [ ] E-mail provider kiválasztása; stabil idempotency key, változatlan request body, provider response ID mentése, `unknown` kimenetel és retry-határ kezelése, E2E. Addig SMTP maradjon hard-disabled.
- [ ] Proaktív lead/üzleti monitor: források, bizonytalanság, minőség és duplikáció mérése.
- [ ] Teljes lead→eredmény workflow állapotmodell, megszakítás/folytatás/idempotencia és E2E.
- [ ] Forrásolt, jogosultságkezelt memória; frissesség, bizonytalanság, retention/deletion és tény/következtetés elkülönítése.

### P2 – későbbi üzemeltetési javítások
- [ ] Storage/Auth/Realtime és projektkonfiguráció backup scope tisztázása.
- [ ] Main branch protection / required checks audit.
- [ ] Alacsony coverage modulok célzott tesztjei, kockázat alapján.

**Lezárási szabály:** a P0 minden pontja és a külső hatásokat érintő P1 pontok teljesüljenek; az új funkciók előfeltételéül szolgáló termék-alapok elfogadási tesztjei zöldek legyenek. P2 nem lehet ürügy a végtelen halasztásra. Ne ismételjük meg a már zöld CI/backup teszteket ok nélkül, és ne találjunk ki további kapukat a fenti feltételek teljesülése után.


## Nehézségi pontszámok és csoportosítás

1–10 skála: 1 könnyű, 10 nagyon nehéz. Az **5/10 alatti** feladatokat közös munkacsomagban végzem, a biztonságos függőségi sorrendet megtartva.

| Feladat | Nehézség |
|---|:---:|
| Production host/URL felderítése | **3/10** |
| SMTP hard-disable deploy és runtime ellenőrzés | **4/10** |
| Migration drift és PG17 replay | **6/10** |
| SQL review, pre/post-check, rollback terv | **4/10** |
| Audit/approval DB integráció és fail-closed | **7/10** |
| RPC write path, service_role lockdown | **7/10** |
| Auth/JWT/session/RLS smoke | **6/10** |
| Production app release és smoke | **6/10** |
| Provider idempotencia E2E | **8/10** |
| Proaktív üzleti monitor minőségmérése | **6/10** |
| Lead→eredmény workflow E2E | **7/10** |
| Forrásolt, jogosultságkezelt memória | **7/10** |
| Backup scope és branch protection felmérése | **2–5/10** |
| Célzott coverage javítás | **4/10** |

**Egy menetben végzendő alacsony nehézségűek:** host felderítése, SMTP kódbeli/workflow ellenőrzése (production deploy külön engedéllyel), SQL review előkészítése, backup scope felmérése, branch protection audit, indokolt célzott coverage. A magasabb nehézségű feladatok külön munkafázisban maradnak.

## 2026-11-25 – összevont alacsony nehézségű feladatok: eredmény

- **Host/URL (3/10):** a production JARVIS host nem azonosítható a repository és a rendelkezésre álló Railway-információ alapján. Streamlit projekt, de igazolt URL nincs.
- **SMTP (4/10):** kódban hard-disabled, korai guarddal; a küldő workflow outbound stepje letiltott. Production deploy/runtime még hiányzik.
- **SQL review (4/10):** a migration drift, PG17 replay, pre/post-check, adatmegőrzés és rollback checklist elkészült; független review nem.
- **Service-role teszt (4/10):** izolált PostgreSQL 17 + pgTAP tesztek sikeresek; productionben a service_role közvetlen DML továbbra is engedélyezett.
- **RLS/grant (3/10):** read-only audit kész; 8/8 tábla RLS-enabled, 0 policy; service_role DML true; anon/authenticated DML false.
- **Build/health/secrets (3/10):** ismert adatok dokumentálva; production hostspecifikus konfiguráció nincs.
- **Branch protection (2/10):** audit kész: `main.protected=false`, required checks enforcement `off`, repository rulesets nincs. A beállítás még nyitott.

A fenti vizsgálatok során production DB-írás, GRANT/REVOKE, deploy, secrets-módosítás és PR merge nem történt.

## Coverage-vezérelt következő javítás

A sikeres CI coverage artifact 90,75%-os összesített line coverage-et mutatott. A `task_actions.py` 81,4%-a indokolta a célzott edge tesztek hozzáadását a PR-hoz. A `scripts/supabase_auth_rls_smoke.py` 17,3%-a külön kezelendő, mert élő Auth/Supabase smoke script; a hiányzó sorok nagy része környezetfüggő, ezért izolált fake-client tesztelés szükséges. Az új task-actions tesztek CI eredménye még nincs igazolva.

## SQL migrációs kód előzetes statikus áttekintése

A `20261123093000`, `20261124130000`, `20261125150000`, `20261125160000` és `20261125170000` migrációk statikus olvasása alapján a fő biztonsági sorrend helyesnek tűnik: append-only audit trigger és hash-chain; trusted `app_metadata.role` alapú RLS; hashed, rövid életű approval; tranzakciós idempotens RPC; végső task DML revoke csak az RPC-enabled app deployja után. A migrációs lánc kódja nem módosult.

**Production előtti kötelező bizonyítékok:** (1) PostgreSQL 17 tiszta és production-shape replay; (2) security-definer függvények tényleges ownerének és EXECUTE-grantjeinek ellenőrzése; (3) párhuzamos azonos operation_id és token replay teszt; (4) audit insert/trigger hiba esetén task tranzakció rollback bizonyítása; (5) legacy logs sorok és settings kulcs/érték adatmegőrzés; (6) migration ledger drift explicit reconciliation. Ez az áttekintés nem helyettesít független SQL review-t és nem engedélyez production alkalmazást.


## PR #26 – frissített feladatállapot, 2026-11-25

A következő státuszok a PR #26 branchére vonatkoznak, nem a productionre és nem a main ágra. [PR #26](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26), commit `38693f2f93b790608aef37a33f190a86e611ff0d`.

1. **Approval race – kód és teszt beépítve, CI eredmény függőben.** A DB-szintű approval hash, principal/payload binding, expiry, atomikus consume és operation-ID lock/replay implementálva. Két párhuzamos PostgreSQL session teszteli az azonos operation ID-t.
2. **Task idempotencia – részben implementált.** A create/update/close műveletek RPC útvonalon futnak; az operation ledger a lezárt művelet eredményét tárolja. Külső szolgáltatók idempotenciája ettől külön feladat.
3. **Audit fail-closed – SQL teszt beépítve, CI eredmény függőben.** A végső audit append hibáját injektáló teszt azt várja el, hogy task, operation ledger és approval consume egy tranzakcióban rollbackelődjön.
4. **SMTP biztonság – kódban hard-disabled.** A DATA utáni bizonytalan kimenetel `send_unknown`, automatikus retry nem engedélyezett; a preflight/connect/auth hibák külön, ismert hibaként kezeltek. Production runtime proof nincs.
5. **Email idempotencia – belső kulcs megvan, provider garancia nincs.** Stabil lead+sequence operation ID kerül a küldési auditba; Gmail SMTP nem garantál provider oldali idempotency-t. API provider kiválasztása és E2E integráció nyitott.
6. **Migration drift – részben rendezett.** A két 20261117 ledger bejegyzés korábban egyeztetve; a 13 migration file-ból hét ledgerben, hat későbbi migration továbbra sincs productionben alkalmazva. A PG17 CI fixture teljes/replay és postcondition ellenőrzést tartalmaz.
7. **Service-role privilege lock – szándékosan blokkolt productionben.** A `20261125170000_enforce_atomic_task_write_privileges.sql` csak az RPC app deploy és sikeres production smoke után alkalmazható.

A dokumentáció frissítésekor a teljes CI két futása (`45689264377`, `45689247826`) még `in_progress` volt. A teszt státusza függőben; nem állítható, hogy zöld. A JARVIS host továbbra sem azonosított, a production adatbázis/deploy változatlan.
