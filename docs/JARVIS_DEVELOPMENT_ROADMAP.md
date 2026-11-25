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

**Frissítve:** 2026-11-25, `main` commit `1f401d0` (PR #22 merge); PR #23 head `58d9e33` még nyitott. A PR #23 push CI (`45658587888`) minden jobja sikeres; a PR-triggerelt CI (`45658617612`) test jobja az utolsó ellenőrzéskor még futott. A production backup workflow-dispatch (`45655512387`) teljesen sikeres: titkosított dump, S3 feltöltés, SSE-KMS és objektumméret ellenőrzés, letöltés, manifest/SHA-256 ellenőrzés, majd külön izolált PostgreSQL 17 restore és táblainventár/rekordszám-ellenőrzés. A restore külön runner-konténerben történt; production DB írás nem történt. [Backup futás](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45655512387).



A dokumentumot folyamatosan frissítsük; ne hozzunk létre párhuzamos, dátumozott roadmapeket.

| Sorrend | Terület | Státusz |
|---|---|---|
| 1 | Megbízhatóság és biztonság | Approval/idempotencia és backup–restore CI igazolt; SMTP hard-disable PR #23-ban kész, de még nem main; production audit és provider idempotencia nincs igazolva |
| 2 | Supabase és jogosultságkezelés | Részben előkészítve – production drift rendezés, migrációs review, deploy és live smoke hátra van; éles adatbázis változatlan |
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

**Terület 1 – Megbízhatóság és biztonság friss minősítése:** a kódbeli approval/idempotencia, audit fail-closed és SMTP unknown-state megoldások regressziós/CI tesztekkel alátámasztottak; a production backup+restore sikeres. A terület még nem zárható le: production audit/approval RPC-k nincsenek telepítve, a production structured audit mezők hiányoznak, az SMTP-küldés környezeti kapcsolókkal aktiválható és a provider oldali idempotencia nincs bizonyítva. E-mailküldés maradjon tiltva a külön validációig.


## Friss mérési állapot – 2026-11-25 (PR #23 head)

A [push CI 45658587888](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45658587888) a `58d9e33` commiton minden jobbal sikeres: 759 teszt sikeres, 3 kihagyott; line coverage 90.75% (3 729/4 109), 80%-os gate felett 10.75 százalékponttal. Branch coverage nincs mérve. A [coverage artifact](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45658587888/artifacts/15043089238) a PR #23 headhez tartozik, nem a main commitra vonatkozó új mérés.

A legnagyobb lefedettségi rés a `scripts/supabase_auth_rls_smoke.py` (17%, 42/243 sor); következő cél a `task_actions.py` (81%, 136/167), majd a backup és dashboard fennmaradó hibakezelési ágai. A line coverage önmagában nem igazolja a production Auth/RLS vagy RPC működését.

| # | Terület | 2026-11-25 minősítés | Fő következő kapu |
|---|---|---|---|
| 1 | Megbízhatóság és biztonság | Kódbeli alapok és CI igazolt; SMTP hard-disable PR #23-ban, még nem main; külső provider és production audit nem bizonyított | PR #23 teljes PR CI zárása, merge; később SMTP provider idempotencia és production audit bizonyítása |
| 2 | Supabase és jogosultságkezelés | Migráció/RPC kódban és izolált PG17 CI-ben előkészítve; production schema drift és hiányzó RPC-k miatt élesítés blokkolt | Drift rendezési terv + SQL review + külön production jóváhagyás, majd deploy/RPC smoke |
| 3 | Önállóbb üzleti asszisztens | Leadkutatás, scoring, proaktív monitor és javaslatok részben implementáltak | Forrásolt minőségi benchmark, pontosság/hasznosság visszamérése és production pilot |
| 4 | Üzleti munkafolyamatok automatizálása | Task/approval alapok implementáltak és teszteltek; teljes E2E folyamat nincs lezárva | Lead→minősítés→jóváhagyás→utánkövetés→eredménymérés E2E és KPI-k |
| 5 | Tudás és hosszú távú memória | Tartós memória/analitika alapjai implementáltak; minőségi tudásréteg nincs igazolva | Forrásolt, jogosultságkezelt, lifecycle-kezelt tudás és retrieval quality tesztek |
