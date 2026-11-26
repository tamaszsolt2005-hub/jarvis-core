# JARVIS – aktuális állapot és következő lépések

**Frissítve:** 2026-11-26  
**Aktív fejlesztési ág:** `feature/company-research-dashboard-readonly`  
**Aktuális PR:** [#28 – nyitott, nem merge-ölt](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/28)  
**Alap PR:** [#26 – nyitott, nem merge-ölt](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26)  
**Aktuális head és CI:** mindig a [PR #28 aktuális headjén és Checks oldalán](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/28/checks) ellenőrizendő. Csak az aktuális headhez tartozó, befejezett és sikeres futás tekinthető igazolásnak; régebbi futás nem.

A teljes összefüggő leírás: [JARVIS Master Documentation](JARVIS_MASTER_DOCUMENTATION.md).

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

1. A jelenlegi PR #27 CI-jének befejeződése és minden hiba javítása az aktuális headen.
2. A dokumentált snapshot migráció és store kód további ellenőrzése.
3. A read-only planner bekötése lapozott lead- és snapshot-lekérdezéshez, majd tesztelés nagy adathalmazon.
4. Megbízható outreach eseményszámláló és állapotmapping a follow-up policy-hoz.
5. Idempotens, jóváhagyott ütemezésű kutatási worker.
6. Kutatási UI és emberi ellenőrzés.
7. Ezután üzleti problémahipotézis és SaaS-ötletmotor.

## 6. Változtatási és biztonsági határok

- PR #26 és #27 nem merge-ölhető külön explicit jóváhagyás nélkül.
- Production Supabase DDL/DML, migration, GRANT/REVOKE, Auth/RBAC, secret és infrastruktúra módosítása tilos külön engedély nélkül.
- Production deploy és outbound e-mail küldés nincs engedélyezve.
- CI zöld státusza csak az adott SHA-ra és az adott tesztkörnyezetre érvényes.


## 7. Új fejlesztési fókusz – 2026-11-26

A PR #28 a cégkutatási előzmények read-only dashboardját vezeti be. A navigációs routing hiányát a 2fa7b9410d5cbd49140391a633853ad73d81a1b9 commit javítja. Az új CI elindult; a javítás teljes CI-eredménye még nincs igazolva. A felület Auth esetén fail-closed, nem használ service-role megkerülést.

A háttérmotor DB-független lifecycle, tartós repository/RPC adapter, planner queue bridge, egyszeri injektált worker, bounded exponential retry, explicit heartbeat callback, admission policy és tokenköltség-becslés formájában már megvalósult a PR #28 ágán. A scheduler, tényleges kutatási handler, Gemini-hívás és atomikus globális budget reservation még nincs implementálva. Production DB, migrációfuttatás, deploy és outbound e-mail továbbra is tiltott külön jóváhagyásig.

A felhasználó kérése szerint a kisebb módosítások után nem állunk meg külön ellenőrzési körre: több összefüggő funkció elkészülte után futtatunk átfogó ellenőrzést.


### 7.1 Háttérmotor első implementációja

A PR #28 ágán már szerepel a company_research_jobs.py tiszta, DB-független job-lifecycle modul és a tests/test_company_research_jobs.py tesztcsomag. Megvalósított elemek: queued/running/retry_wait/succeeded/dead_letter állapotok; stabil operation ID; lease claim és expiry utáni reclaim; tulajdonoshoz kötött heartbeat és completion; véges retry és dead-letter. A tartós tárolás és az atomi RPC claim későbbi kódszeletekkel már előkészített; scheduler és tényleges kutatási végrehajtás még nincs. A kapcsolódó teszteket a következő összesített ellenőrzési körben futtatjuk.


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

A PR #28 ágán elkészült a `company_research_worker.py`: injektált repositoryból legfeljebb egy előkészített jobot claimel, injektált handlerrel feldolgozza, majd complete vagy bounded fail művelettel lezárja. Nincs beépített kutatási handler, Gemini/API-hívás, scheduler vagy automatikus futtatás. A handler hibáinak szövege nem kerül a job rekordba, csak korlátozott hibakód és általános, titokmentes üzenet. Lejárt lease esetén a worker nem jelenti sikeresnek a műveletet.


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

Elkészült a `company_research_budget_reservations` tábla, valamint az append-only `company_research_job_audit`. A létrehozás, claim, heartbeat, sikeres lezárás, retry/dead-letter és végső lease-expiry események tranzakciósan auditálódnak. Az audit tábla service_role számára SELECT/INSERT jogosultságú; UPDATE/DELETE nincs adva. A reservation az előzetesen becsült összeget foglalja; tényleges provider-költség elszámolása és visszatérítés még nincs bekötve. A globális óránkénti és domain napi limit továbbra is csak a jelenlegi snapshotos admission rétegben érvényesül, nem atomikus DB reservation.

A migration továbbra is csak repository fájl, production DB-re nem lett alkalmazva. Izolált PostgreSQL tranzakciós/konkurenciateszt szükséges a tényleges adatbázis-garancia igazolásához.

A `SupabaseCompanyResearchJobRepository.list_audit()` korlátozott, legfeljebb 1000 eseményt visszaadó, service-role-only RPC olvasási útvonalat is biztosít operation ID szerint. A dashboard még nincs erre az audit streamre rákötve.


### 7.11 Atomikus hourly és domain rate limit

A job-create RPC immár adatbázisoldalon is kikényszeríti a globális óránkénti joblimitet és a domainenkénti napi limitet. A budget-, hourly- és domain-ellenőrzések egy közös tranzakciós advisory lock alatt futnak, az idempotens operation ID visszajátszás pedig a korábbi jobot adja vissza, nem fogyaszt új kvótát. A DB a létrehozási időt maga állítja be, így a kliens nem tud régi `created_at` értékkel kvótát megkerülni. A domain összehasonlítás kis-/nagybetűtől független.

A worker concurrency plafon továbbra is külön, atomikus claim RPC-ben érvényesül. A napi költségkeret a becsült költségfoglalás alapján védett; tényleges provider usage elszámolása és vissza nem használt foglalás felszabadítása még nincs bekötve. Az hourly/domain limit a job létrehozásokat számolja, beleértve a később sikertelen jobokat is.


### 7.12 Tényleges költség elszámolása

A worker opcionális `actual_cost_extractor` callbacket fogad. Ha a provider handler a normalizált, JSON-kompatibilis eredményből tényleges költséget tud számolni, a worker azt nemnegatív egész mikro-USD értékként átadja a complete RPC-nek. A job sikeres lezárása és a reservation `settled` állapotba állítása egy tranzakcióban történik; a becsült foglalást a tényleges költség váltja fel, és az audit esemény is rögzíti az actual cost értéket. Ha nincs extractor, a becsült reservation megmarad, tehát a rendszer konzervatívan számol. A provider adapter még nincs bekötve, ezért valós tokenhasználatot jelenleg nem mérünk.

A régi, snapshot admission nélküli refresh enqueue útvonalat is lezártam: mostantól kötelező megadni a becsült költséget és a limit-konfigurációt, és az adapter ugyanazokat az adatbázisoldali költség/hourly/domain paramétereket küldi be. Így egyik Python enqueue belépési út sem hagyja ki a hard DB kvótákat.


### 7.13 Gemini grounded research execution adapter

Elkészült a `company_research_execution.py` provider adapter rétege. A `GeminiGoogleSearchCompanyResearchProvider` injektált Gemini klienssel és modellel működik, Google Search grounding eszközt kér, legfeljebb három próbálkozással és exponenciális backoff-fal kezeli a tranziensekre korlátozott retry-t. A grounding URL-eket a provider metaadataiból veszi át; a `build_company_dossier` csak az ezekkel egyező hostokról származó tényeket tartja meg. A döntéshozói mezők kizárólag nyilvános szakmai kontextust tartalmazhatnak; privát e-mail és telefonszám nem kerül a dossziéba.

A workerhez `make_company_research_handler()` adapter adható. A Gemini provider adapter a szinkron API-kérés és retry-időszak alatt konfigurálható időközönként háttérszálból frissíti a lease-t. Hamis heartbeat vagy callback-kivétel esetén a provider eredményét eldobja. A provider tokenhasználatot visszaadja, a konfigurált input/output tokenárakból `make_gemini_actual_cost_extractor()` számol mikro-USD actual costot. A tokenárakat a hívó adja meg, nincs beégetett árazás.

Fontos: a Gemini kliens és modell injektált; a modul nem olvas secretet, nem hoz létre klienst, és nem indít önálló API-hívást. A worker/queue/dashboard éles összekötése, valós provider hívás, DB snapshot mentés és valódi tokenköltség mérés még nincs bekapcsolva. Outbound e-mail továbbra is tiltott.

A `company_research_runtime.py` explicit composition root is elkészült: `run_company_research_worker_once()` összeköti az injektált repositoryt, Gemini grounding providert, one-shot workert és konfigurált tokenáras actual-cost extractort. Importkor nem futtat semmit, nem készít klienst vagy secretet; kizárólag explicit függvényhíváskor claimel legfeljebb egy jobot. Scheduler, dashboard trigger és automatikus háttérfuttatás továbbra sincs.


### 7.14 Hosszú Gemini-kérések lease-heartbeat javítása

A Gemini provider adapter most a teljes szinkron API-kérés és retry-időszak alatt periodikusan megújítja a lease-t a worker heartbeat callbackjén keresztül. A heartbeat külön leállítható daemon szálon fut; lease-vesztéskor a provider eredménye nem használható fel. A javítást két célzott teszt fedi, a teljes CI-ellenőrzés az új PR head SHA-ján következik.


## 8. Főrendszer-készültségi felmérés – 2026-11-26

A legfrissebb összesített funkcióleltár, a „kész főrendszer” elfogadási feltételei, valamint a P0/P1/P2 és production release teendők külön dokumentumban szerepelnek: [JARVIS_MAIN_SYSTEM_READINESS.md](JARVIS_MAIN_SYSTEM_READINESS.md). Röviden: a lead → scoring → task approval → PostgreSQL → audit E2E és a `36d615f` core commit teljes CI-je sikeres. A dashboard navigációs audit és read-only Settings oldal elkészült, de az ezt követő aktuális HEAD CI-je, a valós Auth/RLS hozzáférés, a worker SQL konkurencia és a kutatási snapshot E2E, valamint a teljes helyi smoke még nem tekinthető igazoltnak. Emiatt a főrendszer még nem minősíthető késznek.


## 9. Dashboard navigációs audit – 2026-11-26

A Chat, Feladatok, Analitika, Cégkutatás, Audit napló és Beállítások navigációs útvonalait áttekintettük. A Settings korábban csak dekoratív HTML volt; most dedikált, kattintható, read-only konfigurációs oldal, titokértékek megjelenítése nélkül. A rendszerdiagnosztika csak kézi indításra fut, és jelzi a Gemini próbakérés lehetséges költségét. Auth módban a Settings settings.read jogosultságot igényel, a teljes diagnosztika admin-only. A runtime titkok, Auth/RBAC, RLS és outbound e-mail zár UI-ból nem módosítható.

A Feladatközpont üres tasklista esetén korábban elrejtette az utánkövetési sort; a korai visszatérést javítottuk és AppTestet adtunk hozzá. A Cégkutatás Auth/RLS módban továbbra is fail-closed, az Audit külön Supabase Auth-admin belépést kér. A dashboard tesztcsomag két Settings teszttel és egy üres tasklista/utánkövetés regressziós teszttel bővült. Az audit utáni új HEAD teljes CI-ellenőrzése még szükséges.
