# JARVIS – központi projekt- és műszaki dokumentáció

> **AKTUÁLIS, FELÜLÍRÓ ÁLLAPOT – 2026-11-27 (PR #34).** Ez a blokk felülírja a dokumentum alábbi részeiben szereplő korábbi PR-, branch-, CI-, budget-cap-, worker- és scheduler-státuszokat. Aktív fejlesztési ág: `feature/daily-hard-budget-cap`. PR: [#34](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/34), továbbra is **open + draft, merged=false**. Ellenőrzött PR HEAD: `52713c448a370b505ed700995eea2b231752a86b`. A `main` ellenőrzött SHA-ja: `477d73afa7d6ebd12eb7d1da7a2e52b68ff2abc0` (változatlan).
>
> **Kódban elkészült és CI-ben ellenőrzött:** napi hard budget ceiling per reservation; tranzakciós/advisory-lock alapú admission és actual-cost settlement; túlköltés esetén dead-letter és további foglalások megállítása; hiányzó, nem mérhető költségadatnál fail-closed viselkedés; közös modellhez kötött token- és Google Search grounding-árazási konfiguráció; prompt token-count ellenőrzés és output-token limit; Search query költség becslése és actual-cost elszámolása; paginált stale-lead refresh planner/queue/runtime; bounded refresh worker és napi GitHub Actions workflow. A provider- és job-retry egy próbálkozásra korlátozott, amíg a sikertelen próbák költsége nem mérhető megbízhatóan.
>
> **CI-állapot:** a PR HEAD-hez tartozó JARVIS CI, PostgreSQL integrációs/race tesztek, compileall, unit, AppTest, böngészős tesztek, CodeQL és dependency audit sikeres. Ez izolált CI-ellenőrzés, nem production-validáció.
>
> **Még nincs beállítva / élesben igazolva:** a tényleges Gemini modellhez tartozó tokenárak és Search grounding ár; napi költségkeret és rate/domain/concurrency limitek GitHub Secrets/Variables értékei; élő, nem production Gemini staging smoke; production migration, deploy és scheduler-aktiválás. A napi workflow csak a PR merge-je után, main ágon, a kötelező konfigurációval válhat aktívvá. A Search query allowance foglalási becslés, nem szolgáltatói hard cap; a tényleges költség elszámolása és túllépéskezelése a DB settlement feladata.
>
> **PC-N ELVÉGZENDŐ – NE CHATBEN:** GitHub → Settings → Secrets and variables → Actions alatt a Gemini API kulcs és Supabase service-role kulcs meglétének ellenőrzése, majd a pontos modellnévhez tartozó input/output tokenár, Search grounding ár, napi hard budget, óránkénti joblimit, domainenkénti napi limit, párhuzamos joblimit, valamint Search query allowance beállítása. Titokértéket ne másolj chatbe, és árakat ne becsüljünk. A beállítás után először csak konfiguráció-validálás és külön jóváhagyott, korlátozott staging smoke következhet; production futtatás/deploy/migráció külön döntést igényel.
>
> **Következő sorrend:** (1) PR #34 kód- és dokumentációs review; (2) PC-s GitHub Secrets/Variables konfigurálás; (3) konfiguráció-validálás és staging smoke, valós usage/grounding költség ellenőrzéssel; (4) Auth/JWT/RLS snapshot-hozzáférés és production migration drift külön felülvizsgálata; (5) csak ezek után release-döntés. PR merge nem történt, és nem történhet explicit kérés nélkül. Production DB/infrastruktúra nem módosult, Gemini éles hívás és scheduled workflow dispatch nem történt.


> **Aktuális állapot – 2026-11-26 (a korábbi státuszblokkokat felülírja).** A PR #26, #27 és #28 mind merge-ölve van a `main` ágba. A legutóbbi main commit: `9ceb2f7fdd0130240c15dc4e1701d3fba1bdb53c`. A PR #28 HEAD-hez tartozó CI #3187 (run `45900450820`) mindhárom jobja sikeres: Python/AppTest/browser tesztek, izolált PostgreSQL 17 worker-integráció, valamint backup–restore/security. A PR #26 HEAD-en a JARVIS CI, CodeQL és dependency audit sikeres; a PR #27 HEAD-en a JARVIS CI sikeres. A merge commiton külön post-merge workflow/státusz nem jelent meg, ezért a merge utáni újrafuttatás nem tekinthető igazoltnak.
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
| Kutatási frissítési szabály | Tiszta, tesztelhető policy modul | Nincs scheduler/automatikus futtatás bekapcsolva |
| One-shot kutatási worker | Queue, RPC repository, Gemini grounding provider és runtime összekötve; snapshot mentés a job complete előtt | Scheduler nincs; élő Gemini integráció és PostgreSQL CI eredmény commitonként igazolandó |
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
- `company_research_store.py`: UUID, időbélyeg és SHA-256 tartalomlenyomat ellenőrzése; append-only snapshot insert, korlátozott történetlekérdezés és operation ID-alapú idempotens mentés.
- `company_research_worker.py` / `company_research_runtime.py`: a validált dosszié snapshot mentése kötelező lépés a job sikeres lezárása előtt; a mentett snapshot lead_id FK-val kapcsolódik a leadhez.
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
- [Főrendszer-készültségi felmérés](JARVIS_MAIN_SYSTEM_READINESS.md)
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

A worker a kétparaméteres handlernek explicit heartbeat callbacket ad át. A Gemini provider adapter a szinkron provider kérés teljes ideje alatt külön, leállítható daemon szálból, konfigurálható időközönként meghívja ezt a callbacket. A callback hamis eredménye vagy kivétele lease-vesztést jelez; a provider válaszát ilyenkor nem adja vissza sikeres kutatási eredményként. A heartbeat szál a provider hívás végén leáll és joinolódik. A worker továbbra is csak érvényes lease-szel complete-elhet.


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


### 10.11 Adatbázisoldali rate limit enforcement

A tartós enqueue RPC ugyanazon tranzakciós advisory lock alatt ellenőrzi a UTC óránkénti globális és UTC naponkénti domainenkénti jobkvótát, mint a napi költségkeretet. Az idempotens operation ID replay a kvótaellenőrzés előtt visszaadja a meglévő rekordot, így retry nem fogyaszt többször kvótát. A létrehozási időt az adatbázis állítja be; a domain kulcs casefoldolt összehasonlítással kerül ellenőrzésre. A Python snapshot admission csak korai, kényelmi szűrő; a kemény hourly/domain/cost korlát a DB RPC-ben van.

A kvóta a job enqueue-k számát jelenti, nem a sikeres kutatásokét: a sikertelen és dead-letter jobok is beleszámítanak az adott időablakba. A költségkeret jelenleg becsült foglalás alapján számol, nem valós provider számla alapján.


### 10.12 Actual cost settlement

A worker opcionális `actual_cost_extractor` függvénnyel képes a provider handler eredményéből tényleges költséget kinyerni. A callback kimenete szigorúan nemnegatív egész mikro-USD. A repository a complete RPC-n keresztül adja át; a job sikeres lezárása, a budget reservation `settled` státuszra váltása, a foglalt összeg actual cost-ra cserélése és az audit metadata beírása egy adatbázis-tranzakcióban történik. Extractor hiányában az eredeti becsült összeg marad fenntartva, így az elszámolás nem engedi véletlenül felszabadítani a fel nem mért költséget. Tényleges provider usage mérés még nincs implementálva.

Minden Python refresh enqueue útvonal kötelezően megadja a becsült költséget és a limit-konfigurációt; nincs több olyan egyszerű enqueue helper, amely a hard adatbázisoldali napi költség-, óránkénti vagy domain napi korlátok nélkül hozhat létre jobot.


### 10.13 Grounded Gemini provider adapter

A cégkutatási execution réteg injektált Gemini klienssel működő Google Search grounding adaptert, strukturált JSON feldolgozást, grounded host alapú tény- és döntéshozó-validációt, legfeljebb három transient retry-t exponenciális backoff-fal, valamint worker-kompatibilis handler factoryt tartalmaz. A provider usage token-számait továbbadja; explicit konfigurált tokenárakkal actual micro-USD költség számítható. API secretet vagy klienst nem olvas/hozz létre önállóan. A szinkron API kérés alatt a provider adapter konfigurálható időközönként háttér-heartbeatet végez; lease-vesztés esetén eldobja a provider eredményét. A dashboard és a tartós snapshot store integrációja még nincs bekötve; nincs automatikus futtatás vagy outbound kommunikáció.

A `company_research_runtime.py` explicit, one-shot composition root a repository + Gemini grounded provider + worker + tokenáras actual-cost extractor bekötésére. A runtime függvény csak explicit híváskor claimel egyetlen jobot; import-time side effect, automatikus scheduler, secret/client létrehozás nincs.


### 10.14 Hosszú Gemini-kérések lease-heartbeat javítása

A korábbi megvalósítás csak a provider hívás előtt és után ellenőrizte a lease-t, ezért egy hosszú szinkron Gemini kérés alatt a lease lejárhatott. Javítás: a GeminiGoogleSearchCompanyResearchProvider most konfigurálható időközönként külön, leállítható daemon szálból meghívja a worker heartbeat callbackjét a teljes API-kérés és retry-időszak alatt. Hamis heartbeat-válasz vagy callback-kivétel lease-vesztésnek minősül, és a provider eredménye nem kerül sikeres jobként complete-olásra. A szál a provider hívás végén leáll és joinolódik. Két célzott teszt fedi a periodikus renewal és lease-vesztés esetét. A teszt/CI eredmény csak az új commit SHA-ján ellenőrizhető; korábbi futás nem igazolja ezt a javítást.


## 10.15 Főrendszer-készültségi felmérés

Elkészült a `JARVIS_MAIN_SYSTEM_READINESS.md`, amely különválasztja a belső főrendszer készre jelentését a hosszú távú autonóm SaaS-ügynök víziójától. Funkciónként megadja az implementációs állapotot, a P0/P1 lezárási feladatokat, a nem blokkoló P2 termékfázisokat és a külön production release kapukat. A jelenlegi minősítés: a főrendszer még nem tekinthető késznek, mert az aktuális CI futás és a teljes core E2E/smoke bizonyítékok hiányoznak.


## 10.16 Dashboard navigáció és Beállítások audit

A PR #28 dashboardjának teljes navigációs útvonala áttekintve: Chat, Feladatok, Analitika, Cégkutatás, Audit napló és Beállítások. A korábbi statikus, nem kattintható Beállítások menüpont helyett dedikált read-only Settings oldal működik, amely csak konfigurációs jelenlétet mutat (titokértékeket nem), jelzi az Auth módot és a biztonsági kapukat, a rendszerdiagnosztikát pedig kizárólag kézi indításra futtatja. A Gemini próbakérés lehetséges API-költségét a UI előre jelzi.

A dashboard státuszfelirata a nem igazolt „Rendszer Online” helyett „Munkamenet aktív”. A Feladatközpont üres tasklista esetén korábban korai visszatéréssel kihagyta az utánkövetési sort; ez javítva, regressziós AppTesttel fedve. A Cégkutatás Auth/RLS módban továbbra is fail-closed, amíg az olvasási jogosultság nincs kivezetve; az Audit külön Supabase Auth-admin belépést igényel. A Settings Auth módban settings.read jogosultsággal érhető el, a teljes diagnosztika admin-only. Nem módosít runtime secretet, Auth/RLS-t vagy adatbázis-konfigurációt, és nem tárol felhasználói preferenciákat.

A dashboard audit után új AppTestek kerültek a branchre. A korábbi `36d615f` core workflow commit CI-je zöld volt, de az új dashboard commitok teljes CI-ellenőrzése külön szükséges.


## 10.17 Egységes runtime hibakezelés

A `jarvis_errors.py` közös hibakategorizálást biztosít: hiányzó/hibás konfiguráció, permission denied, authentication failed, rate limit/quota, hálózati hiba, timeout, szolgáltatáskiesés, invalid request és unknown. A kategorizálás nem teszi a kivétel nyers szövegét felhasználói üzenetté; a chat magyar, biztonságos útmutatót ad. A Gemini kérés korlátozottan újrapróbálkozik átmeneti hibákra, de hitelesítési/jogosultsági hibára nem. A retry nem ismételhet jogosulatlan műveletet, és nem kerülheti meg az RLS-t. A hozzáadott tesztek a kategóriákat, a hálózati retryt és az auth fail-closed viselkedést ellenőrzik. A teljes aktuális CI még külön ellenőrzési kapu.


## 10.18 Szelektív tesztelési stratégia és aktuális hátralék

A projekt nem ismétli minden commit után a teljes, korábban már sikeresen igazolt tesztcsomagot. A módosított modulokhoz célzott unit/AppTest és közvetlen regressziós teszt tartozik; SQL-változásnál izolált PostgreSQL/pgTAP és konkurencia, Auth/RLS vagy provider változásnál izolált integrációs smoke szükséges. Teljes CI csak integrációs mérföldkőnél vagy merge/release előtt indokolt. A tesztbizonyítékot commit SHA-hoz kötjük, a korábbi zöld eredmény nem öröklődik új kódra.

A jelenlegi nyitott munkák, az eddig igazolt ellenőrzések, a következő célzott tesztkör és a production release kapuk a JARVIS_REMAINING_WORK_REPORT.md dokumentumban szerepelnek.


## Aktuális megvalósítási állapot és termékképességek – 2026-11-26

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

PR #28 nyitott, nem merge-ölt, a base a `feature/company-research-phase-1` (stacked PR-lánc: #26 → #27 → #28; a merge sorrend kötelező). A JARVIS app helyi fejlesztés alatt van, nincs production app-host/deploy. A production DB-n nem történt módosítás; nincs production migration, deploy, secret-változtatás vagy e-mailküldés. A dokumentált CI nem jelent production readiness-t.
