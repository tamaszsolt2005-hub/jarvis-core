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

# JARVIS – aktuális állapot és következő lépések

> **AKTUÁLIS FEJLESZTÉSI ÁLLAPOT – 2026-11-27 (PR #34 és PR #35).** A `feature/daily-hard-budget-cap` ág PR #34-e továbbra is open + draft, merged=false. Az Opportunity Engine fejlesztése a `feature/opportunity-center-readonly` ágon, a [PR #35](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/35) részeként található; PR #35 a PR #34-re épül, open + draft, merged=false. A pontos aktuális kód-HEAD-et és CI-állapotot a PR #35 GitHub-oldala mutatja; a branch folyamatosan frissül. Egyik PR sem merge-ölhető külön, konkrét felhasználói engedély nélkül.
>
> **PR #35-ben implementált:** Opportunity Center dashboard; forrásolt céges problémahipotézisek; legalább két különböző vállalathoz kötött, validálható piaci mintázatok; SaaS-jelöltek; hatdimenziós, bizonyítékhoz kötött pontozás; provider-neutral evaluator és session-state előnézet; explicit admin/operator jóváhagyás; immutable, append-only döntési előzmény, idempotenciakulcs, actor/model/version/time és opportunity/pattern snapshot mezők.
>
> **Pontozás:** probléma bizonyítottsága 25%, üzleti érték 20%, fizetési hajlandóság 15%, megvalósíthatóság 15%, újraértékesíthetőség 15%, kockázat 10% fordított irányban. Hiányzó score-dimenzió esetén nincs összpontszám. Minden dimenzióhoz rationale és source evidence szükséges; a hipotézis nem válik automatikusan ténnyé.
>
> **Jogosultság:** hitelesített `admin` és `operator` szerepkör explicit gombnyomással menthet; `reader` csak olvashat; anon nem fér hozzá. A DB trigger ellenőrzi a szerepkört, a validált mintázatot, a két külön céges alátámasztást és a forrás-egyezést. A jóváhagyási előzmény UPDATE/DELETE művelete tiltott. A dashboard user path nem használ service-role írási megkerülést.
>
> **Központi Intelligence Engine:** `intelligence_engine.py` közös provenance szerződés; `20261127140000_intelligence_evidence_store.sql` tartós, append-only `intelligence_evidence` indexet hoz létre. Trigger indexeli a Lead `research_evidence`, a cégdosszié snapshot `evidence_records` és az Opportunity pain evidence rekordokat. A globális leadkutatás kizárólag Google-groundinggel igazolt cégdosszié-tényeket ír strukturált Lead evidence mezőbe; szabad szöveges modell-összefoglalót nem emel bizonyítékká. Az Opportunity Center új Intelligence áttekintő füle forráslinkeket, domain-összesítést és időbélyegeket mutat. A migráció RLS-en keresztül csak authenticated olvasást ad; service_role append-only írásra jogosult. A központi index nincs szinkronizálva külső/korábbi, strukturálatlan Lead jegyzetekből.
>
> **Migrációk:** `20261127100000` core, `20261127110000` scoring, `20261127120000` score evidence, `20261127130000` approval history, `20261127140000` Intelligence evidence store. Ezek a PR branch részei; production adatbázison nem futottak le. A dashboard nincs production deployolva.
>
> **CI és tesztelés:** az Intelligence evidence store pgTAP tesztje 12 assertiont ellenőriz, és a migráció idempotencia-replay is bekerült a CI-be. A dashboard és Lead-kutatás AppTest/unit tesztjei frissültek. A felhasználó kérésére lokális tesztet és kézi CI-dispatch-et nem futtattunk. A pushok automatikus GitHub Actions futást indítanak; az aktuális PR HEAD-hez tartozó CI-t külön ellenőrizni kell. A CI izolált adatbázis, nem production-validáció.
>
> **Következő lépések:** dokumentációs és kód review; a legfrissebb CI eredmény megvárása; Auth/JWT/RLS és migrációk izolált környezetű felülvizsgálata; külön jóváhagyás után staging smoke. Production migration, Auth/RLS éles módosítás, deploy és PR merge továbbra is külön engedélyhez kötött.
**Frissítve:** 2026-11-26  
**Aktív fejlesztési ág:** `main`  
**PR állapot:** #26, #27 és #28 merge-ölve a `main` ágba.  
**PR #28 merge commitja:** `9ceb2f7fdd0130240c15dc4e1701d3fba1bdb53c`  
**Legutóbbi CI:** [#3187](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45900450820), mindhárom job sikeres. A merge commit külön post-merge CI-je nincs igazolva.

A teljes összefüggő leírás: [JARVIS Master Documentation](JARVIS_MASTER_DOCUMENTATION.md).

## Aktuális P1 végrehajtási állapot

> **Frissítés – 2026-11-26:** PR #26–#28 merge-ölve a main ágba. A worker lifecycle, repository/RPC, queue bridge, injektálható grounded Gemini adapter, snapshot-persist→complete, idempotencia, lease/heartbeat/retry/dead-letter és költségelszámolási callback kódban implementált, CI #3187-ben tesztelt. Scheduleres automatikus indítás, élő Gemini/staging smoke, Auth-os snapshot SELECT (fail-closed), teljes manuális dashboard smoke és production deploy még nincs. A napi hard budget cap teljes kikényszerítése még fejlesztendő; production DB és deploy nem módosult.

- A one-shot runtime kötelezően injektált snapshot-adatbázist kap, és a worker sikeres lezárása előtt elmenti a validált dossziét a `company_research_snapshots` táblába.
- A snapshot az `operation_id` alapján determinisztikus UUID-t kap. Ha a snapshot insert sikerült, de a job complete lease-vesztés vagy átmeneti hiba miatt nem, az ismételt worker futás ugyanazt a snapshotot ismeri fel; eltérő tartalommal nem írja felül.
- A mentett snapshot a `lead_id` idegen kulcson keresztül kapcsolódik a leadhez. A snapshot ID és a mentés ténye a job eredményébe is bekerül; a job csak a mentés után complete-elhető.
- A worker külön teszteli a persist → complete sorrendet és azt, hogy mentési hiba esetén nincs sikeres complete, hanem retry/dead-letter útvonal indul.
- A CI új, külön PostgreSQL 17 jobot kapott: izolált fixture, snapshot + worker migrációk, snapshot pgTAP, 15 lifecycle/kvóta assertion és 14 valódi két-session `dblink` race assertion.
- **Ellenőrzési státusz:** A korábbi CI #3136 történeti eredmény; az újabb PR #28 HEAD ellenőrzése a CI #3187, mindhárom job sikeres. A külön PostgreSQL 17 jobban a snapshot-teszt, 20/20 lifecycle/kvóta, 12/12 security és 14/14 konkurencia assertion sikeres. Valódi Gemini API-hívás és production adatbázis-módosítás továbbra sem történt.

## 1. Telepítési és környezeti állapot

- A JARVIS Streamlit alkalmazás helyi fejlesztés alatt áll.
- Nincs kiválasztott JARVIS production app-host vagy production alkalmazás URL.
- A létező Supabase production projekt különálló adatbázis; nem jelenti az alkalmazás deployját.
- A jelenlegi feature branch migrációi nem lettek production adatbázisra alkalmazva.
- A Railway `VolleyForm` projekt nem JARVIS.

## 2. Mi van már a kódban?

### Meglévő JARVIS-alapok
- Magyar nyelvű Gemini chat és üzleti kontextus.
- Explicit kérésre indított, grounding-alapú leadkutatás, legfeljebb 15 új cég/futás.
- Cégazonosítás és duplikációszűrés közös íróúttal.
- Lead scoring, kutatási bizonyosság és belső workflow-ajánlások.
- Task létrehozás/módosítás/lezárás jóváhagyásos útvonallal.
- Read-only task center és consent-aware follow-up queue.
- Outcome-alapú belső következő lépések.
- Üzleti memória, napi briefing, analitika és audit.
- Bejövő e-mail/inbox komponensek konfigurációtól függően; outbound küldés hard-disabled.

### PR #27 – cégkutatás első szelete
- Strukturált üzleti tények és nyilvános szakmai döntéshozói kontextus bekérése.
- `company_dossier.py`: forrás URL és grounding domain ellenőrzés, engedélyezett ténykategóriák, privát elérhetőségek kizárása.
- Dosszié snapshot metaadat: UUID, UTC időbélyeg, schema version és SHA-256 fingerprint.
- `company_research_store.py`: validált, append-only snapshot mentés és korlátozott történetlekérdezés.
- `company_research_snapshots` SQL migráció: RLS engedélyezés, anon/authenticated tiltás, service_role SELECT/INSERT.
- Fail-closed dosszié-frissességi szabály.
- `company_research_policy.py`: elutasítás/opt-out kizárása, két válasz nélküli utánkövetés után automatikus refresh szüneteltetése, meg nem keresett leadek megtartása.
- `company_research_refresh_planner.py`: read-only stale candidate kiválasztás, uncontacted prioritás, friss snapshot kihagyása, duplikációszűrés és limit.

## 3. Mi nincs még kész?

- A planner bekötése a DB-ből lapozva beolvasott leadekhez és legfrissebb snapshotokhoz.
- Automatikus cégkutatási scheduler és háttérworker.
- Claim/lease, heartbeat, retry limit, dead-letter és költség/rate limit a kutatási workerhez.
- A refresh policy bekötése a teljes CRM/outreach eseményállapotba.
- A két follow-up limit megbízható érvényesítése ténylegesen elküldött eseményekből.
- Kutatási előzmény és frissítési státusz UI.
- Bizonyítékokra épülő üzleti problémahipotézis motor.
- Egyedi SaaS-termékötlet-generálás és rangsorolás.
- Globális és cégenkénti „mit ne ajánljunk” napló.
- Személyre szabott ajánlati csomag és outbound compliance gate.
- Teljes értékesítési pipeline és szerződéses projektindítás.
- AI-assisted fejlesztési, tesztelési és átadási folyamat.

## 4. Kutatási frissítési szabály – tervezett viselkedés

| Cég állapota | Frissítési döntés |
|---|---|
| Még nem kerestük meg | Kutatható |
| 0–1 válasz nélküli follow-up | Kutatható |
| Legalább 2 válasz nélküli follow-up | Automatikus frissítés szünetel |
| Kifejezett elutasítás | Kizárva |
| Leiratkozás / do-not-contact | Kizárva |
| Érdeklődés / későbbi egyeztetés | Kutatható, felülvizsgálható |
| Nem besorolt bejövő válasz | Nem tekinthető válaszhiánynak |

A policy önmagában nem küld üzenetet, nem módosít lead státuszt, és nincs workerbe kötve. A kutathatóság nem jelent kapcsolatfelvételi engedélyt.

## 5. Következő fejlesztési sorrend

1. A PR #26–#28 integrációja megtörtént; következő lépés a main ágon a fennmaradó költségkorlát, scheduler és Auth/RLS feladatok fejlesztése.
2. A dokumentált snapshot migráció és store kód további ellenőrzése.
3. A read-only planner bekötése lapozott lead- és snapshot-lekérdezéshez, majd tesztelés nagy adathalmazon.
4. Megbízható outreach eseményszámláló és állapotmapping a follow-up policy-hoz.
5. Idempotens, jóváhagyott ütemezésű kutatási worker.
6. Kutatási UI és emberi ellenőrzés.
7. Ezután üzleti problémahipotézis és SaaS-ötletmotor.

## 6. Változtatási és biztonsági határok

- A PR #26, #27 és #28 2026-11-26-án merge-ölve lett a main ágba.
- Production Supabase DDL/DML, migration, GRANT/REVOKE, Auth/RBAC, secret és infrastruktúra módosítása tilos külön engedély nélkül.
- Production deploy és outbound e-mail küldés nincs engedélyezve.
- CI zöld státusza csak az adott SHA-ra és az adott tesztkörnyezetre érvényes.


## Közös pontozási modell

A Lead prioritás és az Opportunity Score közös scoring_core.py számítási magot használ, de külön súlyozott dimenziókkal és eltérő üzleti jelentéssel. A Lead prioritás cégek kutatási sorrendjét segíti; az Opportunity Score a több cégnél visszatérő probléma SaaS-megoldásának értékét becsüli. Hiányos dimenzió esetén egyik sem ad végső pontszámot. A régi lead_scoring.py::score_lead csak adatmező-teljességi heurisztika.

## Opportunity Engine – aktuális fejlesztési állapot

A PR #35-ben a C stratégiához illeszkedő első Opportunity Engine-szelet készült el: egyedi céges problémákból indul, több cégen át ismétlődő mintázatokat kapcsol össze, majd SaaS-jelölteket rangsorol. A dashboard az Opportunity Center oldalon biztosítja a céges problémák, piaci mintázatok, SaaS-ötletek, értékelési előnézet és döntési előzmények áttekintését.

**Kódban implementált:**
- forrásolt cégprobléma-hipotézisek confidence és státusz mezőkkel;
- validált piaci mintázat csak legalább két különböző céghez kötött problémával;
- alátámasztásvesztés esetén automatikus `under_review` visszaminősítés;
- SaaS-jelöltek, hatdimenziós súlyozott pontozás és dimenziónkénti rationale/evidence;
- provider-neutral evaluator, explicit előnézet és elégtelen bizonyíték esetén pontozás nélküli kimenet;
- admin/operator által explicit gombnyomással menthető, append-only értékelési előzmény;
- reader read-only hozzáférés, actor attribution, idempotenciakulcs, immutable snapshotok;
- DB triggeres ellenőrzés a szerepkörre, pattern állapotra, két cégre és forrás-egyezésre.

**Nem állítható késznek:** a PR nincs merge-ölve; migrációk production DB-re nem kerültek; nincs production deploy; nincs valós ügyfél-validáció, piaci méret/versenytárs/árazási validáció és unit economics kalibráció. A preview Gemini-hívást indíthat, de önmagában nem ment; mentés csak külön jóváhagyásra történik.

**Következő sorrend:**
1. A PR #35 aktuális HEAD-jéhez tartozó CI eredmény megvárása és review; a lokális tesztfuttatás a felhasználó kérésére elmarad.
2. Az approval migration és az RLS/JWT viselkedés izolált CI-környezetű eredményének áttekintése.
3. A cégdosszié history és Opportunity Center eltérő hozzáférési modelljének dashboard-szintű hibakezelése.
4. Evidence minőségi szabályok és az evaluator dimenziónkénti üzleti kalibrálása.
5. Piaci alternatívák, TAM/SAM/SOM, árképzés és unit economics elemzés, majd emberi ügyfél-validáció.
6. Csak külön engedéllyel staging/production migráció, Auth/RLS éles változtatás vagy deploy.

Részletes adatmodell, score-képlet, forrásmodell és biztonsági szabály: [Opportunity Engine dokumentáció](OPPORTUNITY_ENGINE.md).

## 7. Új fejlesztési fókusz – 2026-11-26

A PR #28 a cégkutatási előzmények read-only dashboardját vezeti be. A navigációs routing hiányát a 2fa7b9410d5cbd49140391a633853ad73d81a1b9 commit javítja. Az új CI elindult; a javítás teljes CI-eredménye még nincs igazolva. A felület Auth esetén fail-closed, nem használ service-role megkerülést.

A háttérmotor DB-független lifecycle, tartós repository/RPC adapter, planner queue bridge, egyszeri injektált worker, bounded exponential retry, explicit heartbeat callback, admission policy, grounded Gemini provider adapter és atomikus budget reservation formájában implementált. A scheduleres automatikus indítás és az élő Gemini/staging futás még nincs bekapcsolva. Production DB, migrációfuttatás, deploy és outbound e-mail továbbra is tiltott külön jóváhagyásig.

A felhasználó kérése szerint a kisebb módosítások után nem állunk meg külön ellenőrzési körre: több összefüggő funkció elkészülte után futtatunk átfogó ellenőrzést.


### 7.1 Háttérmotor első implementációja

A PR #28 ágán már szerepel a company_research_jobs.py tiszta, DB-független job-lifecycle modul és a tests/test_company_research_jobs.py tesztcsomag. Megvalósított elemek: queued/running/retry_wait/succeeded/dead_letter állapotok; stabil operation ID; lease claim és expiry utáni reclaim; tulajdonoshoz kötött heartbeat és completion; véges retry és dead-letter. A tartós tárolás és az atomi RPC claim is implementált; a worker kódja injektált handlerrel futtatható. Scheduleres automatikus indítás még nincs. A kapcsolódó CI #3187 sikeres.


### 7.2 Tartós háttérmotor – repository adapter szerződés

A tartós repository-réteg kódja és a planner-queue híd már hozzáadva a PR #28 branchhez. A szerződés DB-független `CompanyResearchJobRepository` protokollt és injektált Supabase klienst használó adaptert határoz meg. A Supabase adapter nem hozhat létre saját klienst, nem olvashat környezeti service-role secretet, és importáláskor sem kapcsolódhat adatbázishoz.

Kötelező adattárolási invariánsok:
- `operation_id` adatbázis-oldali UNIQUE kulcs; az ismételt create idempotensen a már létező jobot adja vissza.
- A claim, heartbeat, complete és fail műveletek adatbázis-oldali RPC-szerződésen keresztül, egyetlen tranzakcióban és feltételes állapot-/lease-ellenőrzéssel történnek.
- A Python oldali SELECT+UPDATE nem tekinthető atomi claimnek.
- A worker az aktuális, le nem járt lease tulajdonosaként végezhet heartbeatet és lezárást; lejárt vagy lecserélt lease-szel rendelkező worker nem írhatja felül az új tulajdonos állapotát.
- A repository metódusok validált job objektumot adnak vissza, vagy egyértelműen jelzik a konfliktust/nem jogosult állapotot.
- A fake repository tesztek a protokoll és az adapter leképezését ellenőrzik; az SQL/RPC konkurencia-viselkedés külön izolált adatbázis-integrációs tesztet igényel.

Az SQL migration csak verziókezelt repository-fájl lehet. A job tábla belső worker-adat: RLS bekapcsolva, PUBLIC/anon/authenticated hozzáférés tiltva, kizárólag backend service role számára engedélyezett műveletek. A migrationt és RPC-kat production Supabase-re nem alkalmazzuk. Ez a fázis nem tartalmaz scheduler-t, Gemini kutatás-végrehajtást vagy outbound mellékhatást.


A megvalósított fájlok: `company_research_job_repository.py` (Protocol + injektált Supabase RPC adapter), `company_research_refresh_queue.py` (planner jelöltek idempotens jobként sorba állítása), `supabase/migrations/20261126153000_company_research_jobs.sql` (service-role-only job tábla és tranzakciós RPC-kontraktus), valamint fake kliens/repository tesztek. A migration kizárólag repository-fájl, nem lett futtatva. A funkciócsomag elkészülte után lekértük az aktuális head workflow-run és combined-status adatait; mindkettő üres listát adott, ezért a CI eredménye jelenleg nem igazolt.


### 7.3 Egyszeri worker-orchestration

A PR #28 ágán elkészült a `company_research_worker.py`: injektált repositoryból legfeljebb egy előkészített jobot claimel, injektált handlerrel feldolgozza, majd complete vagy bounded fail művelettel lezárja. A grounded Gemini handler adapter implementált, de élő API-hívás és scheduleres automatikus futtatás nincs bekapcsolva. A handler hibáinak szövege nem kerül a job rekordba, csak korlátozott hibakód és általános, titokmentes üzenet. Lejárt lease esetén a worker nem jelenti sikeresnek a műveletet.


### 7.4 Retry backoff finomítása

Következő kódszelet: determinisztikus, exponenciális és felső korláttal védett retry késleltetés. A worker az attempt_count alapján növeli a várakozást, de konfigurált maximum fölé nem léphet; a retry továbbra is bounded, dead-letterbe kerül a limitet elérő job. Ez nem helyettesíti a globális rate limitet vagy költségkeretet.


### 7.5 Kutatási admission policy

A következő egység egy tiszta, DB-független admission döntés: óránkénti globális joblimit, domainenkénti napi limit, párhuzamos joblimit és napi költségkeret ellenőrzése. A költség egész mikro-USD egységben szerepel, lebegőpontos kerekítési hibák nélkül. A policy csak a megadott usage snapshot alapján dönt; tartós számlálást és atomikus foglalást későbbi repository/RPC réteg biztosít.


### 7.6 Hosszú jobok lease-heartbeat támogatása

A worker handler heartbeat callbacket kap. A Gemini provider adapter a hosszú szinkron API-kérés alatt konfigurálható időközönként háttérszálból frissíti a lease-t; hamis heartbeat vagy callback-kivétel esetén a provider eredményét eldobja, és a worker nem complete-olhatja sikeresként.


### 7.7 Admission és költségkeret – első implementáció

Elkészült a `company_research_admission.py` DB-független policy, amely globális óránkénti joblimitet, domainenkénti napi limitet, párhuzamos joblimitet és napi költségkeretet vizsgál egész mikro-USD egységben. A `company_research_refresh_queue.py` új admission-aware enqueue útvonala egyetlen batchen belül frissíti a helyi usage snapshotot, így a batch nem lépi túl saját kvótáját. Több párhuzamos folyamat közötti hard limithez még atomikus DB reservation szükséges; ez a Python policy önmagában nem biztosít globális költségplafont.

A Gemini provider adapter a worker callbackjét leállítható daemon szálból, konfigurálható időközönként hívja a szinkron provider-kérés alatt; a szál a kérés lezárásakor leáll.


### 7.8 Worker- és idempotencia-hardening

A worker most már ellenőrzi a claim válasz alakját, a handler eredményének JSON-kompatibilitását és maximális méretét (alapértelmezésben 256 KiB), másolatot ad a handlernek a payloadból, és a provider által adott hibakódot szűri, hogy titok vagy tetszőleges szöveg ne kerüljön a job állapotába. A repository create művelete az `operation_id` egyezése mellett a `job_type`, `lead_id` és payload egyezését is megköveteli; azonos idempotency key eltérő tartalommal konfliktus. A domain kvótakulcsok kis-/nagybetűtől függetlenül normalizálódnak.

A költségbecsléshez elkészült az `estimate_research_cost_microusd()` egész számú, felfelé kerekítő segédfüggvény. A szolgáltatói tokenárakat a hívó adja át; a kód nem tartalmaz beégetett modellárakat.


### 7.9 Atomikus worker concurrency limit

A claim RPC most már tranzakciós advisory lockkal sorosítja a claim döntéseket, megszámolja az aktív, le nem járt lease-eket, és csak a konfigurált párhuzamossági plafon alatt vesz fel új jobot. A Python repository és az egyszeri worker a `max_concurrent_jobs` értéket átadja az RPC-nek. Ez a korlát a claim műveletnél érvényesül, nem pusztán az enqueue előtti usage snapshotban. A SQL migration repository-fájl marad, production adatbázisra nem futott le; izolált PostgreSQL konkurenciateszt még szükséges.


### 7.10 Atomikus költségfoglalás és tartós worker-audit

A job létrehozása most `company_research_job_create(jsonb,bigint,bigint)` RPC-n keresztül történik. A tranzakció napi UTC budget advisory lockot vesz fel, összeadja az adott nap tartós költségfoglalásait, és a job rekorddal egy tranzakcióban rögzíti az új reservationt. A budget túllépés rögzített, nem érzékeny hibakóddal utasítja el az enqueue-t; a queue ezt `daily_cost_limit` okként jelzi. Az operation ID idempotens újraküldése nem foglal újra költséget.

Elkészült a `company_research_budget_reservations` tábla, valamint az append-only `company_research_job_audit`. A létrehozás, claim, heartbeat, sikeres lezárás, retry/dead-letter és végső lease-expiry események tranzakciósan auditálódnak. Az audit tábla service_role számára SELECT/INSERT jogosultságú; UPDATE/DELETE nincs adva. A reservation előzetesen becsült összeget foglal; az actual-cost extractor és a complete RPC tranzakciós settlementje implementált. Az actual cost meghaladhatja a becslést, ezért a napi hard cap túllépés elleni védelem még fejlesztendő. A globális óránkénti és domain napi limit továbbra is csak a jelenlegi snapshotos admission rétegben érvényesül, nem atomikus DB reservation.

A migration továbbra is csak repository fájl, production DB-re nem lett alkalmazva. Izolált PostgreSQL tranzakciós/konkurenciateszt szükséges a tényleges adatbázis-garancia igazolásához.

A `SupabaseCompanyResearchJobRepository.list_audit()` korlátozott, legfeljebb 1000 eseményt visszaadó, service-role-only RPC olvasási útvonalat is biztosít operation ID szerint. A dashboard még nincs erre az audit streamre rákötve.


### 7.11 Atomikus hourly és domain rate limit

A job-create RPC immár adatbázisoldalon is kikényszeríti a globális óránkénti joblimitet és a domainenkénti napi limitet. A budget-, hourly- és domain-ellenőrzések egy közös tranzakciós advisory lock alatt futnak, az idempotens operation ID visszajátszás pedig a korábbi jobot adja vissza, nem fogyaszt új kvótát. A DB a létrehozási időt maga állítja be, így a kliens nem tud régi `created_at` értékkel kvótát megkerülni. A domain összehasonlítás kis-/nagybetűtől független.

A worker concurrency plafon továbbra is külön, atomikus claim RPC-ben érvényesül. A napi költségkeret becsült költségfoglalással védett; az actual-cost settlement callback és a tranzakciós elszámolás implementált. A becslést meghaladó tényleges költség miatti hard cap túllépés még külön védelemre szorul. Az hourly/domain limit a job létrehozásokat számolja, beleértve a később sikertelen jobokat is.


### 7.12 Tényleges költség elszámolása

A worker opcionális `actual_cost_extractor` callbacket fogad. Ha a provider handler a normalizált, JSON-kompatibilis eredményből tényleges költséget tud számolni, a worker azt nemnegatív egész mikro-USD értékként átadja a complete RPC-nek. A job sikeres lezárása és a reservation `settled` állapotba állítása egy tranzakcióban történik; a becsült foglalást a tényleges költség váltja fel, és az audit esemény is rögzíti az actual cost értéket. Ha nincs extractor, a becsült reservation megmarad, tehát a rendszer konzervatívan számol. A provider adapter kódban be van kötve a worker handlerhez; élő szolgáltatói hívás nélkül valós tokenhasználatot még nem validáltunk.

A régi, snapshot admission nélküli refresh enqueue útvonalat is lezártam: mostantól kötelező megadni a becsült költséget és a limit-konfigurációt, és az adapter ugyanazokat az adatbázisoldali költség/hourly/domain paramétereket küldi be. Így egyik Python enqueue belépési út sem hagyja ki a hard DB kvótákat.


### 7.13 Gemini grounded research execution adapter

Elkészült a `company_research_execution.py` provider adapter rétege. A `GeminiGoogleSearchCompanyResearchProvider` injektált Gemini klienssel és modellel működik, Google Search grounding eszközt kér, legfeljebb három próbálkozással és exponenciális backoff-fal kezeli a tranziensekre korlátozott retry-t. A grounding URL-eket a provider metaadataiból veszi át; a `build_company_dossier` csak az ezekkel egyező hostokról származó tényeket tartja meg. A döntéshozói mezők kizárólag nyilvános szakmai kontextust tartalmazhatnak; privát e-mail és telefonszám nem kerül a dossziéba.

A workerhez `make_company_research_handler()` adapter adható. A Gemini provider adapter a szinkron API-kérés és retry-időszak alatt konfigurálható időközönként háttérszálból frissíti a lease-t. Hamis heartbeat vagy callback-kivétel esetén a provider eredményét eldobja. A provider tokenhasználatot visszaadja, a konfigurált input/output tokenárakból `make_gemini_actual_cost_extractor()` számol mikro-USD actual costot. A tokenárakat a hívó adja meg, nincs beégetett árazás.

Fontos: a Gemini kliens és modell injektált; a modul nem olvas secretet, nem hoz létre klienst, és nem indít önálló API-hívást. A worker→provider→dossier→snapshot→lead→complete/audit kódút implementált és CI-vel tesztelt; valós provider hívás és éles scheduleres futtatás nincs bekapcsolva. Outbound e-mail továbbra is tiltott.

A `company_research_runtime.py` explicit composition root is elkészült: `run_company_research_worker_once()` összeköti az injektált repositoryt, Gemini grounding providert, one-shot workert és konfigurált tokenáras actual-cost extractort. Importkor nem futtat semmit, nem készít klienst vagy secretet; kizárólag explicit függvényhíváskor claimel legfeljebb egy jobot. Scheduler, dashboard trigger és automatikus háttérfuttatás továbbra sincs.


### 7.14 Hosszú Gemini-kérések lease-heartbeat javítása

A Gemini provider adapter most a teljes szinkron API-kérés és retry-időszak alatt periodikusan megújítja a lease-t a worker heartbeat callbackjén keresztül. A heartbeat külön leállítható daemon szálon fut; lease-vesztéskor a provider eredménye nem használható fel. A javítást két célzott teszt fedi, a teljes CI-ellenőrzés az új PR head SHA-ján következik.


## 8. Főrendszer-készültségi felmérés – 2026-11-26

A legfrissebb összesített funkcióleltár, a „kész főrendszer” elfogadási feltételei, valamint a P0/P1/P2 és production release teendők külön dokumentumban szerepelnek: [JARVIS_MAIN_SYSTEM_READINESS.md](JARVIS_MAIN_SYSTEM_READINESS.md). A P1 worker→provider→dossier→snapshot→lead FK→job completion út kódoldali runtime-integrációja és a PostgreSQL worker lifecycle/kvóta/konkurencia tesztek a PR #28 HEAD-en CI-vel igazoltak (Run #3136). Még hátra van a valós Gemini provider smoke, Auth/RLS szerepkörteszt, a teljes helyi manuális dashboard smoke és néhány worker lifecycle peremfeltétel mélyebb SQL-lefedése.


## 9. Dashboard navigációs audit – 2026-11-26

A Chat, Feladatok, Analitika, Cégkutatás, Audit napló és Beállítások navigációs útvonalait áttekintettük. A Settings korábban csak dekoratív HTML volt; most dedikált, kattintható, read-only konfigurációs oldal, titokértékek megjelenítése nélkül. A rendszerdiagnosztika csak kézi indításra fut, és jelzi a Gemini próbakérés lehetséges költségét. Auth módban a Settings settings.read jogosultságot igényel, a teljes diagnosztika admin-only. A runtime titkok, Auth/RBAC, RLS és outbound e-mail zár UI-ból nem módosítható.

A Feladatközpont üres tasklista esetén korábban elrejtette az utánkövetési sort; a korai visszatérést javítottuk és AppTestet adtunk hozzá. A Cégkutatás Auth/RLS módban továbbra is fail-closed, az Audit külön Supabase Auth-admin belépést kér. A dashboard tesztcsomag két Settings teszttel és egy üres tasklista/utánkövetés regressziós teszttel bővült. Az audit utáni új HEAD teljes CI-ellenőrzése még szükséges.


## 8. Központi konfiguráció- és hibakezelés – 2026-11-26

A PR #28 ágán egységes, titokmentes hibakategorizálás készült a `jarvis_errors.py` modulban. A rendszer külön kezeli a hiányzó/hibás konfigurációt, jogosultság- és hitelesítési hibát, API-kvótát/rate limitet, hálózati hibát, timeoutot, átmeneti szolgáltatáskiesést és hibás kérést. A kategóriához magyar, műveleti útmutatót adó üzenet tartozik; a szolgáltatói hiba teljes szövege és a secret nem kerül a chat felületére.

A Gemini kliens a kategorizálás alapján korlátozottan újrapróbálkozik hálózati, timeout, rate limit és átmeneti szolgáltatáshibánál. Hitelesítési és jogosultsági hibára nincs retry vagy másik jogosultsági útvonal. A dashboard chat megőrzi a megállási szakaszt, de a felhasználónak csak biztonságos, kategorizált segítséget mutat. A titokmentes naplózás továbbra is best-effort; naplózási hiba nem írhatja felül az eredeti hibát.

A hozzáadott tesztek lefedik a hibakategóriákat, a secret UI-ból való kizárását, a hálózati retryt és az auth/permission fail-closed viselkedést. A teljes CI-t az összefüggő fejlesztési csomag lezárásakor kell futtatni; az implementáció önmagában még nem jelent zöld CI-t. Production konfiguráció, DB, jogosultság, secret és infrastruktúra nem módosult.


Történeti CI-hibajegyzet: a #3019 két AppTest elvárása később javítva lett. A frissebb PR #28 HEAD CI #3187 mindhárom jobja sikeres; a korábbi hiba nem aktuális blokkoló.


## 9. Következő munka és ellenőrzési terv – 2026-11-26

A felhasználói tesztelési elvárás szerint nem ismételjük meg minden commit után a teljes, már korábban igazolt tesztcsomagot. A célzott tesztelési szabályokat és a még hiányzó ellenőrzéseket a [JARVIS_REMAINING_WORK_REPORT.md](JARVIS_REMAINING_WORK_REPORT.md) tartalmazza.

A konfigurációs és runtime hibakezelési kód bekerült: hiányzó/hibás kötelező secret, hibás Supabase HTTP(S) URL, hálózati hiba, timeout, API rate limit/kvóta, szolgáltatáskiesés, hitelesítési és jogosultsági hiba kategorizálása. A Gemini modellváltás kizárólag rate-limit/szolgáltatás-túlterhelés esetén engedélyezett; hitelesítési és permission hiba esetén nincs fallback. A felhasználói felület kategorizált, titokmentes segítséget mutat.

Történeti CI #3019 összefoglaló; ezt a hibát a későbbi commitok javították. A jelenlegi dokumentációs referencia a PR #28 HEAD CI #3187, amely teljesen sikeres.


### 7.9 PostgreSQL worker konkurencia- és kvótatesztek

A PR #28 ágon elkészült két új SQL tesztfájl, de futtatási eredmény még nincs:
- `supabase/tests/company_research_jobs.test.sql`: 15 pgTAP assertion az idempotenciára, napi költségfoglalásra, óránkénti/domain kvótára, claim plafonra, heartbeat-re, actual-cost settlementre és auditra.
- `supabase/tests/company_research_jobs_concurrency.test.sql`: 14 pgTAP assertion két független `dblink` PostgreSQL sessionnel. Valódi párhuzamos budget reservation és párhuzamos worker claim versenyt indít.

Következő lépés: a helyi Supabase/PostgreSQL elindítása után `supabase test db` futtatása izolált környezetben, majd az esetleges hibák javítása és az eredmény commit SHA-hoz kötött dokumentálása. A concurrency teszthez `dblink` extension kell. A production DB-n sem tesztet, sem migrációt nem futtatunk. A jelenlegi napi keret a becsült költséget foglalja le, majd a tényleges költséget könyveli; alulbecslés esetén a tényleges költés meghaladhatja a becsült keretet, ezért a valódi hard cap külön tervezési feladat.


## Aktuális állapot – 2026-11-26, CI #3121

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
2. **[KÉSZ – CI #3136, izolált PostgreSQL 17]** `company_research_jobs_lifecycle_edges.test.sql`: 20/20 lifecycle/kvóta assertion; `company_research_jobs_security.test.sql`: 12/12 security assertion; `company_research_jobs_concurrency.test.sql`: 14/14 valódi, két `dblink` sessionnel futó konkurencia assertion; a snapshot-tároló SQL teszt is sikeres. A futtatás kizárólag eldobható CI-adatbázisban történt.
3. Worker lifecycle teljesítése/tesztelése: lease expiry és reclaim, heartbeat, párhuzamos claim és concurrency plafon, retry/dead-letter, idempotencia, óránkénti/napi/domain kvóták, actual-cost settlement és audit tranzakció.
4. Auth/RLS izolált szerepkörtesztek: reader/admin, valós JWT, RPC, service-role kizárólag trusted server oldalon; fail-closed és nincs jogosultsági fallback.
5. Valódi Google GenAI SDK/izolált staging integrációs próba: 429, 503, timeout, auth, grounding metadata, usage/cost és retry/heartbeat; production kulcs és production DB nélkül.
6. Teljes helyi manuális dashboard smoke: Chat, Feladatok, Analitika, Cégkutatás, Audit, Beállítások; üres adat, hiányzó/hibás konfiguráció, hálózat, kvóta és permission állapotok.
7. Chat gyorsműveletek valódi kattintható műveletté alakítása; user preference mentés csak jóváhagyott adattárolási modell alapján, a titkok és biztonsági zárak változtathatatlanul hagyásával.

**P2 – későbbi terméképítési szakasz:** scheduler/automatikus háttérkutatás; SaaS-ötletmotor és piaci alternatívaelemzés; globális és cégenkénti tiltó/ütközésnapló; ajánlatgenerálás és outreach workflow; jogszerű marketing-hozzájárulás/suppression modell; outbound e-mail külön engedélyezés után; AI-assisted termékfejlesztés és build/test/release pipeline.

### PR és környezeti állapot

PR #26, #27 és #28 merge-ölve a main ágba; a stacked PR-lánc lezárult. A JARVIS app helyi fejlesztés alatt van, nincs production app-host/deploy. A production DB-n nem történt módosítás; nincs production migration, deploy, secret-változtatás vagy e-mailküldés. A dokumentált CI nem jelent production readiness-t.


### 7.8 Worker SQL-életciklus szélső esetei – 2026-11-26

A korábbi 15 lifecycle/kvóta és 14 konkurencia assertion mellé új, 20 assertionös izolált PostgreSQL pgTAP csomag készült: `supabase/tests/company_research_jobs_lifecycle_edges.test.sql`. Lefedi az expired lease reclaimet és tulajdonosváltást, a régi worker heartbeat/complete tiltását, retry_wait átmenetet, max-attempt dead-lettert, végső próbálkozás utáni lease-expiry dead-lettert, valamint az UTC napi budget rollover viselkedését. A teszt bekerült a PostgreSQL 17 CI jobba és a migration-contract teszt is ellenőrzi a CI bekötést. A commit elkészült; a tényleges pgTAP futási eredmény az új head CI-jéhez kötött, addig nem tekintjük igazoltnak.


### 7.9 Worker RPC / RLS jogosultsági tesztek – 2026-11-26

Az előző lifecycle-edge csomag mellé elkészült a `supabase/tests/company_research_jobs_security.test.sql` 10 pgTAP assertionnel. Ellenőrzi a három worker tábla RLS-bekapcsolását, az anon és authenticated közvetlen táblaelérésének tiltását, a service_role szükséges és korlátozott táblajogosultságait, a hat worker RPC kizárólag service_role általi futtathatóságát, valamint az audit append-only jogosultsági határait. A PostgreSQL 17 CI job futtatja, a Python migration-contract teszt pedig ellenőrzi a CI bekötést. A tényleges futási eredmény az új head CI-jéhez kötött.


### 7.10 Gemini SDK és Auth/RLS regressziós tesztek – 2026-11-26

A Gemini hibakezelési tesztek kiegészültek a Google GenAI SDK tényleges `ClientError`/`ServerError` kivételosztályaival: 429 RESOURCE_EXHAUSTED, 503 UNAVAILABLE, 504 DEADLINE_EXCEEDED, 403 PERMISSION_DENIED, 400 API_KEY_INVALID és 500 INTERNAL. A generate_text tesztek ellenőrzik a valós SDK-kivétel retry viselkedését, valamint hogy auth/permission hibánál nincs retry. A tesztek mockolt model klienssel futnak, élő API-hívás nélkül; mockolt HTTP transport még nincs bekötve.

Az Auth tesztek külön ellenőrzik, hogy a tárolt kliensoldali role és a user_metadata role nem írhatja felül a frissen lekért, szerveroldali app_metadata role-t, és hogy nem megerősített fiókkal a refreshelt session is elutasításra kerül. A worker security pgTAP csomag 12 assertionre bővült: a snapshot history RLS-ét, publikus role-ok kizárását és service_role append-only jogosultságát is ellenőrzi. Az új futások eredménye a friss CI-hez kötött.


## Aktuális státusz felülvizsgálata – 2026-11-26

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


## Intelligence Graph – új fejlesztési réteg

A PR #35 branch tartalmazza a `intelligence_entities` és `intelligence_relationships` származtatott gráftáblákat, forrásrekordokat szinkronizáló triggeres karbantartást, idempotens backfillt, a `intelligence_graph.py` bounded Graphviz projection modult és az Opportunity Center új **Intelligence Graph** fülét. A gráf a meglévő üzleti rekordokat köti össze, nem helyettesíti azokat. A Python tesztek 9 esetet, a pgTAP teszt 24 assertiont fed le; a teszteket helyben a felhasználó kérésére nem futtattuk. A CI push után automatikusan indul. Részletek: [Intelligence Graph](INTELLIGENCE_GRAPH.md).
