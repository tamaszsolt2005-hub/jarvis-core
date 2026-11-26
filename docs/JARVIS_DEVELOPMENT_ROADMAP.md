# JARVIS – elsődleges fejlesztési útiterv

> **Aktuális munkamód – 2026-11-26:** a JARVIS alkalmazás nincs telepítve; helyi Streamlit dashboardból fejlesztjük. A PR #26 nyitott, nem merge-ölt, a PR mindenkori aktuális headje és checkjei a [GitHub PR-oldalon](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26) követhetők; a 2026-11-26-i ellenőrzéskor a teszt, backup/restore, CodeQL és pip-audit checkek sikeresek voltak. A cégazonosítási `upsert_company_lead` RPC és a két-session concurrency teszt elkészült. A production host felderítése és a production release gate-ek nem blokkolják a helyi funkciófejlesztést. Az aktuális állapot részletei: [CURRENT_STATE_AND_NEXT_STEPS.md](CURRENT_STATE_AND_NEXT_STEPS.md).


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
| 3 | Önállóbb üzleti asszisztens | Részben implementálva – forrásolt leadprioritás és belső következőlépés-javaslat már össze van kapcsolva; proaktív minőségmérés és production bizonyíték hátra van |
| 4 | Üzleti munkafolyamatok automatizálása | Első read-only lépés elkészült: leadkutatás → bizonyíték-alapú triázs → belső task-javaslat; task lead-kapcsolat, approval-integráció, follow-up állapotgép és eredménymérés még hátra van |
| 5 | Tudás és hosszú távú memória | Alapok implementálva – tartós memória és analitika létezik; forrásolt tudásgráf, lifecycle és minőségi mérés hátra van |

A státuszokat minden munkamenetben a tényleges kód, teszteredmény, CI-futás és – ahol releváns – engedélyezett integrációs bizonyíték alapján frissítsük. Egy feladat csak akkor tekinthető késznek, ha a lezárási feltétele teljesült. A „kódban implementált”, „automatikusan tesztelt”, „külső integrációval igazolt” és „productionben aktív” állapotokat mindig különböztessük meg.

## 2026-11-26 – első lead-to-task workflow szelet

A PR #26 branchben elkészült a `lead_workflow.py` read-only ajánlásépítő modul, és bekerült a napi vezetői briefingbe.

- A modul kizárólag strukturált, saját leadkutatásból származó adatot értékel; a manuális jegyzetet nem kezeli kutatási bizonyítékként.
- A meglévő üzleti illeszkedési pontszámot, bizonyosságot és nyilvános bizonyítékok számát egy következő belső ellenőrzési feladatjavaslattá alakítja.
- A gyenge bizonyosság vagy kevés bizonyíték további kutatást javasol, nem magas prioritású üzleti végrehajtást.
- Ha a leadhez már kapcsolódik task, nem készít ismételt első lépésű javaslatot.
- A javaslat leadazonosítót, feladatcímet, prioritást és indoklást tartalmaz; adatbázisba nem ír, jóváhagyást nem fogyaszt, e-mailt nem küld és kapcsolatfelvételi engedélyt nem ad.

**Minősítés:** kódban implementált; az új célzott tesztek hozzáadva; GitHub CI futás a legfrissebb PR-headen még ellenőrizendő. Ez még nem a teljes workflow. Következő fejlesztési szelet: a feladatművelet biztonságos lead-kapcsolata és jóváhagyási útvonala, majd a follow-up állapotok és eredménymérés.

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

A következő lista a roadmap sorrendjét egészíti ki. Ez a korábbi szabály a production release-re vonatkozott, és nem alkalmazható a jelenlegi helyi fejlesztési szakaszra. Helyi funkciófejlesztés folytatható; a P0/P1 production kapuk kizárólag éles deploy, production adatbázis-/jogosultság-változtatás vagy külső mellékhatás előtt kötelezők. A PR #25 utáni main: `c5cf1ded6d5ee3ef5635ef5dbad743073bff73e1`; main CI `45663296144` mindkét jobja sikeres.

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

**Fejlesztési ág:** `docs/pre-feature-readiness-gates` · **PR:** [#26](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26) · **aktuális PR-head:** `a korábbi státuszfelvételkor aktuális PR-head (történeti adat; a friss állapotot a dokumentum legutolsó 2026-11-26-i blokkja rögzíti)`. A kód- és tesztváltozások CI-vel igazolt commitja: `38693f2f93b790608aef37a33f190a86e611ff0d`.

A PR #26-ban a korábban nyitott biztonsági munka több kódbeli és tesztelési eleme elkészült:
- DB-szintű, rövid életű, principal- és payload-kötött approval token; atomikus consume a task végrehajtással együtt.
- Operation ID-val védett task műveleti RPC; azonos művelet replay-je tárolt eredményt ad vissza.
- Approval replay/revoke, audit fail-closed rollback és két párhuzamos végrehajtás SQL-tesztje bekerült a PostgreSQL 17 CI-be.
- SMTP kimenő küldés hard-disabled; az SMTP DATA utáni bizonytalan eredmény `send_unknown` állapotú és nem kerül automatikus retry-ra. Stabil belső email operation ID van, de Gmail SMTP provider-oldali idempotenciát nem garantál.
- A service-role task DML lockdown migrációja és negatív tesztje izolált CI-ben szerepel; productionre továbbra is blokkolt, amíg az RPC app path nincs deployolva és smoke-tested.

**CI eredmény:** a `38693f2` kódcommiton a `45689264377` mindkét jobja (`test`, `backup-restore-integration`) sikeres. A párhuzamos `45689247826` futást a GitHub concurrency szabálya megszakította. A későbbi dokumentációs commitok után indult futások is megszakadtak; az aktuális PR-head dokumentációs módosításaira külön teljes CI-eredmény még nincs. Kövesd a [CI futásokat](https://github.com/tamaszsolt2005-hub/jarvis-core/actions).

**Production továbbra is változatlan:** a korábbi read-only snapshot szerint a két 20261117 ledger-egyeztetés után hét történeti verzió szerepel a ledgerben; hat újabb migráció (köztük az audit/RBAC/task approval és végső privilege lock) nincs alkalmazva. Az új PR-kód/izolált teszt nem bizonyít production telepítést. A JARVIS host továbbra sincs igazolva; a hozzáférhető Railway projekt nem JARVIS. Nincs production deploy, migráció, GRANT/REVOKE, Auth flag aktiválás vagy PR merge.

**Az első terület állapota:** a megbízhatósági és biztonsági kódmunka nagyrészt implementálva, de a CI végső eredménye, production RPC/app rollout, provider-oldali email idempotencia és runtime SMTP hard-disable proof még hiányzik. Ezért az 1. terület még nem zárható le, és a teljes JARVIS sem minősíthető késznek.


## Aktuális ellenőrzött állapot – 2026-11-25, PR #26

A korábbi PR #26 állapotbekezdések a friss ellenőrzés előtti pillanatképek; az alábbi állapot az irányadó.

- **PR:** [#26](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26), nyitott, nem merge-ölt.
- **Teljesen ellenőrzött CI/CodeQL/audit commit:** `7c8e6970a733884f4423821cddf3731f58e5b392`. Az ezt követő commitok dokumentációs javítások; új workflow-eredmény még nincs visszaigazolva. A PR mindenkori headje a [PR #26](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26) oldalon látható.
- **JARVIS CI:** a `test` és `backup-restore-integration` job sikeres.
- **CodeQL:** az `Analyze Python` job és annak elemzési lépése sikeres.
- **Függőség-audit:** a `pip-audit` sikeres a `requirements-test.txt` fájlon, amely a runtime függőségeket is behúzza.
- **Dependabot:** heti Python- és GitHub Actions-frissítési konfiguráció bekerült a repóba.

**E-mail állapot:** a kiválasztott provider Gmail SMTP (`EMAIL_PROVIDER=smtp`); a secretnevek meglétét ellenőrizték, de a credential értékek és az SMTP kapcsolat nincsenek validálva. A küldés továbbra is hard-disabled. A Resend adapter alternatívaként a kódban marad, nem az aktív küldési út.

**Az öt fejlesztési terület státusza nem változik attól, hogy a CI zöld:** a megbízhatósági és biztonsági kódmunka jelentősen előrehaladt, de production RPC/app rollout, migration drift rendezés, jogosultság- és Auth/RLS-validáció, valamint a termékfolyamatok E2E bizonyítása nyitott. Production módosítás nem történt.



## Ellenőrzött állapotfrissítés – 2026-11-26, PR #26

**Ez a blokk felülírja a dokumentum korábbi, 2026-11-25-i CI/head pillanatképeit.** A PR #26 nyitott, nincs merge-ölve. Az ellenőrzés kiinduló headje: `6ef4020bba3949e02440e97583fc907b6bcb1f00`.

- JARVIS CI: sikeres; **838 passed, 3 skipped, 0 failed**, teljes coverage **91.29%** (80% minimum).
- PostgreSQL 17 backup/restore és izolált migrációs/pgTAP integráció: sikeres.
- CodeQL Python elemzés: sikeres.
- pip-audit runtime és tesztfüggőségek: sikeres.
- A PR leírását ehhez az eredményhez igazítottuk.

### Global lead research – párhuzamos duplikáció audit

A `global_lead_research.py` az adatbázis meglévő cégneveit és webdomainjeit 1000-es offset-oldalakban tölti be, majd az aktuális kutatási futás során memóriában bővíti a deduplikációs halmazokat. Ez ugyanazon folyamaton belüli, már beolvasott adatokra jó szűrő, de **nem atomikus adatbázis-szintű egyediség**:

1. Két worker ugyanazt a snapshotot olvashatja be, majd mindkettő beszúrhatja ugyanazt az új céget.
2. Az offset pagination nem ad garantált, egyetlen MVCC snapshotot; párhuzamos beszúrások közben rekordok eltolódhatnak oldalak között. Az `.order("id")` stabil sorrendet ad, de nem oldja meg a konkurens írások miatti konzisztenciát.
3. A cégnév normalizált unique indexe legitim névazonosságokat ütköztetne; a domain-indexhez pedig a webhely-normalizálás és a közös/átirányított domainek szabályait előbb üzletileg és technikailag definiálni kell.
4. A CSV email import külön adatbázis unique indexszel védett; ez nem véd a cég/domain alapú kutatási duplikáció ellen.

**Állapotkorrekció – 2026-11-26:** a korábbi, csak alkalmazásszintű global research race kockázatot a PR #26 közös, tranzakciós `upsert_company_lead` RPC-je kezeli. A `global_lead_research.py` és a `lead_gen.py` ugyanazt az RPC-t használja; a két-session PostgreSQL race teszt és a teljes CI sikeres. A konkurens cégclaim fejlesztési feladata lezárható. Production migráció/deploy nem történt.

### Friss munkasorrend

1. A helyi dashboard fő funkcióútvonalainak integrációs/hibakezelési ellenőrzése.
2. A helyi konfiguráció, szerveroldali titkok és későbbi host-konfiguráció határainak tisztázása.
3. A scheduler/worker folyamatok dashboardtól független futtatási modelljének előkészítése.
4. A következő felhasználó által priorizált funkció fejlesztése a roadmap öt területe szerint.
5. E-mail küldés továbbra is hard-disabled; provider live E2E és külön jóváhagyás nélkül nem oldható fel. A production host, migration/Auth/RLS és privilege-lock csak későbbi release gate.

A zöld CI kizárólag a vizsgált branch automatikus tesztjeit igazolja. Production deploy, migration, GRANT/REVOKE, Auth/RBAC aktiválás, secretmódosítás és e-mailküldés nem történt. PR merge külön jóváhagyást igényel.

## 2026-11-26 – cégszintű lead deduplikáció és email-prioritás

A korábbi, csak alkalmazásszintű global research deduplikációt a PR #26 ágban közös DB/RPC protokoll váltja fel. A céget normalizált név- és webdomain-aliasok azonosítják; mindkét aliasra tranzakciós advisory lock kerül. A két íróút (`global_lead_research.py`, `lead_gen.py`) ugyanazt a `upsert_company_lead` RPC-t használja. A rollout kétlépcsős: először az RPC és az aliasok kerülnek fel, a régi app kompatibilitásához az INSERT átmenetileg megmarad; az RPC-t használó app deployja és smoke ellenőrzése után a második migráció újra-backfill-el és visszavonja a közvetlen INSERT/DELETE jogokat.

Egy cég több, külön hozzájárulással rendelkező emailjelöltet tárolhat, de a CRM lead egy marad. A kiválasztás kezdeti heurisztikája a szerepkörös címeket (info/contact/office/sales) hátrasorolja, a személyes webmail címet (pl. xy@gmail.com) előnyben részesíti. A jelöltek külön táblában megmaradnak; hozzájárulás nem öröklődik címek között. Küldés, válasz vagy opt-out után a kiválasztott cím nem módosítható automatikusan. Azonos cégnévhez eltérő, már regisztrált webdomain esetén a rendszer nem olvaszt össze automatikusan, hanem manuális felülvizsgálatot kér.

A migráció, Python integráció, SQL prioritás/consent teszt és két PostgreSQL sessionös race teszt a `96d4aa48a312b1942e61bb7c659dce6cdd790b0f` commiton sikeres teljes CI-vel, PostgreSQL 17 integrációval, CodeQL-lel és dependency audittal igazolt. A konkurenciavédelem fejlesztési feladata lezárható. Production migráció, deploy vagy e-mail küldés nem történt; a release readiness külön nyitott.
