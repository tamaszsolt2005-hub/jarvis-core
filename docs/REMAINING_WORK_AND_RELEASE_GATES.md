# JARVIS – production és release gate-ek

Ez a dokumentum csak azt határozza meg, mi kell egy production változtatás vagy élesítés előtt. A fejlesztési teendők a [fejlesztési backlogban](DEVELOPMENT_REVIEW_AND_RECOMMENDATIONS.md) vannak.

## Jelenlegi döntési állapot

**Production Auth/RBAC: OFF. Production migráció: blokkolt. Production deploy: nincs jóváhagyva. A produkciós logikai backup és izolált PostgreSQL 17 restore 2026-11-25-én igazoltan sikeres.**

A `main` aktuális commitja `71d6a1cdc755607a9598bf9b2c19c50730f5e036` (PR #21 squash merge). A PR #21 két workflow minden jobja sikeres. Ez kódintegráció, nem production release.

## Kötelező kapuk

**2026-11-25 friss bizonyíték:** [backup+restore workflow #45655512387](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45655512387) minden lépése sikeres. A mentés ellenőrzési kapuja teljesült; a többi kapu ettől függetlenül nyitott.


### 1. Repository és CI
- [x] A pontos main commit (`2e2a97e`) CI-je befejezett és sikeres (`45655131500`).
- [x] A backup workflow teljes, friss futása sikeres (`45655512387`): dump, age titkosítás, S3 feltöltés, SSE-KMS/KMS key ellenőrzés, letöltés, visszafejtés és manifest SHA-256 ellenőrzés.
- [x] A tényleges production archívum külön, izolált PostgreSQL 17 konténerbe restore-olása sikeres; 8 public tábla és kijelölt rekordszámok ellenőrizve.
- A sikertelen vagy futó workflow nem tekinthető sikeresnek.

### 2. Migration drift
- Friss read-only production schema és remote ledger snapshot készült.
- A két 20261117 verzió ledger-eltérése dokumentáltan és függetlenül rendezett.
- Az öt visszanyert történeti migráció és a repository migrációk tartalma/postconditionjei ellenőrzöttek.
- A teljes migrációs sorrend production-shape izolált PostgreSQL 17 környezetben sikeres.
- A pontos SQL-készletet független review és külön, konkrét production jóváhagyás fedi.

### 3. Auth/RLS
- A live Auth/JWT/RLS smoke csak már létező, kifejezetten engedélyezett izolált Supabase környezetben sikeres.
- Admin Auth user, szerepkörök, session refresh, invalid/lejárt token és admin/operator/reader jogosultságok ellenőrzöttek.
- A production RLS/GRANT utófeltételek és visszaellenőrző lekérdezések előre definiáltak.
- Auth/RBAC flag csak a migráció után, külön jóváhagyással kapcsolható be.

### 4. Üzemeltetés
- RPO/RTO, retention, riasztás, kulcsrotáció, hozzáférés és incidenskezelés dokumentált.
- Restore runbook és felelősök kijelölve.
- A logikai DB backup határain túli igények (Storage objektumok, Auth/Realtime platformadatok, projektkonfiguráció) kezelése tisztázott.

## Kifejezetten tiltott külön jóváhagyás nélkül

- Production DDL/DML és adatírás.
- `supabase db push`, `supabase migration repair`, migration ledger kézi átírása.
- GRANT/REVOKE, RLS policy és Auth user módosítás.
- Production Auth/RBAC feature flag bekapcsolása.
- AWS production deploy vagy backup infrastruktúra változtatása.
- Új Supabase projekt vagy branch létrehozása.

A backup sikeres, de ez nem jelenti a Supabase migration drift vagy az élesítés lezárását. A production állapot részletes, időponthoz kötött tényállása: [Production állapot és migrációs terv](PRODUCTION_STATE_AND_MIGRATION_PLAN.md).


## Friss audit és CI állapot – 2026-11-25

- PR #21 squash merge-elve: main commit `71d6a1cdc755607a9598bf9b2c19c50730f5e036`.
- Mindkét PR #21 workflow minden jobja sikeres: [45656372633](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45656372633), [45656331519](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45656331519).
- A production read-only audit szerint a `private` schema, a structured logs mezők, a `tasks.operation_id`, az audit-chain state, a private approval táblák és a task/approval RPC-k hiányoznak. Nyolc public tábla RLS-enabled, de policy nélküli; a remote ledger 5 migrációt tartalmaz, a két 20261117 verzió hiányzik.
- A két 20261117 migráció sémabeli hatása látható (`leads.website`, `logs.level`), de a ledger eltérése nincs rendezve. A CI fixture ezt modellezi és teszteli, nem javítja a production ledgert.
- A kimenő SMTP-küldés a PR #23 kódmódosításával hard-disabled: az `EMAIL_DELIVERY_ENABLED` konstans `False`, nem környezeti változóból származik; a közvetlen küldő API Auth/DB/secret elérés előtt leáll, a scheduled outbound workflow-lépés `if: false`. A bejövő IMAP monitor külön működhet. SMTP provider idempotencia és live E2E továbbra sincs igazolva; újraengedélyezés külön review-hoz kötött.
- A production DDL/DML, migration repair, grants, RLS, Auth provisioning és deploy továbbra is tiltott külön jóváhagyás nélkül.

A release gate-ek **nem teljesültek** pusztán attól, hogy a PR CI zöld: előbb drift-egyeztetés, teljes PG17 replay, SQL review, külön production jóváhagyás, majd deploy és RPC smoke szükséges.


A PR #23 kimenő e-mailt letiltó kódmódosítása után az SMTP-küldés nem aktiválható GitHub secret vagy runtime környezeti változó átállításával. Ez csak a PR merge és a CI sikeres lezárása után tekinthető a main ágban érvényesnek.


## 2026-11-25 17:06 UTC – friss audit és main állapot

- PR #23 SMTP hard-disable merge-elve a mainbe: `c1364e8aaf0741ba2c8ef33360799c744bf1b688`. Merge utáni main CI `45661201562`: backup–restore sikeres, test job futott az utolsó ellenőrzéskor.
- Production read-only: 8/8 public táblán RLS enabled, 0 policy; anon/authenticated közvetlen DML jog false; service_role teljes DML true. Private schema, audit chain state, approval táblák és task RPC hiányoznak; tasks.operation_id hiányzik; migration ledger 5 (20261119). Advisor 8 INFO policy nélküli RLS miatt.
- SMTP main kódban hard-disabled, de production runtime deploy nem történt. Secrets nem módosultak, e-mail nem ment ki.
- Production migráció, ledger repair, GRANT/REVOKE, Auth provisioning és deploy továbbra is blokkolt külön jóváhagyásig.

## ÚJ FUNKCIÓK ELŐTTI KÉSZÜLTSÉGI KAPU – 2026-11-25

A dokumentum célja egyértelmű: mi az a véges, ellenőrizhető munka, amely nélkül új JARVIS funkció nem kezdhető. A PR #25 utáni `main` commit: `c5cf1ded6d5ee3ef5635ef5dbad743073bff73e1`; a main CI `45663296144` mindkét jobja sikeres.

### Kötelező P0/P1 lista
- [ ] **Production célpont:** a tényleges JARVIS app host és URL azonosítása. Repo-ban nincs deploy workflow/app URL; a hozzáférhető Railway projekt VolleyForm, nem JARVIS. Ismeretlen célpontra deploy tilos.
- [ ] **SMTP hard-disable élesítése:** mainből a valós production appba deploy, majd runtime bizonyíték, hogy semmilyen outbound SMTP útvonal nem küld. Addig a kimenő küldés tiltott.
- [ ] **Production schema/ledger drift:** a két 20261117 hiányzó ledger bejegyzés reconciliációja; teljes migration lánc PG17 replay és adatmegőrzés; productionben hiányzó audit/approval objektumok migrációs csomagja.
- [ ] **SQL review és engedélyezés:** független review, pre/post-check és rollback terv; production DDL/DML/ledger/grants/RLS/Auth művelet kizárólag külön konkrét jóváhagyás után.
- [ ] **Audit és approval:** structured audit/hash chain, `private.task_approvals`, `private.task_action_operations`, `tasks.operation_id`, `execute_approved_task_action` és kapcsolódó RPC-k production működése; audit hiba fail-closed minden érzékeny útvonalon.
- [ ] **Task jogosultság:** RPC-alapú alkalmazás deploy + smoke; csak utána a `20261125170000` service_role közvetlen task DML lockdown; utána pozitív RPC és negatív direkt DML teszt.
- [ ] **Auth/JWT/RLS:** live smoke már létező, engedélyezett izolált Supabase környezetben; expired/invalid JWT, session refresh és role negatív esetek. Production Auth/RBAC külön jóváhagyás.
- [ ] **Provider idempotencia:** külső provider kiválasztása (még nincs döntés), stabil idempotency key, request payload stabilitás, provider ID mentés, `unknown` kezelés, retry határ és E2E. SMTP hard-disable marad.
- [ ] **Production alkalmazás ellenőrzés:** deploy után health check, DB/RPC/audit/task/approval smoke és rollback útvonal.

### P2 – nem blokkolja önmagában az új funkciók specifikációját
- [ ] Storage/Auth/Realtime és projektkonfiguráció backup scope tisztázása a már sikeres PostgreSQL logikai backupon túl.
- [ ] Main branch protection / required checks állapotának ellenőrzése.
- [ ] Alacsony coverage modulok célzott tesztjei, csak ahol a kockázat indokolja.

### Jelenlegi production tényállás
- 8/8 public tábla RLS-enabled, 0 policy; anon/authenticated DML grant tiltása igazolt; service_role teljes DML joga megvan.
- `private` schema, audit-chain state, approval/operation táblák, `tasks.operation_id` és task RPC hiányzik.
- Migration ledger 5 darab 20261119-es bejegyzést tartalmaz; a két 20261117 sémahatás jelen van, ledger bejegyzés hiányzik.
- Production deploy, DDL/DML, ledger repair, GRANT/REVOKE és Auth provisioning nem történt.
- Backup+restore sikeres; ez nem pótolja a migration/release kapukat.

**Nem szabad összekeverni:** a zöld CI, a mainben lévő kód, a production DB séma és a futó production app négy külön állapot. Mindegyikhez saját bizonyíték szükséges.


## Feladatonkénti nehézség és végrehajtási csoportosítás

Skála: **1 = könnyű, 10 = nagyon nehéz**; becslés, nem időígéret. Az **5/10 alatti** pontokat közös munkacsomagban végzem, a függőségek betartásával. Az 5/10-es és magasabb feladatok külön, sorrendben haladnak. Production változtatás csak külön konkrét jóváhagyással.

| Feladat | Nehézség |
|---|:---:|
| Production host/URL felderítése | **3/10** |
| SMTP hard-disable deploy és runtime ellenőrzés | **4/10** |
| Schema/ledger drift, migrációs replay és adatmegőrzés | **6/10** |
| SQL review, pre/post-check és rollback terv | **4/10** |
| Audit/approval DB objektumok és fail-closed működés | **7/10** |
| RPC task write path deploy, majd service_role lockdown és teszt | **7/10** |
| Auth/JWT/RLS élő smoke | **6/10** |
| Provider kiválasztás és idempotencia E2E | **8/10** |
| Production alkalmazás health/smoke/rollback ellenőrzés | **6/10** |
| Storage/Auth/Realtime backup scope | **5/10** |
| Main branch protection / required checks | **2/10** |
| Célzott coverage javítás | **4/10** |

**Közös, 5/10 alatti munkacsomag:** host/URL felderítés, SMTP kódbeli és workflow ellenőrzés (deploy külön jóváhagyással), SQL review előkészítő ellenőrzőlista, backup scope felmérés, branch protection audit és indokolt célzott coverage. A migrációs replay, DB security és provider-integráció nem kerül ebbe az összevont csomagba, mert nagyobb kockázatú és függőségei vannak.

## Frissített állapot a 2026-11-25-i összevont alacsony-nehezségű audit után

A 7 feladatból több csak részben zárható le: a kódszintű ellenőrzés és izolált teszt nem helyettesíti a production deployt vagy a production jogosultságváltozást.

### Lezárt ellenőrzések
- [x] SMTP hard-disable kódbeli és workflow-szintű ellenőrzése: konstans `False`, korai fail-closed guard, outbound workflow step letiltva.
- [x] Service-role task jogosultsági teszt izolált PostgreSQL 17 + pgTAP CI-ben: sikeres.
- [x] RLS/grant read-only felülvizsgálat: 8/8 public tábla RLS-enabled; 0 policy; service_role DML true; anon/authenticated DML tiltás igazolt.
- [x] Ismert build/secret/health-check adatok dokumentálása: Python 3.11, Streamlit indítóparancs, health self-diagnostics és secretnevek (értékek nélkül).
- [x] GitHub main branch protection audit: `protected=false`, required checks enforcement `off`, repository rulesets nincs.

### Továbbra is nyitott feladatok
- [ ] A valódi JARVIS production host/URL azonosítása; hosthoz kötött környezeti konfiguráció és futó példány ellenőrzése.
- [ ] SMTP hard-disable deploy a tényleges production appba és runtime bizonyíték.
- [ ] Független SQL review, migrációs pre/post-checkek és rollback/recovery terv jóváhagyása.
- [ ] Két 20261117 migration-ledger eltérés reconciliation terve és jóváhagyása.
- [ ] Teljes production-shape PostgreSQL 17 migration replay, adatmegőrzés és migrációs postconditionök.
- [ ] Productionben hiányzó private schema, audit/hash-chain, approval/operation táblák és RPC-k migrációs csomagjának véglegesítése.
- [ ] Audit fail-closed útvonal-leltár és minden érzékeny művelet negatív tesztje.
- [ ] Task RPC write path alkalmazás deployja és smoke tesztje; csak utána külön jóváhagyott service_role task DML lockdown.
- [ ] Lockdown után production negatív direct-DML és pozitív RPC teszt; jelenleg productionben service_role DML még engedélyezett.
- [ ] Live Auth/JWT/session/RLS/role smoke engedélyezett izolált Supabase környezetben.
- [ ] Production migrációk szakaszos alkalmazása külön konkrét jóváhagyás után.
- [ ] Production app deploy, health check, DB/RPC/task/approval/audit smoke és rollback ellenőrzés.
- [ ] Storage/Auth/Realtime/platform backup scope tisztázása a már sikeres PostgreSQL backup/restore mellett.
- [ ] Main branch protection és required checks beállítása, majd újraellenőrzése.
- [ ] Külső e-mail provider kiválasztása és idempotens API-integráció E2E tesztekkel; SMTP maradjon hard-disabled.
- [ ] Proaktív lead/üzleti monitor forrás-, minőség-, bizonytalanság- és duplikációmérése.
- [ ] Leadkutatás→minősítés→stratégia→task→approval→utánkövetés→eredménymérés E2E workflow.
- [ ] Forrásolt, jogosultságkezelt memória: frissesség, bizonytalanság, retention/deletion és tény/következtetés elkülönítése.
- [ ] Jóváhagyás nélküli külső/üzleti hatású végrehajtás kizárásának negatív tesztjei.
- [ ] Kockázat alapján célzott coverage javítás.

A hét feladat közül az URL felderítése továbbra sem sikerült, az SMTP csak kódszinten igazolt, a SQL review elő van készítve, a service-role teszt csak izolált CI-ben zöld, a branch protection audit eredménye pedig azt mutatja, hogy a main jelenleg nincs védve.

## Új coverage ellenőrzési eredmény

A CI coverage artifact összesített line coverage-e 90,75% (3729/4109). A `task_actions.py` 81,4%-on állt, ezért célzott edge tesztek kerültek a PR-ba: hibás parser bemenetek, tiltott payload mezők, approval validáció, hibás RPC válaszok és singleton lista válasz. Az új tesztek CI-eredménye még függőben van.

A `scripts/supabase_auth_rls_smoke.py` 17,3%-os coverage-e nem tekinthető önmagában kódminőségi hibának: ez élő Supabase/Auth integrációs smoke script, amelyhez elkülönített tesztprojekt és érvényes Auth konfiguráció szükséges. Később izolált fake-client/contract tesztekkel érdemes lefedni, nem production hívásokkal.

## SQL migrációs kód előzetes statikus áttekintése

A `20261123093000`, `20261124130000`, `20261125150000`, `20261125160000` és `20261125170000` migrációk statikus olvasása alapján a fő biztonsági sorrend helyesnek tűnik: append-only audit trigger és hash-chain; trusted `app_metadata.role` alapú RLS; hashed, rövid életű approval; tranzakciós idempotens RPC; végső task DML revoke csak az RPC-enabled app deployja után. A migrációs lánc kódja nem módosult.

**Production előtti kötelező bizonyítékok:** (1) PostgreSQL 17 tiszta és production-shape replay; (2) security-definer függvények tényleges ownerének és EXECUTE-grantjeinek ellenőrzése; (3) párhuzamos azonos operation_id és token replay teszt; (4) audit insert/trigger hiba esetén task tranzakció rollback bizonyítása; (5) legacy logs sorok és settings kulcs/érték adatmegőrzés; (6) migration ledger drift explicit reconciliation. Ez az áttekintés nem helyettesít független SQL review-t és nem engedélyez production alkalmazást.
