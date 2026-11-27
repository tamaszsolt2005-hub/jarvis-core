> **HITeles, frissített állapot – 2026-11-27 13:37 CET.** Ez a státuszblokk a dokumentum alábbi korábbi, dátumozott állapotjelentéseit felülírja. A vizsgált kód a `feature/opportunity-center-readonly` branch PR #35-ös állapota, HEAD: `f90225235b804ca0d13930d11bbf1f1ae627e9f2`. PR #35 nyitott, Draft, nem merge-ölt; a PR #34-re épül. A HEAD-hez tartozó automatikus JARVIS CI run `45999509740` befejeződött `success` eredménnyel. A felhasználó kérésének megfelelően lokális tesztet és kézi CI-dispatch-et nem futtattunk. Ez a CI az izolált tesztkörnyezetet igazolja, nem production üzemet.
>
> **Kész a kódban (PR #35):** Opportunity Engine adatmodell és dashboard; céges problémahipotézisek és legalább két külön céghez kötött validált piaci mintázatok; SaaS-jelöltek; hatdimenziós, forrásbizonyítékhoz kötött scoring; evaluator preview session state-ben; explicit admin/operator jóváhagyás és append-only assessment history; közös `intelligence_engine.py` evidence/provenance szerződés és append-only `intelligence_evidence` index Lead-, dossier- és pain-forrásokhoz; Intelligence áttekintő; származtatott Intelligence Graph és Graphviz dashboardfül. A gráf forrásai a domain táblák, az AI által kitalált kapcsolatok nem válnak automatikusan igazolt élekké. A gráf Python projection determinisztikus, duplikált node ID esetén bemenet-sorrendtől függetlenül választ rekordot.
>
> **Biztonsági és release-határ:** a PR #35 migrációi csak a repository/CI részei; production adatbázison nem futottak le. A dashboard nincs production deployolva. Az assessment preview nem ment automatikusan; a mentés explicit admin/operator jóváhagyás. A dashboard authenticated/RLS útvonalat használ, nincs service-role write bypass. A PR merge, production migráció, Auth/RLS éles módosítás és deploy külön, konkrét engedélyt igényel.
>
> **Ami még nincs kész / igazolva:** teljes automatikus Opportunity Discovery Pipeline; időzített cégkutatás és folyamatos automatikus adatbetöltés; több cég problémáinak autonóm felismerése és validálása end-to-end; valós fizetési hajlandóság/interjúvalidáció; élő staging/provider-integrációs smoke; production release. A meglévő komponensek és dashboard nem bizonyítják, hogy a teljes pipeline önállóan működik.
>
> **Javasolt következő sorrend:** (1) PR #34/#35 kód-, migráció-, RLS- és dokumentációs review, stacked PR függőség tisztázása; (2) izolált staging környezetben Auth/JWT/RLS és migráció smoke, production érintése nélkül; (3) Opportunity Discovery adatfolyam első, kézi/explicit indítású vertical slice-e: kiválasztott cégek → grounded kutatás → dossier/evidence → pain hypothesis → market pattern; (4) adatminőségi és evidence-minimum szabályok, mintázat deduplikáció és emberi validáció; (5) ügyfélinterjúk/fizetési hajlandóság validálása, majd SaaS-jelölt értékelés; (6) csak ezután scheduler/automatizálás és release-terv. Tesztet helyben nem futtatunk, kézi CI-dispatch nincs.

---

# JARVIS – elsődleges fejlesztési útiterv

> **AKTUÁLIS FEJLESZTÉSI ÁLLAPOT – 2026-11-27 (PR #34 és PR #35).** A `feature/daily-hard-budget-cap` ág PR #34-e továbbra is open + draft, merged=false. Az Opportunity Engine fejlesztése a `feature/opportunity-center-readonly` ágon, a [PR #35](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/35) részeként található; PR #35 a PR #34-re épül, open + draft, merged=false. A legutóbb ellenőrzött kód-HEAD `8cb080856f745dc5f8278f78a836791a75b48355`; a dokumentációs commitok ezt a HEAD-et tovább fogják mozgatni. Egyik PR sem merge-ölhető külön, konkrét felhasználói engedély nélkül.
>
> **PR #35-ben implementált:** Opportunity Center dashboard; forrásolt céges problémahipotézisek; legalább két különböző vállalathoz kötött, validálható piaci mintázatok; SaaS-jelöltek; hatdimenziós, bizonyítékhoz kötött pontozás; provider-neutral evaluator és session-state előnézet; explicit admin/operator jóváhagyás; immutable, append-only döntési előzmény, idempotenciakulcs, actor/model/version/time és opportunity/pattern snapshot mezők.
>
> **Pontozás:** probléma bizonyítottsága 25%, üzleti érték 20%, fizetési hajlandóság 15%, megvalósíthatóság 15%, újraértékesíthetőség 15%, kockázat 10% fordított irányban. Hiányzó score-dimenzió esetén nincs összpontszám. Minden dimenzióhoz rationale és source evidence szükséges; a hipotézis nem válik automatikusan ténnyé.
>
> **Jogosultság:** hitelesített `admin` és `operator` szerepkör explicit gombnyomással menthet; `reader` csak olvashat; anon nem fér hozzá. A DB trigger ellenőrzi a szerepkört, a validált mintázatot, a két külön céges alátámasztást és a forrás-egyezést. A jóváhagyási előzmény UPDATE/DELETE művelete tiltott. A dashboard user path nem használ service-role írási megkerülést.
>
> **Migrációk:** `20261127100000` core, `20261127110000` scoring, `20261127120000` score evidence, `20261127130000` approval history. Ezek a PR branch részei; production adatbázison nem futottak le. A dashboard nincs production deployolva.
>
> **CI és tesztelés:** a felhasználó kérésére lokális tesztet és kézi CI-dispatch-et nem futtattunk. A kód commitján a GitHub Actions automatikusan indult; a korábbi ellenőrzéskor run `45987043894` folyamatban volt, ez nem jelent zöld CI-t. A dokumentációs commit után az aktuális PR HEAD-hez tartozó legfrissebb CI-t külön kell ellenőrizni. A CI izolált adatbázis, nem production-validáció.
>
> **Következő lépések:** dokumentációs és kód review; a legfrissebb CI eredmény megvárása; Auth/JWT/RLS és migrációk izolált környezetű felülvizsgálata; külön jóváhagyás után staging smoke. Production migration, Auth/RLS éles módosítás, deploy és PR merge továbbra is külön engedélyhez kötött.
**Aktuális ág:** `main`  
**PR állapot:** #26, #27 és #28 merge-ölve.  
**PR #28 merge commitja:** `9ceb2f7fdd0130240c15dc4e1701d3fba1bdb53c`  
**CI #3187:** mindhárom job sikeres.

**Központi dokumentáció:** [JARVIS Master Documentation](JARVIS_MASTER_DOCUMENTATION.md)  
**Aktuális állapot:** [CURRENT_STATE_AND_NEXT_STEPS.md](CURRENT_STATE_AND_NEXT_STEPS.md)

A roadmap a fejlesztési sorrendet határozza meg. A kódban lévő funkciót, CI-vel tesztelt viselkedést, külső integrációt és productionben aktív működést külön kell kezelni. A fejlesztési ciklusok között nem szükséges minden apró commit után külön kézi ellenőrzési megállót tartani: a kapcsolódó funkciócsomag elkészülte után egyben kell futtatni és áttekinteni a releváns ellenőrzéseket.

## Alapelv
A JARVIS először kutat és elemez, utána javasol. Adatbázis-írás, külső kapcsolatfelvétel, szerződés vagy fejlesztésindítás csak külön jogosultság- és jóváhagyási kapun keresztül történhet.

## Aktuális Phase 1 végrehajtási állapot

A job → claim → grounded provider → validált dosszié → append-only snapshot → lead FK-kapcsolat → job completion út most a one-shot runtime-ban össze van kötve. A snapshot ID a job operation ID-jából determinisztikusan képződik, így a snapshot insert utáni worker retry nem hoz létre új snapshotot; azonos operation ID eltérő tartalommal konfliktust jelez. A worker csak a snapshot mentése után complete-elhet.

A PostgreSQL worker tesztek külön CI jobban, eldobható PostgreSQL 17 adatbázisban futnak. A job 15 lifecycle/kvóta és 14 két-session `dblink` konkurenciatesztet, valamint a snapshot tároló tesztjét futtatja. **A tényleges sikerességet csak az új commiton befejeződő CI igazolhatja.** A scheduler és automatikus futtatás nincs bekapcsolva; élő Gemini API-kérés nem történt.

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

**Állapot: első implementáció PR #35-ben.**

A `business_pain_hypotheses` modell, confidence/státusz és forrás-evidence mezők, valamint az Opportunity Center céges probléma nézete elkészült. A hipotézis és bizonyított tény külön kezelendő. További feladat: a kutatási dosszié tényekből történő automatizált, ellenőrizhető hipotézis-képzés és az evidence minőségének mélyebb validálása. Részletek: [Opportunity Engine](OPPORTUNITY_ENGINE.md).

## Phase 3 – ismétlődő piaci mintázatok és SaaS-termékötlet motor

**Állapot: első implementáció PR #35-ben.**

A több cég problémáit összekötő `market_problem_patterns` és `market_pattern_pains` modell, a legalább két különböző céges alátámasztást kikényszerítő validáció, a `saas_opportunities` jelöltek és a provider-neutral evaluator elkészült. A pontozás hat dimenziót használ: probléma bizonyítottsága 25%, üzleti érték 20%, fizetési hajlandóság 15%, megvalósíthatóság 15%, újraértékesíthetőség 15%, kockázat 10% fordított irányban. Hiányos bizonyíték esetén nincs pontszám.

Az evaluator csak előnézetet készít; explicit emberi jóváhagyás szükséges a tartós mentéshez. Az append-only értékelési előzmény, az admin/operator írási és reader olvasási jogosultság, a forrás-egyezés és az idempotencia alapja PR #35-ben implementált. További feladat: piaci alternatívák, TAM/SAM/SOM, árképzés, unit economics, ügyfél-validáció és a pontozási dimenziók üzleti adatokkal történő kalibrálása. Részletek: [Opportunity Engine](OPPORTUNITY_ENGINE.md).

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


## Aktuális prioritások – 2026-11-26

> PR #26–#28 merge-ölve a main ágba. CI #3187: 3/3 job sikeres. A worker, queue bridge, provider adapter, snapshot persist→complete, lease/heartbeat/retry/dead-letter és költségelszámolási callback kódban implementált. Következő: napi hard budget cap, scheduleres futtatás, Auth/RLS snapshot-hozzáférés, élő Gemini staging smoke, helyi manuális dashboard smoke. Production DB/deploy nincs engedélyezve vagy végrehajtva.

## Korábbi fejlesztési napló – 2026-11-26 (történeti)

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


## Szelektív tesztelési és bizonyíték-kezelési szabály

A teljes CI nem minden commit utáni kötelező lépés. Változatlan kód korábban sikeres tesztjeit nem ismételjük feleslegesen. A módosított modulokhoz tartozó célzott tesztek, közvetlen regressziós tesztek és új integrációs kockázatok ellenőrzése az elsődleges. Teljes CI-t csak egy összefüggő fejlesztési mérföldkő lezárásakor és merge/release gate-ként futtatunk. A backup–restore, SQL konkurencia, Auth/RLS és valós provider smoke külön bizonyítékot igényel; az egyik sikeres tesztje nem helyettesíti a másikat.

A jelenlegi nyitott feladatok és a korábban már igazolt tesztkörök tételes listája: [JARVIS_REMAINING_WORK_REPORT.md](JARVIS_REMAINING_WORK_REPORT.md).


## Roadmap státuszfrissítés – 2026-11-26

**Aktuális PR #28 HEAD:** `4e5bed363285553525aae89ff4aae78b5e79de2b`. **CI:** [Run #3136](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45883574515) – mindhárom job sikeres: Python/AppTest/browser tesztek (`140128615157`), izolált PostgreSQL worker-integráció (`140128614819`), backup–restore (`140128615278`). Eredmény: **1144 passed, 3 skipped, 0 failed**, coverage **90,17%**; `python -m compileall -q .` sikeres. A PostgreSQL job sikeresen lefuttatta a snapshot-tároló tesztet, a **15/15 lifecycle/kvóta** és a **14/14 két-session dblink konkurencia** assertiont.

### P0 – fejlesztési csomag állapota

A Gemini és külső szolgáltatások hibakezelési P0 kódcsomag **elkészült és a fenti teljes CI zölden ellenőrizte**. Ide tartozik a Google GenAI státuszkódok normalizálása, központi retry-besorolás, korlátozott exponenciális retry, 429/503 fallback, auth/config/invalid-request no-retry, biztonságos provider-kód allowlist, titokmentesített hibajelzés és az SMTP duplikált újraküldésének kizárása. A Settings AppTest korábbi hibája is javítva van.

**Korlát:** valódi Google Gemini API-val végzett élő/staging smoke nem történt. A CI a mockolt/tesztelt viselkedést igazolja, nem a szolgáltató élő válaszát. Ez a külső integrációs ellenőrzés továbbra is hátralévő feladat.

### Jelenlegi termékképességek – mi van ma a JARVIS-ban?

- Magyar nyelvű, Gemini-alapú üzleti chat (működéséhez helyi API-konfiguráció szükséges).
- Kifejezett felhasználói kérésre indított, Google Search groundingre épülő lead/cégkutatás; dokumentált korlátja legfeljebb 15 új cég egy futásban.
- Cégazonosítás és duplikációszűrés; lead scoring, kutatási bizonyosság és belső workflow-ajánlások.
- Jóváhagyáshoz kötött task létrehozás/módosítás/lezárás; read-only Feladatok központ és utánkövetési sor.
- Üzleti memória, napi briefing, analitika és audit funkciók.
- Cégdosszié/snapshot és read-only kutatási előzmény UI kódban; a worker runtime→provider→snapshot→lead FK→complete/audit út CI-vel igazolt. Auth módban a snapshot oldal továbbra is fail-closed, amíg az RLS olvasási jogosultság nincs megfelelően kiépítve.
- Read-only Beállítások oldal, konfigurációs státuszok és kézi diagnosztika; titokértékek nem jelennek meg és nem szerkeszthetők.
- Bejövő inbox/e-mail komponensek konfigurációtól függően rendelkezésre állhatnak; **kimenő e-mail küldés hard-disabled**.

### Ami még NINCS kész – a SaaS-vízió és a tényleges termék közötti különbség

A JARVIS jelenleg nem autonóm SaaS-értékesítő vagy önálló SaaS-gyár. Nincs kész automatikus piacfigyelő/cégfelderítő scheduler, folyamatos háttérkutatás, teljesen bekötött és bizonyított worker adatút, automatikus SaaS-termékötlet- és versenytárselemző motor, globális/cégenkénti termék-tiltó és ütközésnapló, automatikus személyre szabott outreach, outbound e-mail, illetve AI-alapú teljes termékfejlesztési/build/release pipeline. Ezek célfunkciók, nem jelenlegi kész képességek.

### Következő javítások és lezárási sorrend

**P1 – állapot és még hátralévő feladatok:**
1. **[KÉSZ – kódoldali runtime E2E, CI #3136]** Queue → claim → grounded provider → dossier validáció → snapshot mentés → lead FK-kapcsolat → job completion/audit bekötve. A worker csak a snapshot mentése után complete-elhet; operation ID-alapú stabil snapshot UUID, idempotens replay és persist-hiba esetén retry/dead-letter viselkedés célzott tesztet kapott. Élő Gemini API-hívás nem történt.
2. **[KÉSZ – CI #3136, izolált PostgreSQL 17]** `company_research_jobs.test.sql`: 15/15 lifecycle/kvóta assertion; `company_research_jobs_concurrency.test.sql`: 14/14 valódi, két `dblink` sessionnel futó konkurencia assertion; a snapshot-tároló SQL teszt is sikeres. A futtatás kizárólag eldobható CI-adatbázisban történt.
3. Worker lifecycle teljesítése/tesztelése: lease expiry és reclaim, heartbeat, párhuzamos claim és concurrency plafon, retry/dead-letter, idempotencia, óránkénti/napi/domain kvóták, actual-cost settlement és audit tranzakció.
4. Auth/RLS izolált szerepkörtesztek: reader/admin, valós JWT, RPC, service-role kizárólag trusted server oldalon; fail-closed és nincs jogosultsági fallback.
5. Valódi Google GenAI SDK/izolált staging integrációs próba: 429, 503, timeout, auth, grounding metadata, usage/cost és retry/heartbeat; production kulcs és production DB nélkül.
6. Teljes helyi manuális dashboard smoke: Chat, Feladatok, Analitika, Cégkutatás, Audit, Beállítások; üres adat, hiányzó/hibás konfiguráció, hálózat, kvóta és permission állapotok.
7. Chat gyorsműveletek valódi kattintható műveletté alakítása; user preference mentés csak jóváhagyott adattárolási modell alapján, a titkok és biztonsági zárak változtathatatlanul hagyásával.

**P2 – későbbi terméképítési szakasz:** scheduler/automatikus háttérkutatás; SaaS-ötletmotor és piaci alternatívaelemzés; globális és cégenkénti tiltó/ütközésnapló; ajánlatgenerálás és outreach workflow; jogszerű marketing-hozzájárulás/suppression modell; outbound e-mail külön engedélyezés után; AI-assisted termékfejlesztés és build/test/release pipeline.

### PR és környezeti állapot

PR #26, #27 és #28 merge-ölve a `main` ágba 2026-11-26-án. A JARVIS app továbbra is helyi fejlesztés alatt áll, production app-host/deploy nincs. A production DB-n nem történt módosítás; nincs production migration, deploy, secret-változtatás vagy e-mailküldés. A dokumentált CI nem jelent production readiness-t.


## Aktuális roadmap státusz – 2026-11-26

> **Aktuális állapot – 2026-11-26 (a korábbi státuszblokkokat felülírja).** A PR #26, #27 és #28 mind merge-ölve van a `main` ágba. A PR #28 merge commitja: `9ceb2f7fdd0130240c15dc4e1701d3fba1bdb53c`. A PR #28 HEAD-hez tartozó CI #3187 (run `45900450820`) mindhárom jobja sikeres: Python/AppTest/browser tesztek, izolált PostgreSQL 17 worker-integráció, valamint backup–restore/security. A PR #26 HEAD-en a JARVIS CI, CodeQL és dependency audit sikeres; a PR #27 HEAD-en a JARVIS CI sikeres. A merge commiton külön post-merge workflow/státusz nem jelent meg, ezért a merge utáni újrafuttatás nem tekinthető igazoltnak.
>
> **Implementált és CI-vel tesztelt:** cégdosszié és append-only snapshot tárolás; read-only előzmény-dashboard; worker job lifecycle, repository/RPC adapter, queue bridge és worker; injektálható grounded Gemini provider adapter; snapshot mentés a job sikeres lezárása előtt; idempotencia; lease/heartbeat/retry/dead-letter; PostgreSQL lifecycle, kvóta, security és két-session konkurenciatesztek. A CI izolált adatbázist használ, nem productiont.
>
> **Még nincs élesben igazolva / nincs bekapcsolva:** ütemezett automatikus futtatás; a worker schedulerből történő indítása; élő Gemini API/staging smoke; Auth-os snapshot SELECT (a dashboard Auth módban fail-closed, a snapshot tábla service_role-only); teljes manuális helyi dashboard smoke; production app-host és deploy.
>
> **Költségkorlát:** a becsült költségfoglalás, actual-cost settlement callback és tranzakciós elszámolás kódban megvan. A provider adapter nincs élő szolgáltatói hívással validálva, és az actual cost a becslést meghaladhatja; ezért a napi hard cap teljes kikényszerítése még külön feladat.
>
> **Biztonsági határ:** production Supabase migráció/DDL/DML, grant/RLS/Auth módosítás, secret-változtatás, deploy és outbound e-mail nem történt. A kimenő e-mail hard-disabled. A CI-zöld állapot önmagában nem production readiness.
>
> **Következő fókusz:** (1) napi hard budget cap és reservation-overrun védelem; (2) scheduler/operációs vezérlés és worker futtatási életciklus; (3) izolált Auth/JWT/RLS jogosultsági tesztek, különösen snapshot history hozzáférés; (4) élő, nem production Gemini staging smoke usage/grounding/retry/heartbeat ellenőrzéssel; (5) teljes helyi dashboard manuális smoke; (6) production migration drift és hozzáférési modell független felülvizsgálata, majd külön release-döntés.
>
> A dokumentum korábbi PR-állapotai, régi CI-run számai és „nincs worker” megjegyzései történeti feljegyzések; a fenti blokk az aktuális összefoglaló. Részletek: [PR #26](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26), [PR #27](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/27), [PR #28](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/28), [CI #3187](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45900450820).


## Intelligence Graph – fejlesztési állapot

Az Intelligence Graph első implementációja PR #35-ben elkészült: gráf-adatmodell, meglévő rekordok backfillje, triggeres szinkronizálás, Python-projekció és read-only dashboard. Következő validációs feladat a friss commitok CI-eredményének ellenőrzése, majd később a gráf-szűrés, iparági/entitás-alapú fókusz és a nagyobb adatmennyiségek lapozott vizsgálata. Production migráció és deploy nem történt. Részletek: [INTELLIGENCE_GRAPH.md](INTELLIGENCE_GRAPH.md).
