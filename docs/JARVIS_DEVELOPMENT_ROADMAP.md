# JARVIS – elsődleges fejlesztési útiterv

**Ez a dokumentum a JARVIS fejlesztésének elsődleges iránytűje.** Minden új fejlesztési munkamenet elején ezt kell először elolvasni. A feladatokat az alábbi sorrendben kell végrehajtani; ettől csak a felhasználó kifejezett döntésével térjünk el.

## Alapelv

A JARVIS fokozatosan váljon megbízható, biztonságos és önállóbb üzleti asszisztenssé. Figyelhet, elemezhet, felismerhet lehetőségeket és javasolhat műveleteket, de külső vagy üzleti hatású végrehajtás csak megfelelő jogosultsággal és explicit jóváhagyással történhet.

## A fejlesztés öt egymásra épülő területe

### 1. Megbízhatóság és biztonság

Cél: a jelenlegi működés legyen kiszámítható, hibákkal és párhuzamos végrehajtással szemben ellenálló.

- Javítsuk ki a backup workflow importhibáját.
- Tegyük atomikussá az egyszer használatos jóváhagyások felhasználását, beleértve a konkurens kérések kezelését.
- Egészítsük ki a műveletek idempotenciáját: ismételt kérés vagy bizonytalan külső válasz ne okozzon duplikált feladatot vagy mellékhatást.
- Az érzékeny műveletek auditálása legyen fail-closed.
- A kimenő e-mail és más külső mellékhatások maradjanak tiltva, amíg a biztonságos idempotencia és a végponttól végpontig tesztek nem igazolják a működést.

**Lezárási feltétel:** a javítások regressziós és konkurenciatesztekkel igazoltak; a backup teljes friss futása sikeres, beleértve a mentés ellenőrzését és a visszaállítási próbát.

### 2. Supabase és jogosultságkezelés

Cél: az adatbázis állapota, a migrációs előzmények, az Auth és az RLS ellenőrizhetően összhangban legyenek.

- Térképezzük fel és rendezzük a repository és a production migration ledger/séma közötti eltéréseket.
- A migrációkat production-shape PostgreSQL 17 izolált környezetben játsszuk vissza, adatmegőrzési ellenőrzéssel.
- Teszteljük az Auth, session refresh, JWT, szerepkörök és RLS működését kizárólag már létező, engedélyezett izolált Supabase környezetben.
- Válasszuk szét a felhasználói JWT-alapú és a háttérfolyamatok service-role hozzáférését.
- Készítsünk bizonyítékokon alapuló éles átállási tervet, visszaállási tervvel és ellenőrzési kapukkal.

**Lezárási feltétel:** migrációs eltérésekre jóváhagyott, tesztelt rendezési terv; izolált Auth/JWT/RLS tesztek zöldek; dokumentált production cutover és rollback terv.

**Éles korlát:** production DDL/DML, migration push/repair, ledger-módosítás, GRANT/REVOKE, RLS/Auth módosítás és feature flag bekapcsolás külön, konkrét felhasználói jóváhagyás nélkül tilos. Az izolált tesztek nem jelentenek production engedélyt.

### 3. Önállóbb üzleti asszisztens

Cél: a JARVIS ne csak kérdésekre válaszoljon, hanem proaktívan támogassa az üzleti munkát.

- Figyelje a leadeket és a releváns üzleti változásokat.
- Ismerje fel és indokolja meg a lehetséges üzleti lehetőségeket.
- Készítsen javasolt feladatokat, prioritást és következő lépéseket.
- Mutassa meg a javaslatok forrását, bizonytalanságát és várható üzleti értékét.
- A feladatok és külső műveletek végrehajtása maradjon explicit jóváhagyáshoz kötött.

**Lezárási feltétel:** a proaktív javaslatok visszakövethetők, tesztelhetők, duplikációmentesek, és jóváhagyás nélkül nem váltanak ki tiltott mellékhatást.

### 4. Üzleti munkafolyamatok automatizálása

Cél: a különálló képességekből mérhető, végigkövethető üzleti folyamat álljon össze.

**Folyamat:** Leadkutatás → minősítés → stratégia → feladat → jóváhagyás → utánkövetés → eredménymérés.

- Minden lépésnek legyen egyértelmű bemenete, kimenete, állapota és felelőse.
- A folyamat legyen megszakítható, folytatható és idempotens.
- A jóváhagyási pontok legyenek láthatók; jóváhagyás nélkül ne történjen külső végrehajtás.
- Mérjük a leadminőséget, a konverziót, az utánkövetés eredményét és a végrehajtás sikerességét.

**Lezárási feltétel:** a teljes folyamat tesztelhető, auditálható, újraindítható és üzleti eredményekkel mérhető.

### 5. Tudás és hosszú távú memória

Cél: olyan tartós üzleti tudásréteg kialakítása, amely összekapcsolja a leadekről, ügyfelekről, interakciókról, döntésekről, feladatokról és eredményekről rendelkezésre álló információkat.

- Őrizze meg a releváns üzleti kontextust és annak forrását.
- Kapcsolja össze a korábbi döntéseket, végrehajtott lépéseket és azok eredményeit.
- Tegye visszakereshetővé a tanulságokat, és használja fel őket a későbbi javaslatok javítására.
- Kezelje az adatok frissességét, bizonytalanságát, hozzáférési jogosultságait és törlési/megőrzési szabályait.
- Ne tekintse a modell által generált következtetést ellenőrzött ténynek; különítse el a forrást, a tényt és a következtetést.

**Lezárási feltétel:** a tudás visszakereshető, forrásolt, jogosultságkezelt és mérhetően javítja a javaslatok minőségét.

## Haladáskövetés

**Frissítve:** 2026-11-25, `main` commit `71d6a1c` (PR #21 merge). A PR #20 javította az S3 ellenőrző Python-blokk behúzását. A main CI (`45655131500`) sikeres. A production backup workflow-dispatch (`45655512387`) teljesen sikeres: titkosított dump, S3 feltöltés, SSE-KMS és objektumméret ellenőrzés, letöltés, manifest/SHA-256 ellenőrzés, majd külön izolált PostgreSQL 17 restore és táblainventár/rekordszám-ellenőrzés. A restore külön runner-konténerben történt; production DB írás nem történt. [Backup futás](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45655512387).



A dokumentumot folyamatosan frissítsük; ne hozzunk létre párhuzamos, dátumozott roadmapeket.

| Sorrend | Terület | Státusz |
|---|---|---|
| 1 | Megbízhatóság és biztonság | Kódbeli alapok és izolált CI tesztek sikeresek; kimenő SMTP hard-disabled; production audit/RPC integráció és SMTP provider idempotencia még nincs igazolva |
| 2 | Supabase és jogosultságkezelés | Részben előkészítve – production drift friss read-only ellenőrzése, migrációs review, deploy és live smoke hátra van |
| 3 | Önállóbb üzleti asszisztens | Részben implementálva – proaktív monitor/lead és javaslati modulok vannak; minőségi és production bizonyíték hiányzik |
| 4 | Üzleti munkafolyamatok automatizálása | Részben implementálva – task/approval alapok megvannak; teljes E2E folyamat és üzleti mérés hátra van |
| 5 | Tudás és hosszú távú memória | Alapok implementálva – tartós memória és analitika létezik; forrásolt tudásgráf, lifecycle és minőségi mérés hátra van |

A státuszokat minden munkamenetben a tényleges kód, teszteredmény, CI-futás és – ahol releváns – engedélyezett integrációs bizonyíték alapján frissítsük. Egy feladat csak akkor tekinthető késznek, ha a lezárási feltétele teljesült. A „kódban implementált”, „automatikusan tesztelt”, „külső integrációval igazolt” és „productionben aktív” állapotokat mindig különböztessük meg.

## Munkamenet-szabály

1. Elsőként ezt az útitervet olvasd el.
2. Ezután olvasd el az `AGENTS.md`-t, a `README.md`-t és az aktuális feladathoz tartozó részletes dokumentációt.
3. A legkorábbi még nyitott területen dolgozz; ne ugorj későbbi pontra pusztán azért, mert az kényelmesebb.
4. Minden változtatás után futtasd a releváns teszteket, frissítsd a státuszt és az érintett részletes dokumentációt.
5. Production műveletet csak a dokumentált biztonsági kapuk és külön, konkrét jóváhagyás alapján végezz.

## Kapcsolódó részletes dokumentumok

- [AI fejlesztési útmutató](../AGENTS.md)
- [JARVIS képességei és architektúrája](JARVIS_DOCUMENTATION.md)
- [Production állapot és migrációs terv](PRODUCTION_STATE_AND_MIGRATION_PLAN.md)
- [Fejlesztési backlog](DEVELOPMENT_REVIEW_AND_RECOMMENDATIONS.md)
- [Production/release kapuk](REMAINING_WORK_AND_RELEASE_GATES.md)


**Friss audit – 2026-11-25, PR #21 után:** PR #21 merge commit `71d6a1c`; mindkét PR workflow minden jobja zöld. A production read-only snapshot továbbra is 5 ledger verziót, hiányzó 20261117 ledger-bejegyzéseket, nem létező `private` sémát, 8 policy nélküli RLS-es public táblát, legacy `logs` sémát, hiányzó `tasks.operation_id` mezőt és hiányzó audit/approval RPC objektumokat mutat. A CI izolált PostgreSQL 17-en ellenőrzi a migrációs láncot, de nem változtatja meg a production állapotot.

**Terület 1 – Megbízhatóság és biztonság friss minősítése:** a kódbeli approval/idempotencia, audit fail-closed és SMTP unknown-state megoldások regressziós/CI tesztekkel alátámasztottak; a production backup+restore sikeres. A terület még nem zárható le: production audit/approval RPC-k nincsenek telepítve, a production structured audit mezők hiányoznak, az SMTP-küldés PR #23-ban kódszinten és workflow-szinten letiltásra kerül; a provider oldali idempotencia nincs bizonyítva. E-mailküldés maradjon tiltva a külön validációig.


**Kimenő e-mail biztonsági állapot:** a PR #23 kódszintű `EMAIL_DELIVERY_ENABLED = False` tiltást vezet be, amely a runtime környezeti kapcsolóktól független. A scheduled outbound küldési lépés le van tiltva; a bejövő IMAP monitor külön marad. A kimenő e-mail csak külön biztonsági felülvizsgálat, provider idempotencia-igazolás és E2E teszt után engedélyezhető újra.


## Megbízhatóság és biztonság – 2026-11-25 frissítés

- SMTP hard-disable mainbe integrálva PR #23 squash merge-dzsel (`c1364e8aaf0741ba2c8ef33360799c744bf1b688`). Production deploy nem történt.
- Production read-only audit: 8/8 public tábla RLS enabled, 0 policy; anon/authenticated DML tiltva; service_role teljes DML engedélyezett. Private schema/task approval RPC hiányzik; ledger csak 5 20261119-es migrációt tartalmaz.
- Külső e-mail idempotencia továbbra sincs. SMTP nem hordoz natív idempotency key-t; ehhez API provider, stabil event-key és változatlan request body szükséges. Resend dokumentáltan támogat `Idempotency-Key` fejlécet azonos payload mellett 24 órán keresztül; a provider kiválasztása és hitelesítő adat/domain beállítása még hiányzik.

## ÚJ FUNKCIÓK ELŐTTI KÖTELEZŐ KAPU – 2026-11-25

A következő lista a roadmap sorrendjét egészíti ki. Új funkció csak akkor kezdhető, ha a P0/P1 biztonsági és production működési kapuk teljesültek. A PR #25 utáni main: `c5cf1ded6d5ee3ef5635ef5dbad743073bff73e1`; main CI `45663296144` mindkét jobja sikeres.

1. **Production app azonosítás és deploy:** az app URL/host jelenleg nem ismert; a repo nem tartalmaz deploy workflow-t, az elérhető Railway projekt nem JARVIS. Előbb a valódi Streamlit/egyéb hostot kell megtalálni, majd a main SMTP hard-disable változását oda deployolni és runtime-ban ellenőrizni.
2. **Migration drift és DB biztonság:** rendezni kell a két 20261117 ledger eltérést; teljes PG17 replay és adatmegőrzés; audit/approval/private schema/RPC hiányzó objektumok migrációja; SQL review, pre/post-check és rollback terv.
3. **Task atomicity és jogosultság:** RPC app deploy + smoke, majd a service_role közvetlen task DML tiltása; pozitív RPC és negatív direkt DML ellenőrzés.
4. **Audit fail-closed és Auth/RLS:** minden érzékeny útvonal audit-hibára álljon le; JWT/session/role/RLS tesztek izolált, engedélyezett környezetben. Production Auth/RBAC külön jóváhagyás.
5. **Külső hatások idempotenciája:** e-mail provider kiválasztása után stabil idempotency key, tartós payload és provider ID, bizonytalan válasz és retry teszt. SMTP addig hard-disabled.
6. **App release bizonyíték:** production health check, DB/RPC/task/approval/audit smoke és rollback ellenőrzés.
7. **Alapvető termékfolyamatok:** lead→minősítés→stratégia→task→approval→follow-up→eredménymérés E2E; proaktív javaslatok forrás/uncertainty/duplikáció minőségmérése; jogosultságkezelt, forrásolt memória és adat-életciklus.

A nem blokkoló P2 feladatok (platform backup scope, branch protection felülvizsgálat, alacsony kockázatú coverage bővítés) maradhatnak a backlogban. Ne adjunk hozzá újabb ellenőrzéseket, ha a fenti elfogadási feltételek teljesültek.


## Nehézségi becslés a nyitott előfeltételekre

A skála 1–10: 1 könnyű, 10 nagyon nehéz. Az 5/10 alatti feladatokat közös munkacsomagban végzem; az összetettebbeket külön, függőségi sorrendben.

| Előfeltétel | Nehézség |
|---|:---:|
| Production host/URL felderítése | **3/10** |
| SMTP hard-disable élesítése és runtime igazolása | **4/10** |
| Migration drift és teljes PG17 replay | **6/10** |
| SQL review és rollback terv | **4/10** |
| Audit/approval/private schema/RPC production integráció | **7/10** |
| Task RPC deploy és service_role lockdown | **7/10** |
| Auth/JWT/session/RLS tesztek | **6/10** |
| Provider idempotencia és E2E | **8/10** |
| Production app release és smoke | **6/10** |
| Üzleti workflow és E2E | **7/10** |
| Forrásolt memória és adat-életciklus | **7/10** |
| Branch protection és backup scope felmérése | **2–5/10** |

Az alacsonyabb nehézségű feladatokat összevonom, de az éles deployt, jogosultságmódosítást és adatbázis-migrációt nem hajtom végre pusztán azért, mert a becsült nehézség alacsony.

## 2026-11-25 – az összevont alacsony nehézségű ellenőrzési kör eredménye

A következő ellenőrzések közös munkacsomagban lefutottak:
- SMTP hard-disable: kódban és workflow-ban ellenőrizve; production deploy/runtime bizonyíték hiányzik.
- Service-role negatív teszt: izolált PostgreSQL 17 + pgTAP CI sikeres; productionben a közvetlen task DML jog továbbra is aktív, ezért éles negatív DML teszt csak lockdown után.
- RLS/grant: 8 public tábla RLS-enabled, 0 policy; service_role DML engedélyezett, anon/authenticated DML tiltott.
- Build/health/secrets: Python 3.11, Streamlit indítási parancs és `health_check.run_self_diagnostics()` dokumentálva; production host ismeretlen.
- GitHub branch protection: main nem védett, required checks enforcement off, rulesets nincs.
- SQL review: előfeltétel- és ellenőrzőlista előkészítve, független review még szükséges.

**Következő sorrend:** JARVIS host azonosítása → SMTP deploy bizonyítéka → SQL/migrációs review és PG17 replay → audit/approval RPC és task write path deploy → csak utána production task DML lockdown → production smoke. A main branch protection beállítása külön, alacsony kockázatú üzemeltetési javítás, de a tényleges beállítás előtt ellenőrizni kell a required workflow check neveket.



## Aktuális állapotfrissítés – 2026-11-25, PR #26

**Fejlesztési ág:** `docs/pre-feature-readiness-gates` · **PR:** [#26](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26) · **aktuális PR-head:** `eaad5428311d86590f03c744f7f5b0e02da45064`. A kód- és tesztváltozások CI-vel igazolt commitja: `38693f2f93b790608aef37a33f190a86e611ff0d`.

A PR #26-ban a korábban nyitott biztonsági munka több kódbeli és tesztelési eleme elkészült:
- DB-szintű, rövid életű, principal- és payload-kötött approval token; atomikus consume a task végrehajtással együtt.
- Operation ID-val védett task műveleti RPC; azonos művelet replay-je tárolt eredményt ad vissza.
- Approval replay/revoke, audit fail-closed rollback és két párhuzamos végrehajtás SQL-tesztje bekerült a PostgreSQL 17 CI-be.
- SMTP kimenő küldés hard-disabled; az SMTP DATA utáni bizonytalan eredmény `send_unknown` állapotú és nem kerül automatikus retry-ra. Stabil belső email operation ID van, de Gmail SMTP provider-oldali idempotenciát nem garantál.
- A service-role task DML lockdown migrációja és negatív tesztje izolált CI-ben szerepel; productionre továbbra is blokkolt, amíg az RPC app path nincs deployolva és smoke-tested.

**CI eredmény:** a `38693f2` kódcommiton a `45689264377` mindkét jobja (`test`, `backup-restore-integration`) sikeres. A párhuzamos `45689247826` futást a GitHub concurrency szabálya megszakította. A későbbi dokumentációs commitok után indult futások is megszakadtak; az aktuális PR-head dokumentációs módosításaira külön teljes CI-eredmény még nincs. Kövesd a [CI futásokat](https://github.com/tamaszsolt2005-hub/jarvis-core/actions).

**Production továbbra is változatlan:** a korábbi read-only snapshot szerint a két 20261117 ledger-egyeztetés után hét történeti verzió szerepel a ledgerben; hat újabb migráció (köztük az audit/RBAC/task approval és végső privilege lock) nincs alkalmazva. Az új PR-kód/izolált teszt nem bizonyít production telepítést. A JARVIS host továbbra sincs igazolva; a hozzáférhető Railway projekt nem JARVIS. Nincs production deploy, migráció, GRANT/REVOKE, Auth flag aktiválás vagy PR merge.

**Az első terület állapota:** a megbízhatósági és biztonsági kódmunka nagyrészt implementálva, de a CI végső eredménye, production RPC/app rollout, provider-oldali email idempotencia és runtime SMTP hard-disable proof még hiányzik. Ezért az 1. terület még nem zárható le, és a teljes JARVIS sem minősíthető késznek.
