# JARVIS – elsődleges fejlesztési útiterv

**Aktuális ág:** `feature/company-research-dashboard-readonly`  
**Aktuális PR:** [#28 – nyitott, nem merge-ölt](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/28)  
**Stacked alap PR-ek:** [#27](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/27), [#26](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26) – mindkettő nyitott, nem merge-ölt.  
**Központi dokumentáció:** [JARVIS Master Documentation](JARVIS_MASTER_DOCUMENTATION.md)  
**Aktuális állapot:** [CURRENT_STATE_AND_NEXT_STEPS.md](CURRENT_STATE_AND_NEXT_STEPS.md)

A roadmap a fejlesztési sorrendet határozza meg. A kódban lévő funkciót, CI-vel tesztelt viselkedést, külső integrációt és productionben aktív működést külön kell kezelni. A fejlesztési ciklusok között nem szükséges minden apró commit után külön kézi ellenőrzési megállót tartani: a kapcsolódó funkciócsomag elkészülte után egyben kell futtatni és áttekinteni a releváns ellenőrzéseket.

## Alapelv
A JARVIS először kutat és elemez, utána javasol. Adatbázis-írás, külső kapcsolatfelvétel, szerződés vagy fejlesztésindítás csak külön jogosultság- és jóváhagyási kapun keresztül történhet.

## Jelenlegi funkcionális alap
| Terület | Állapot | Korlát |
|---|---|---|
| Magyar Gemini chat | Implementált | API és helyi konfiguráció szükséges |
| Explicit céges leadkutatás | Implementált | Nem autonóm folyamatos worker |
| Cégazonosítás/deduplikáció | Implementált | Migrációs release kapuk külön kezelendők |
| Lead scoring/workflow ajánlás | Implementált | Belső javaslat, nem külső végrehajtás |
| Task CRUD | Jóváhagyásos | Külön approval szükséges |
| Task center/follow-up queue | Read-only | Nem küld üzenetet |
| Cégdosszié és snapshot store | Implementált kódban | Production migráció nem történt |
| Cégkutatási előzmény UI | PR #28-ban | Authos SELECT RLS-jogosultság még tervezendő; aktuális head CI-je nem igazolt |
| Refresh policy és candidate planner | Implementált tiszta modulok | Nincs DB-integráció és worker |
| Outbound email | Hard-disabled | Nincs küldési engedély |

## Phase 1 – cégkutatás és dosszié-előzmények
Meglévő kódszeletek: grounding-alapú strukturált cégkutatás; forrásdomainhez kötött tényvalidálás; nyilvános szakmai döntéshozói kontextus; snapshot UUID/időbélyeg/schema/hash; append-only store; refresh eligibility policy; read-only stale candidate planner; read-only dashboard előzményoldal a PR #28-ban.

Hátralévő munka: a #28 routing javítás és az aktuális funkciócsomag CI-igazolása; Authos felhasználói SELECT RLS-jogosultság külön tervezése és izolált tesztelése; planner bekötése lapozott lead- és snapshot-lekérdezéshez; follow-up számláló megbízható integrációja ténylegesen elküldött eseményekkel; atomikus globális rate/budget reservation, tartós audit, scheduler és emberi felülvizsgálat.

## Phase 1A – biztonságos háttérmotor (következő fejlesztési fókusz)
Először DB- és külső API-független job-lifecycle modult kell készíteni. Kötelező állapotok: queued, claimed/running, succeeded, retry_wait és dead_letter. Minden jobhoz stabil operation ID, lease owner/expiry, attempt counter, created/updated timestamp és last error metadata tartozik. A claim legyen atomi a későbbi repository-szerződés szerint; lejárt lease visszavehető; heartbeat csak az aktuális lease tulajdonosának sikerülhet; ugyanaz az operation ID nem hozhat létre duplikált üzleti műveletet. Retry csak konfigurált átmeneti hibákra, véges számú próbálkozással. A dead-letter állapot emberi felülvizsgálatot igényel.

Az első szelet tiszta Python logika és fake repository tesztek. Nem csatlakozik production Supabase-hez, nem futtat migrációt, nem hív Gemini API-t, nem ütemez automatikus munkát és nem küld üzenetet.

## Phase 2 – üzleti problémahipotézis
A dosszié tényekből különítse el a bizonyítékot, következtetést és hipotézist. A problémákhoz confidence, forrás és ellenőrizendő kérdés tartozzon. Bizonyítékhiány esetén további kutatás legyen a kimenet, ne kitalált probléma.

## Phase 3 – egyedi SaaS-termékötlet motor
Cégenként több termékkoncepció; magyarázható értékelés üzleti érték, illeszkedés, bizonyítottság, megvalósíthatóság, kockázat, költség és differenciálás alapján; alternatívák és piaci megoldások vizsgálata; indokolt esetben tartózkodás az ajánlástól.

## Phase 4 – globális és cégenkénti termék-tiltó napló
Globális, iparági és cégenkénti kizárások; elutasított ajánlatok és korábbi sikertelen ötletek; determinisztikus fingerprint és szemantikus hasonlóságvizsgálat; aktív projektek és ügyfélközi kizárólagosság ellenőrzése; auditált feloldás és emberi jóváhagyás.

## Phase 5 – személyre szabott ajánlat és outreach előkészítés
Forrásolt üzleti megfigyelés és problémahipotézis; személyre szabott ajánlati tervezet; marketingjogalap, országonkénti szabályok, suppression és opt-out ellenőrzés; emberi jóváhagyás. Outbound email hard-disabled marad.

## Phase 6 – válaszkezelés és értékesítési pipeline
Külön állapot az érdeklődés, kérdés, elutasítás, későbbi kapcsolatfelvétel, leiratkozás, besorolásra váró válasz és válasz nélküli állapot. A „nincs válasz” nem egyenlő elutasítással.

## Phase 7 – szerződött AI-assisted termékfejlesztés
Elfogadott és verziózott scope; írásos szerződés/megrendelés; adatkezelés, tulajdonjog, licencek és felelősség; külön belső projektindítási jóváhagyás; specifikáció, architektúra, kód, teszt, security review, ügyfél-elfogadás és átadás.

## Phase 8 – mérés és tanulás
Az ajánlások, elutasítások, ügyfélhasználat, fejlesztési költség és eredmény visszacsatolása a kutatás és rangsorolás javításához.

## Release és biztonsági szabály
A roadmap nem jogosít production DB-módosításra, migrációfuttatásra, Auth/RBAC aktiválásra, secret-változtatásra, deployra, e-mailküldésre vagy PR merge-re. Ezek külön, konkrét jóváhagyást igényelnek.


## Fejlesztési napló – 2026-11-26

Elkészült a háttérmotor első, DB-független kódszelete: company_research_jobs.py és tests/test_company_research_jobs.py. Tartalmaz job létrehozást, operation ID-t, lease claimet és lejárt lease visszavételt, heartbeatet, sikeres lezárást, bounded retry-t és dead-letter átmenetet. Ez még nem tartalmaz tartós adattárolást vagy valódi atomikus konkurens claimet; ezeket majd a repository-adapter és adatbázis oldali egyediség/locking biztosítja. Nincs scheduler, automatikus kutatás vagy külső API-hívás.


## Phase 1B – tartós job repository és SQL/RPC szerződés

- DB-független `CompanyResearchJobRepository` Protocol és injektált kliensű Supabase adapter.
- Idempotens create az `operation_id` adatbázis UNIQUE kulcsával.
- Claim, heartbeat, complete és fail kizárólag tranzakciós DB RPC-kontraktuson keresztül; Python SELECT+UPDATE nem tekinthető atomikusnak.
- Fake repository és adapter mapping tesztek; későbbi külön SQL concurrency teszt.
- Belső job tábla RLS-sel, PUBLIC/anon/authenticated tiltással és service-role-only hozzáféréssel.
- Migration csak repository-fájl, production alkalmazás nélkül. Nincs saját kliens létrehozás, secret olvasás, scheduler, Gemini-hívás vagy outbound side effect.


### Phase 1B megvalósítási napló

A PR #28 branchben elkészült a `CompanyResearchJobRepository` Protocol és az injektált Supabase adapter (`company_research_job_repository.py`), a planner és repository közötti idempotens enqueue híd (`company_research_refresh_queue.py`), a service-role-only job tábla és tranzakciós RPC-k migrationje, valamint a fake adapter/queue tesztek. Az RPC claim `FOR UPDATE SKIP LOCKED` mintát alkalmaz; heartbeat/complete/fail csak aktív lease tulajdonostól fogad el módosítást. Production DB-re nem csatlakozott, a migration nem futott le. A csomag elkészülte után lekértük az aktuális head workflow-run és combined-status adatait; mindkettő üres listát adott, így a CI-eredmény nem igazolt.


### Phase 1C – egyszeri worker-orchestration

A PR #28 ágban elkészült a `company_research_worker.py` injektált repository + handler alapú egyszeri végrehajtója. Egy hívás legfeljebb egy jobot claimel, handler eredményét complete-eli, hibáját bounded retry/dead-letter útvonalra küldi, és lease-vesztésnél nem állít sikert. A kivételszöveg nem kerül a tartós jobrekordba. A tényleges cégkutatási handler, scheduler, Gemini/API-integráció és automatikus futtatás továbbra sincs engedélyezve vagy implementálva.


### Phase 1D – bounded exponential retry backoff

- Exponenciális késleltetés attempt_count alapján, konfigurálható felső korláttal.
- Pozitív egész bemenetek validálása, overflow-biztos számítás.
- Worker-integráció és determinisztikus tesztek.
- Nem helyettesíti a globális provider rate limitet, concurrency limitet vagy költségkeretet.


### Phase 1E – admission policy és költségvédelmi döntés

- Globális óránkénti joblimit, domainenkénti napi limit és párhuzamos futási limit.
- Napi költségkeret egész mikro-USD-ben.
- Determinisztikus, DB-független döntési függvény és határérték tesztek.
- A policy önmagában nem foglal kvótát; konkurens hard limithez később atomikus DB/RPC reservation szükséges.


### Phase 1F – worker lease heartbeat callback

- Opcionális callback hosszú handler műveletek közbeni lease-megújításhoz.
- Kizárólag explicit handler checkpointból fut, automatikus timer/worker thread nélkül.
- Lease-vesztés és stale worker tesztek.


### Phase 1E/1F megvalósítási napló

Elkészült a `company_research_admission.py` és az admission-aware planner queue útvonal, valamint az exponenciális, capped retry backoff a workerben. A worker kétparaméteres handler esetén explicit heartbeat callbacket ad át. A policy és a worker viselkedéséhez fake-alapú tesztek kerültek a repositoryba. A több worker közötti globális kvótafoglalás még nincs megoldva; hard budget enforcementhez adatbázis-oldali atomikus reservation kell.


### Phase 1G – worker és idempotencia hardening megvalósítva

- Claim/handler eredmény JSON alak- és méretellenőrzés, másolt payload átadása.
- Hibakód szűrés és kivételüzenet kizárása a tartós jobrekordból.
- Operation ID újrafelhasználásának ellenőrzése immutable job mezők szerint.
- Domain napi usage kulcsainak case-insensitive normalizálása.
- Egész mikro-USD alapú tokenköltség-becslés felfelé kerekítéssel, vendor árak beégetése nélkül.


### Phase 1H – atomikus worker concurrency limit

- A claim RPC tranzakciós advisory lockkal sorosítja a kapacitásellenőrzést.
- Aktív, le nem járt lease-ek számlálása és plafon ellenőrzése a job felvétele előtt.
- A repository/worker explicit concurrency ceiling paramétert ad át.
- Fake adapter teszt lefedi az RPC-paraméterezést; valódi konkurenciateszt izolált PostgreSQL környezetben még szükséges.


### Phase 1I – tartós budget reservation és worker audit implementálva

- Atomikus napi UTC cost reservation a job-create RPC tranzakciójában, advisory lockkal.
- Idempotens operation ID replay nem foglal újra költséget.
- Túllépéskor kontrollált `daily_cost_limit` elutasítás.
- Tartós budget reservation tábla és append-only lifecycle audit tábla.
- Audit események: enqueue, claim, heartbeat, success, retry, dead-letter és final lease expiry.
- Production migration nem futott; PostgreSQL konkurencia-/tranzakcióteszt, actual-cost settlement, reservation release és atomikus hourly/domain rate quota még szükséges.

- Korlátozott (1–1000 sor) operation ID szerinti audit-list RPC és repository metódus.


### Phase 1J – atomikus rate limit enforcement implementálva

- Globális UTC óránkénti jobkvóta adatbázisoldali ellenőrzése.
- Domainenkénti UTC napi jobkvóta adatbázisoldali ellenőrzése, case-insensitive domain kulccsal.
- A költségkeret és rate limit ellenőrzések közös tranzakciós advisory lock alatt futnak.
- Idempotens operation ID replay nem fogyaszt új kvótát.
- A DB állítja be a job `created_at` értékét.
- A tényleges provider-költség elszámolása és reservation release még hátravan.


### Phase 1K – actual cost settlement alap implementálva

- Opcionális worker actual-cost extractor callback.
- Szigorú egész mikro-USD validáció.
- Sikeres job completion és reservation settlement ugyanabban az RPC-tranzakcióban.
- Audit metadata tartalmazza a tényleges költséget.
- Provider-specifikus token usage adapter és valós költségmérés még hátravan.

- Minden Python enqueue helper a kötelező budget/hourly/domain limiteket adja át; a korlátokat megkerülő egyszerű queue útvonal megszüntetve.


### Phase 1L – grounded provider execution adapter alap implementálva

- Gemini + Google Search grounding provider adapter, injektált klienssel/modellel.
- Strukturált JSON és provider grounding URL validáció; csak grounded hostra hivatkozó tények kerülnek a dossziéba.
- Retry maximum 3 próbálkozással, exponenciális backoff.
- Worker handler factory és lease ellenőrzés provider hívás előtt/után.
- Provider token usage metadata és konfigurált input/output tokenáras actual cost extractor.
- A hosszú szinkron provider hívás alatti heartbeat renewal implementálva: konfigurálható időközű, leállítható háttérszál frissíti a lease-t; lease-vesztéskor a provider eredménye nem használható fel.
- Nyitott: valós runtime/queue/store integráció, provider hitelesítés és end-to-end futtatás.

- One-shot runtime composition root: repository, grounded Gemini provider, worker és actual-cost extractor explicit injektált összekötése.
- Még nincs scheduler, dashboard trigger, credential/client bootstrap vagy automatikus háttérfuttatás.


#### Phase 1L hibajavítás – Gemini lease renewal

A provider adapter a teljes szinkron kérés és retry-szakasz alatt külön daemon szálból, konfigurálható időközönként frissíti a worker lease-t. A heartbeat hibája vagy hamis eredménye lease-vesztést okoz; a provider válasz nem kerül visszaadásra sikeres eredményként. A heartbeat szál a kérés lezárásakor leáll. Két célzott teszt ellenőrzi a periodikus renewal és a lease-vesztés viselkedését.


## Főrendszer-készültségi kapu – 2026-11-26

A belső főrendszer és az autonóm SaaS-ügynök két külön cél. A főrendszer lezárási feltételeit és a P0/P1/P2 feladatokat a [JARVIS_MAIN_SYSTEM_READINESS.md](JARVIS_MAIN_SYSTEM_READINESS.md) tartalmazza. A core lead → approval/task → audit E2E és az előző core commit teljes CI-je sikeres. A dashboard navigációs leltár, a read-only Settings oldal és az üres tasklista melletti utánkövetési sor hibajavítása elkészült; az audit utáni aktuális HEAD teljes CI-je, a valós Auth/RLS hozzáférés, worker SQL konkurencia és snapshot E2E, majd dokumentált helyi smoke következik. Scheduler, teljes SaaS-ötletmotor, tiltó napló, outreach és AI-fejlesztési pipeline nem blokkolja a belső core asszisztens lezárását.
