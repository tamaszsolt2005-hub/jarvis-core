# JARVIS – központi projekt- és műszaki dokumentáció

**Dokumentációs verzió:** 2026-11-26  
**Érvényességi kör:** a `feature/company-research-dashboard-readonly` branch aktuális kódja és a PR #28 (a #27-re épülő stacked PR)  
**Pull request:** [#28 – nyitott, nem merge-ölt](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/28)  
**Alap / stacked PR:** [#26 – nyitott, nem merge-ölt](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26)

> Ez a dokumentum a jelenlegi fejlesztési állapot és a hosszú távú cél közötti különbséget egyértelműen kezeli. A „kódban van”, „CI-ben tesztelt”, „külső integrációval igazolt” és „productionben aktív” külön státuszok. A dokumentáció önmagában nem jelent engedélyt adatbázis-módosításra, deployra vagy külső kapcsolatfelvételre.

## 1. Mi a JARVIS?

A JARVIS egy magyar nyelvű, Streamlit-alapú üzleti asszisztens, amely jelenleg helyi fejlesztés alatt áll. A meglévő rendszer chatet, leadkutatást, lead scoringot, jóváhagyásos task-kezelést, üzleti memóriát, napi briefinget, analitikát és auditfunkciókat tartalmaz.

A hosszú távú cél egy kutatásvezérelt üzleti ügynök: a JARVIS önállóan releváns cégeket talál, nyilvános és ellenőrizhető forrásokból megérti a működésüket, azonosítja a lehetséges üzleti problémákat, majd minden céghez egyedi AI/SaaS termékkoncepciót javasol. A rendszer a korábbi elutasítások és termékütközések alapján tanul, személyre szabott ajánlatot készít, és csak emberi jóváhagyási kapuk után léphet kapcsolatfelvétel vagy termékfejlesztés felé.

**Alapelv:** előbb értsük meg a céget és a problémáját, utána válasszunk terméket. Nem minden cégnek ugyanazt a SaaS-t kell ajánlani.

## 2. Jelenlegi fejlesztési és release státusz

| Terület | Jelenlegi állapot | Mit nem jelent |
|---|---|---|
| Streamlit dashboard | Helyi fejlesztés | Nincs JARVIS production app vagy app-host |
| Gemini chat és üzleti kontextus | Kódban implementált | API-konfiguráció és helyi környezet szükséges |
| Leadkutatás | Explicit indítású, grounding-alapú kutatás | Nem folyamatos autonóm worker |
| Cégdosszié | Grounding-domainhez kötött tények és szakmai döntéshozói kontextus | Nem korlátlan személyes adatgyűjtés |
| Snapshot verziózás | Tárolómodul és repository migráció elkészült | Production adatbázisra nincs alkalmazva |
| Kutatási frissítési szabály | Tiszta, tesztelhető policy modul | Nincs scheduler/worker bekötve |
| Task és approval | Jóváhagyásos működési útvonal | Nem jelent automatikus végrehajtási jogosultságot minden műveletre |
| Follow-up queue | Read-only, consent-aware | Nem küld e-mailt |
| Outbound email | Hard-disabled | Semmilyen dokumentum nem engedélyezi a küldést |
| SaaS-ötletmotor és tiltó napló | Célarchitektúra | Még nincs megvalósítva |
| AI-termékfejlesztési pipeline | Célarchitektúra | Nincs automatikus projektindítás |
| Production Supabase | Külön létező projekt, korábbi read-only auditokkal | A jelenlegi feature migrációk nincsenek oda telepítve |

A PR #28 a #27-re, a #27 pedig a #26-ra épülő stacked pull request. Integrálásuk sorrendje: #26, #27, #28. Egyik PR sincs merge-ölve. A CI státuszt mindig a PR aktuális head SHA-ján kell ellenőrizni; korábbi zöld futás nem igazolja az újabb commitokat.

## 3. Jelenlegi architektúra – fő komponensek

### 3.1 Felhasználói felület és chat
- `dashboard.py`: Streamlit felület és routing.
- Gemini-alapú magyar nyelvű válaszgenerálás és korlátozott beszélgetési kontextus.
- A természetes nyelvű javaslat nem egyenlő adatbázis-művelettel.
- Az explicit műveleti parancsok parseren és jóváhagyási folyamaton keresztül haladnak.

### 3.2 Leadkutatás és cégazonosítás
- `global_lead_research.py`: explicit kérésre indított, grounding-alapú céges kutatás.
- Legfeljebb 15 új cég mentése egy kutatási futásban.
- Forrás- és domainellenőrzés, strukturált üzleti tények és nyilvános szakmai döntéshozói kontextus.
- `lead_identity.py` és az adatbázis RPC biztosítja a cégazonosítás/deduplikáció közös útját.
- A kutatás nem ad kapcsolatfelvételi engedélyt.

### 3.3 Cégdosszié és verziózott kutatási előzmény
- `company_dossier.py`: engedélyezett ténykategóriák, URL-validálás, grounding domain ellenőrzés, dossziébélyegzés, hash és frissességi szabály.
- `company_research_store.py`: UUID, időbélyeg és SHA-256 tartalomlenyomat ellenőrzése; snapshot insert és korlátozott történetlekérdezés.
- `supabase/migrations/20261126140000_company_research_snapshot_history.sql`: append-only snapshot tábla, RLS és backend-only grant.
- A lead notes mező rövid összefoglalóként marad; a teljes dosszié külön snapshot rekordba kerül.
- A migráció repository/CI szintű artefaktum; productionben nem futott le.

### 3.4 Kutatási frissítési jogosultság
A `company_research_policy.py` read-only döntést ad arról, hogy egy lead alkalmas-e automatikus kutatási frissítésre. A `company_research_refresh_planner.py` ezt a szabályt a snapshot frissességével kombinálja, és rendezett, limitált jelöltlistát állít elő.

| Lead helyzete | Kutatási frissítés |
|---|---|
| Még nem kerestük meg | Jogosult lehet |
| Még nem kapott választ, de 2-nél kevesebb follow-up történt | Jogosult lehet |
| Legalább 2 rögzített, válasz nélküli follow-up | Szüneteltetve |
| Kifejezett elutasítás | Kizárva |
| Opt-out / do-not-contact | Kizárva |
| Érdeklődő vagy későbbi egyeztetést kérő válasz | Felülvizsgálatra jogosult |
| Nem besorolt bejövő válasz | Nem tekinthető automatikusan hallgatásnak |

A „nem válaszolt” és a „nem érdekli” külön állapot. A két utánkövetéses küszöb jelenleg policy-szabály, nem a teljes CRM pipeline-ba integrált automatizmus. A follow-up számlálás csak megbízhatóan rögzített, ténylegesen elküldött eseményekből történhet. A még meg nem keresett lead kutatható, de ettől nem válik jogszerűvé vagy engedélyezetté a kapcsolatfelvétel.

A frissítés elsődleges célcsoportja:
1. még meg nem keresett, releváns leadek;
2. kutatott, de ajánlat-előkészítés előtt álló cégek;
3. érdeklődő vagy későbbi kapcsolatfelvételt kérő cégek;
4. aktív lehetőségek, ahol az új információ érdemben módosíthatja az ajánlatot.

### 3.5 Task, memória, analitika és audit
- Task create/update/close explicit approval flow-val.
- Read-only task center és consent-aware follow-up queue.
- Eredménymérési taskok explicit pozitív/negatív/nincs válasz kategóriával.
- Üzleti memória explicit mentési/listázási/inaktiválási parancsokkal.
- Napi briefing, analitika és audit adminisztráció.

## 4. Kutatási dosszié – adatminőség és adatvédelem

A megőrzött tények engedélyezett kategóriákhoz kötöttek: üzleti modell, termékek/szolgáltatások, ügyfélszegmensek, piacok, növekedési jelzések, technológiai jelzések, működési folyamatok, vezetés és nyilvános hírek.

Követelmények:
- A tények forrás URL-je csak ellenőrzött grounding domainhez kapcsolódhat.
- A hiányzó adat „ismeretlen”, nem szabad kitalálni.
- A tény, a következtetés és a hipotézis különüljön el.
- A döntéshozói adatok kizárólag nyilvános, szakmai és az üzleti célhoz szükséges információk lehetnek.
- Privát e-mail, telefon, családi/egészségügyi/vallási/politikai és más érzékeny adat nem cél és nem kerülhet a dossziéba.
- A webes tartalom adat, nem utasítás; prompt injection ellen védekezni kell.
- A dosszié frissessége önmagában nem jelent újrakutatási ütemezést.

## 5. Cégkutatási frissítési életciklus – tervezett működés

A későbbi workernek:
1. korlátozott batchben lekérdeznie a frissítésre jogosult leadeket;
2. kizárnia az elutasított, opt-out és inaktív, válasz nélkül maradt cégeket;
3. a `company_research_refresh_planner.py` segítségével a stale policy és kizárási szabályok metszetéből kiválasztania a frissítendő dossziékat;
4. idempotens claim/lease mechanizmussal lefoglalnia a munkát;
5. heartbeat, retry limit, dead-letter és operation ID mellett futtatnia a kutatást;
6. költség-, domain-rate- és időkorlátokat betartania;
7. a teljes új snapshotot append-only módon mentenie;
8. változásösszefoglalót és forrásokat adnia emberi ellenőrzésre;
9. auditálnia a sikert, hibát és kihagyás okát.

A planner továbbra is tiszta, read-only jelöltkiválasztó. A PR #28 ág már tartalmazza a tartós job repository/RPC adaptert, queue bridge-et és egyszeri injektált workert lease/heartbeat/retry támogatással. A planner DB-lekérdezésének integrációja, scheduler, tényleges kutatási handler és automatikus refresh még nincs implementálva vagy bekapcsolva.

## 6. Hosszú távú SaaS ajánlási folyamat

A tervezett folyamat cégenként több termékkoncepciót állít elő. Minden ötletet magyarázhatóan értékel:
- probléma bizonyítottsága;
- várható üzleti érték;
- céghez és folyamataihoz való illeszkedés;
- technikai megvalósíthatóság;
- meglévő piaci alternatívák és differenciálás;
- adatvédelmi, szabályozási és biztonsági kockázat;
- fejlesztési és fenntartási költség;
- újrahasznosíthatóság más ügyfelek számára.

Ha a bizonyíték kevés, a helyes válasz a további kutatás vagy az, hogy jelenleg nincs ajánlható ötlet. A rendszer nem kényszeríthet ki ajánlást.

### 6.1 „Mit ne ajánljunk” napló
Kötelező célfunkció, még nem implementált. Külön kell tárolni:
- globálisan tiltott termékkoncepciók;
- egy adott cégnél elutasított ajánlatok;
- korábban elvetett ötletek és indokok;
- jogi/technikai/piaci kizárások;
- már meglévő vagy ügyfél által használt megoldások;
- ügyfélközi kizárólagossági vállalások;
- csak új bizonyíték vagy felülvizsgálat után újranyitható ötletek.

Ajánlás előtt determinisztikus fingerprint- és szemantikus hasonlóságvizsgálat szükséges a tiltó napló, a korábbi ajánlatok, az aktív projektek és a termékkatalógus ellen. A tiltás feloldása auditált és jogosultság-ellenőrzött művelet legyen.

## 7. Ajánlat, kapcsolatfelvétel és fejlesztés – kötelező kapuk

A személyre szabott ajánlat kizárólag a cég valós, forrásolt üzleti helyzetére épülhet. Nem állíthat hamis személyes kapcsolatot, nem igazolt ROI-t, nem létező integrációt vagy kész terméket.

Kapcsolatfelvétel előtt külön ellenőrizendő:
- címzett adatának eredete;
- országonkénti jogalap és marketingkövetelmény;
- consent/opt-out/suppression;
- gyakorisági és küldési limitek;
- emberi jóváhagyás.

**A nyilvános e-mail-cím nem jelent automatikus marketingengedélyt. Az outbound email jelenleg hard-disabled.**

Az érdeklődés nem megrendelés. Termékfejlesztés csak elfogadott scope, írásos szerződés/megrendelés, adatkezelési és tulajdonjogi feltételek, elfogadási kritériumok és külön belső projektindítási jóváhagyás után kezdődhet.

## 8. Biztonsági és működési invariánsok

- Külső mellékhatás előtt explicit, az adott műveletre szóló jóváhagyás szükséges.
- Audit és idempotencia minden érzékeny írási úton.
- Fail-closed működés bizonytalan jogosultság vagy adat esetén.
- Nincs automatikus outbound e-mail, szerződés, árazási ígéret vagy fejlesztésindítás.
- Production DB, Auth/RBAC, secret, deploy és backup infrastruktúra nem módosítható külön engedély nélkül.
- PR merge külön engedélyt igényel.
- A branch migrációi csak CI/tesztkörnyezetben futtathatók automatikusan; production alkalmazásuk külön döntés.
- Titok, token, connection string és érzékeny személyes adat nem kerülhet Gitbe vagy dokumentációba.

## 9. Fejlesztési roadmap és elfogadási feltételek

### Phase 0 – meglévő alap stabilizálása
Chat, lead, task, memória, audit, jogosultság és CI megbízhatóságának fenntartása.

### Phase 1 – cégkutatás
**Részben implementált:** grounding-alapú cégkutatás, cégdosszié, forrásellenőrzés, snapshot metadata/hash, append-only snapshot store, frissességi és refresh-eligibility policy.

**Hátravan:** a planner DB-lekérdező integrációja és teljes worker/scheduler, lease/heartbeat/dead-letter, a follow-up állapotok megbízható integrációja a policy-ba, kutatási UI, költség/rate limit és emberi review.

Elfogadás: nincs duplikáció; minden tény forrásolt; elutasított/opt-out lead nem kerül automatikus refreshbe; két igazolt, válasz nélküli follow-up után szünetel; a még meg nem keresett lead kutatható; nincs outreach mellékhatás.

### Phase 2 – problémahipotézis és SaaS-ötletmotor
Több egyedi ötlet, magyarázható pontozás, bizonyítékok, alternatívák és bizonytalanság.

### Phase 3 – globális és cégenkénti termék-tiltó napló
Fingerprint, hasonlóság, scope, ok, audit, feloldási folyamat.

### Phase 4 – ajánlati csomag és személyre szabott tervezet
Forrásolt állítások, emberi ellenőrzés, jogalap és suppression gate; küldés továbbra is tiltott, amíg külön engedélyezett fejlesztési fázis nem készül.

### Phase 5 – válaszkezelés és értékesítési pipeline
Érdeklődés, elutasítás, későbbi kapcsolatfelvétel, leiratkozás és no-response külön kezelése.

### Phase 6 – szerződött AI-assisted termékfejlesztés
Scope, szerződés, belső jóváhagyás, specifikáció, architektúra, kód, teszt, security review, átadás.

### Phase 7 – eredménymérés és tanulás
Ajánlatok, elutasítások, termékhasználat, költség és ügyfélérték visszacsatolása.

## 10. Tesztelés és helyi futtatás

Helyi indítás:
```bash
python -m pip install -r requirements.txt
streamlit run dashboard.py --server.port 8501
```

Tesztfüggőségek és tesztek:
```bash
python -m pip install -r requirements-test.txt
python -m compileall -q .
python -m pytest -q
```

Az adatbázis-migrációs és pgTAP teszteket a GitHub Actions CI izolált PostgreSQL környezetben futtatja. A CI zöld eredménye nem bizonyít production telepítést vagy külső szolgáltatói működést.

## 11. Dokumentumtérkép

- [Aktuális állapot és következő lépések](CURRENT_STATE_AND_NEXT_STEPS.md)
- [Fejlesztési útiterv](JARVIS_DEVELOPMENT_ROADMAP.md)
- [Rendszer- és architektúra-dokumentáció](JARVIS_DOCUMENTATION.md)
- [Önálló SaaS-ügynök vízió](JARVIS_AUTONOMOUS_SAAS_VISION.md)
- [Parancs- és kifejezéskalauz](JARVIS_COMMAND_GUIDE.md)
- [Fejlesztési backlog](DEVELOPMENT_REVIEW_AND_RECOMMENDATIONS.md)
- [Release gate-ek](REMAINING_WORK_AND_RELEASE_GATES.md)
- [Production állapot és migrációs terv](PRODUCTION_STATE_AND_MIGRATION_PLAN.md)
- [E-mail provider/idempotencia](EMAIL_PROVIDER_IDEMPOTENCY.md)



## 10. Frissített végrehajtási állapot – 2026-11-26

A PR #28 (feature/company-research-dashboard-readonly) a cégkutatási előzmények read-only Streamlit felületét adja hozzá. A dashboard navigációs útvonalának hiányát a 2fa7b9410d5cbd49140391a633853ad73d81a1b9 commit javítja: a research oldal most a render_company_research_page() függvényt hívja, a meglévő adatbázis-kapcsolatot használja, hibát kezel és a chat helyett dedikált oldalként megáll. A javítás utáni korábbi CI-futás eredménye nem igazolja a jelenlegi headet; a legutóbbi headre nem érkezett workflow-run vagy status adat.

A kutatási előzmény UI jelenlegi korlátai: legfeljebb 500 leadből választ céget, és legfeljebb 20 snapshotot kér le; a forrás URL-ek HTTP(S), hostname, credential, localhost és .local ellenőrzésen mennek át; Auth login esetén fail-closed módon jelzi a hiányzó felhasználói SELECT jogosultságot, service-role megkerülés nélkül; productionben nem aktív.

### Következő végrehajtási fázis – biztonságos kutatási háttérmotor

A következő fejlesztés az autonóm kutatás előfeltételeit készíti elő, nem indít azonnal automatikus kutatást:
1. DB-től független, tesztelhető job-lifecycle és idempotencia szerződés.
2. Lease/claim, lease-expiry, heartbeat és operation ID kezelés.
3. Bounded retry, dead-letter és hibakategorizálás.
4. Korlátos batch, concurrency, domain/API rate limit és költségkeret.
5. Csak ezután injektált repository-adapter és izolált tesztkörnyezetű DB-integráció.
6. Scheduler csak explicit feature flag és emberi operációs kontroll mellett; production scheduler nincs engedélyezve.

Az első implementációs szelet nem használhat production Supabase-t, nem futtathat migrációt, nem indíthat Gemini-kutatást és nem küldhet outbound üzenetet. A worker csak előkészített jobokat kezelhet; a tényleges kutatási végrehajtás későbbi külön lépés.


### 10.1 Háttérmotor – első kódszelet

A PR #28 ágán elkészült a company_research_jobs.py DB-független job-lifecycle modul és a tests/test_company_research_jobs.py tesztcsomag. A modul queued/running/retry_wait/succeeded/dead_letter állapotokat, stabil operation ID mezőt, lease owner/expiry, heartbeat, attempt counter, korlátozott retry és dead-letter átmeneteket modellez. A műveletek tiszta függvények, a repositorynak kell majd az operation ID egyediségét és a claim atomikusságát garantálnia. Nincs DB-integráció, scheduler, Gemini-hívás vagy külső mellékhatás. A tesztcsomag hozzáadva; az összesített CI-ellenőrzés a későbbi funkciócsomag után történik.


### 10.2 Tartós háttérmotor – repository adapter szerződés

A PR #28 ágán elkészült a DB-független `CompanyResearchJobRepository` protokoll és az injektált Supabase kliensre épülő adapter. Az adapter importáláskor nem kapcsolódhat adatbázishoz, nem készíthet saját klienst és nem olvashat service-role secretet környezeti változóból.

Az `operation_id` adatbázis-oldali UNIQUE kulcs; az ismételt create ugyanazt a jobot adja vissza. A claim/heartbeat/complete/fail műveletek külön RPC-kontraktuson keresztül, adatbázis-oldali tranzakcióval és feltételes lease/state ellenőrzéssel valósulhatnak meg. A Python SELECT+UPDATE nem atomi claim. A fake repository tesztek a Python szerződést fedik le; az SQL konkurencia-szemantikát később izolált adatbázis-integrációs teszt igazolja.

A worker job tábla belső adat: RLS bekapcsolva, PUBLIC/anon/authenticated tiltva, kizárólag backend service role jogosultsággal. Migration és RPC csak verziókezelt repository-fájl; production Supabase-re nem alkalmazható. Ebben a fázisban nincs scheduler, Gemini-kutatás vagy outbound mellékhatás.


A Phase 1B repository-szelet implementációja a PR #28 branchben: `company_research_job_repository.py` tartalmazza a Protocolt és az injektált Supabase RPC adaptert; `company_research_refresh_queue.py` a read-only planner jelöltjeit idempotens operation ID-val tartós jobokká alakítja. A `20261126153000_company_research_jobs.sql` migration táblát, UNIQUE operation ID-t, SKIP LOCKED claimet, lease-t ellenőrző heartbeat/complete/fail RPC-kat és service-role-only grants/RLS-t definiál. Fake adapter- és planner-queue tesztek kerültek mellé. A migration nem lett alkalmazva; a CI a teljes funkciócsomag után ellenőrizendő.


### 10.3 Egyszeri worker-orchestration

A `company_research_worker.py` legfeljebb egy előkészített jobot claimel, majd kizárólag injektált handlerrel hajtja végre, és repository RPC-n keresztül complete/fail állapotba teszi. A modul nem tartalmaz kutatási implementációt, Gemini/API-hívást, scheduler-t vagy automatikus futtatást. A handler exception szövegét nem menti, ezzel csökkentve a titok- és személyesadat-szivárgás kockázatát. Ha a lease közben elveszik, nem jelez hamis sikert. Fake repository tesztek fedik le az idle, success, retry, dead-letter és lease-loss ágakat; a teljes csomag ellenőrzése a későbbi összesített körben történik.


### 10.4 Retry backoff

A retry késleltetés exponenciális, determinisztikus és felső korláttal védett legyen. A számítás az attempt_count alapján történik, szigorú pozitív egész validációval; a worker nem lépheti túl a beállított maximumot. A retry-k száma továbbra is véges, a végső próbálkozás dead-letter állapotba vezet. Ez a mechanizmus önmagában nem biztosít globális rate limitet vagy költségkeretet.


### 10.5 Kutatási admission és költségvédelem

A job futtatása előtt determinisztikus admission policy ellenőrizze a globális óránkénti limitet, a domainenkénti napi limitet, a párhuzamos jobok számát és a napi költségkeretet. Költség egész mikro-USD-ben tárolandó. A tiszta policy csak konzisztens usage snapshot alapján hoz döntést; a konkurens worker-ek közötti atomi budget reservation külön adatbázis-oldali műveletet igényel, így a Python oldali ellenőrzés önmagában nem jelent kemény költségplafont.


### 10.6 Hosszú jobok heartbeat callbackje

A worker a kétparaméteres handlernek explicit heartbeat callbacket adhat át. Ez csak a handler által meghívott checkpointoknál végez repository heartbeat RPC-t, nem indít saját timert vagy szálat. A lease-vesztés hamis completiont nem eredményezhet; a handlernek a callback hamis eredményét tiszteletben kell tartania.


### 10.7 Admission policy és queue integráció

A `company_research_admission.py` determinisztikus admission döntést ad a globális óránkénti limit, domainenkénti napi limit, concurrency és napi költség alapján. A költség mikro-USD egész szám. A `company_research_refresh_queue.py` admission-aware batch enqueue útvonala elfogadott jobonként növeli a helyi számlálókat, így ugyanazon batchen belül nem oversubscribe-ol. A több folyamat közötti kvótafoglalás még nem atomikus; ehhez később DB/RPC reservation szükséges. A policy nem hív külső API-t.


### 10.8 Worker eredmény- és idempotencia-biztonság

A worker csak objektum alakú claimelt jobot dolgoz fel, a handlernek másolt payloadot ad át, a visszatérő eredményt JSON-kompatibilitásra és alapértelmezett 256 KiB méretkorlátra ellenőrzi. Nem JSON vagy túlméretes eredmény nem kerül completionbe. A hibakód szűrt, a kivételüzenet nem kerül tartós tárolásba. A repository azonos `operation_id` esetén összeveti a `job_type`, `lead_id` és payload értékeket is; eltérő bemenet idempotencia-konfliktus, nem sikeres duplikáció. A költségbecslő egész mikro-USD-ben, felfelé kerekítve számol, a szolgáltatói tokenárakat konfigurációból kapja.


### 10.9 Atomikus párhuzamossági korlát

A `company_research_job_claim` RPC globális tranzakciós advisory lockot használ, így a párhuzamos claim kérések sorosan ellenőrzik az aktív, le nem járt lease-ek számát. A `p_max_concurrent_jobs` plafon elérésekor a claim üres eredménnyel tér vissza. Ez megakadályozza, hogy több worker ugyanazt a szabad kapacitást egyszerre felhasználva túllépje a megadott concurrency limitet. A lock csak a claim döntést szerializálja; heartbeat és lezárás továbbra is feltételes lease-owner RPC. A migration még nem lett alkalmazva, és az SQL konkurenciát külön izolált PostgreSQL tesztnek kell igazolnia.


### 10.10 Tartós napi budget reservation és lifecycle audit

A Supabase job-create RPC a `company_research_budget_reservations` táblába atomikusan foglal napi UTC költségkeretet. Advisory lockkal sorosítja a foglalásokat, így párhuzamos enqueue-k nem tudják ugyanazt a szabad keretet többször elkölteni. A foglalás és a job insert egy tranzakció; operation ID replay nem készít második reservationt. A napi plafon túllépése `research_daily_budget_exceeded` jelölővel elutasított, amit az adapter és a queue kontrollált `daily_cost_limit` elutasításként kezel.

Az append-only `company_research_job_audit` eseménynapló a job lifecycle fontos tranzícióit rögzíti: enqueued, claimed, heartbeat, succeeded, retry_scheduled, dead_letter, beleértve a végső lease-expiry esetét. A táblára UPDATE/DELETE jog nincs kiosztva. A reservation becsült költséget tart fenn; actual provider usage settlement, unused reservation release, atomikus hourly/domain rate quota és audit retention/archival még hátralévő feladat. A migration nem lett production adatbázison futtatva; a DB viselkedés izolált PostgreSQL tesztet igényel.

A tartós audit események lekérdezésére a repository `list_audit(operation_id, limit)` metódust biztosít; a DB RPC 1–1000 közötti limitet kényszerít ki, és csak service_role hívhatja. A dashboard-integráció még hátravan.
