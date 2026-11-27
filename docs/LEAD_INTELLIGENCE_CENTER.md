# JARVIS – Lead Intelligence Center és következő fejlesztési terv

**Frissítve:** 2026-11-27 18:05 CET  
**Fejlesztési ág:** `feature/opportunity-center-readonly`  
**Hatókör:** a Leadkezelő és a hozzá kapcsolódó kutatási, Opportunity, CRM, Task és E-mail folyamatok.  
**Fontos:** ez fejlesztési terv, nem release- vagy production-engedély.

## 1. Hol tartunk?

### Lead Intelligence Center

A Leadkezelő eddigi vizuális frissítése és a kétpaneles alapelrendezés a feature branchben elkészült:

- kereshető és szűrhető leadlista a bal oldalon;
- kijelölt lead részletező panelje a jobb oldalon;
- státusz szerinti szűrés és prioritás/cégnév szerinti rendezés;
- a keresés ténylegesen része a szűrt leadlistának;
- meglévő review RPC, AI SaaS-javaslat és döntési előzmények megtartva.

Kapcsolódó commitok:
- alap UI-frissítés: `1e933a81dc1c3812ff408f32702d942bc10d03b4`
- kétpaneles szerkezet: `a2dbfda7a88e8c5a53fad1b3b8d051793bf0bfcf`
- keresés bekötése: `8e4ae2b56f588d39b0c523965dee9809efc7046b`

A kódot GitHubról visszaolvastuk, de a teljes böngészős megjelenítés még nincs igazolva. Különösen ellenőrizendő, hogy a részletező panelen a kutatási tények, források és döntési előzmények jól elkülönülnek-e. A korábbi mesterpromptban szereplő külön Részletek / Források / Döntési előzmények információs szerkezetet a tényleges képernyő alapján kell véglegesíteni, nem feltételezéssel.

### Kapcsolódó modulok

- Analitika: a régebbi események dátumot is kapnak az idő mellett. Commit: `cfb1da6d39b67ee02516c54759806738f14b064a`.
- E-mail központ: a jóváhagyott, elutasított, stílusprofil és engedélyek/küldési sor tab-hozzárendelése javítva. Commit: `5962eda938c2f3950097c3c24b0a2b0fb22cf717`.
- CRM és Feladatközpont: korábbi kódellenőrzés nem talált konkrét UI-logikai hibát; a CRM csak jóváhagyott leadeket mutat. A Feladatközpont 0-s adatbázis-állapota most nincs frissen igazolva.

### Adatminőség – miért fontos ez?

A korábbi production read-only ellenőrzéskor:
- 11 lead volt;
- 0 lead rendelkezett Google-grounding source mezővel;
- 0 lead rendelkezett bármilyen source mezővel;
- 0 cégkutatási snapshot volt;
- 0 lead review approval és 0 e-mail-piszkozat/jóváhagyott/elutasított e-mail szerepelt;
- 0 bejövő e-mail válasz volt.

Ez időponthoz kötött korábbi pillanatkép, nem mostani lekérdezés. A pontozatlan lead nem hibás, ha hiányzik a strukturált, forrásolt kutatási bizonyíték. Nem szabad üres adatokból pontszámot, forrást vagy döntést generálni.

## 2. Javasolt végrehajtási sorrend

### P0 – A Lead Intelligence Center felület lezárása

**Cél:** a most elkészült kétpaneles alapból valóban használható, gyors és egyértelmű munkafelület legyen.

Feladatok:
1. Böngészőben ellenőrizni a kétpaneles layoutot széles és keskeny ablakban.
2. Végigellenőrizni a lead kiválasztását, keresést, státuszszűrőt és rendezést.
3. Ellenőrizni, hogy a kijelölt lead adatai mindig ugyanahhoz a rekordhoz tartoznak-e, szűrés után sem marad-e téves kijelölés.
4. A jobb oldali panel tartalmát világos blokkokra bontani:
   - **Áttekintés:** cég, ország, weboldal, státusz, prioritás és pontszám oka;
   - **Kutatás és források:** strukturált tények, forrás URL, kivonat, időbélyeg és bizonytalanság;
   - **Döntési előzmények:** review események, indoklás és időrend.
5. Külön megjeleníteni a hiányos kutatás, nincs forrás, betöltési hiba és jogosultsághiány állapotát.
6. Az AI-javaslatot vizuálisan is hipotézisként jelölni, elkülönítve a forrásolt tényektől.

**Elfogadási feltételek:**
- A lista és a részletező panel mindig ugyanazt a leadet mutatja.
- A keresés és a szűrők kombinálhatók.
- A pontszám hiánya magyarázott, nem „0” vagy félrevezető dash.
- A forráslinkek biztonságos URL-ellenőrzésen mennek át.
- A meglévő JARVIS oldalsáv és navigáció változatlan.
- A review műveletek csak a már meglévő admin/operator jogosultsággal érhetők el.

### P1 – Egyetlen lead teljes, grounded kutatási útja

**Cél:** először egy leadnél bizonyítsuk, hogy a teljes adatút megbízhatóan működik.

Adatfolyam:

`lead kiválasztás → grounded kutatás → dossier/snapshot → strukturált evidence → lead scoring → review`

Feladatok:
1. Kiválasztott leadnél explicit indítású kutatás.
2. Google grounding URL-ek és kivonatok ellenőrzése.
3. Snapshot és leadhez kötés ellenőrzése.
4. Strukturált evidence rekordok megjelenítése az Intelligence felületen.
5. Lead score kiszámítása csak a szükséges strukturált inputok meglétekor.
6. Hiányos vagy ellentmondó forrás esetén bizonytalanság jelzése, automatikus pontozás helyett.

**Elfogadási feltételek:**
- Minden tény visszamutat forrásra.
- A szabad szöveges modell-összefoglaló nem válik automatikusan bizonyítékká.
- Ugyanazon kutatás ismétlése nem hoz létre indokolatlan duplikátumokat.
- A lead approval továbbra sem jelent kapcsolatfelvételi engedélyt.

### P2 – Opportunity Discovery end-to-end bizonyítása

**Cél:** valós forrásokkal alátámasztani, hogy a külön cégek problémáiból hasznos, ismétlődő piaci mintázat keletkezhet.

Adatfolyam:

`több grounded dossier → pain hipotézisek → cross-company pattern → SaaS draft → emberi pattern review → értékelési előnézet`

Feladatok:
1. Legalább két különböző cégtől származó, hasonló kategóriájú és forrásolt pain rekord ellenőrzése.
2. A klaszterezés eredményének emberi áttekintése.
3. Fingerprint/idempotencia és duplikációk ellenőrzése.
4. Candidate pattern és draft opportunity kapcsolatának ellenőrzése.
5. Téves klaszterek elutasítása, kevés bizonyíték esetén további vizsgálat.
6. Fizetési hajlandóságot nem szabad webes problémaleírásból bizonyítottnak tekinteni; ehhez interjú vagy megfelelő piaci bizonyíték kell.

**Elfogadási feltételek:**
- Egy pattern legalább két külön céges bizonyítékra hivatkozik.
- A candidate nem válik automatikusan validated állapotúvá.
- Minden döntés indoklással és audit eseménnyel rögzül.
- A scoring hiányos bizonyítéknál nem ad félrevezető összpontszámot.

### P3 – Lead → CRM → Task folyamat

**Cél:** a lead ne csak egy kutatási rekord legyen, hanem követhető üzleti folyamat alapja.

Javasolt állapotút:
1. Lead kutatás alatt.
2. Kutatás áttekintve.
3. Emberileg jóváhagyva vagy elutasítva.
4. Jóváhagyott lead esetén CRM folyamat indulhat.
5. Interakció kézi rögzítése.
6. Következő teendő javaslata.
7. Feladat létrehozása külön jóváhagyással.
8. Eredmény rögzítése és workflow stage frissítése.

**Elfogadási feltételek:**
- Minden task egyértelmű leadhez és workflow eseményhez kapcsolódik.
- A consent, opt-out és ügyfélstátusz szabályai minden utánkövetési javaslatnál érvényesülnek.
- A lezárásnak van eredménye és indoka.
- Sem CRM művelet, sem task létrehozása nem küld e-mailt.

### P4 – E-mail munkafolyamat, továbbra is küldés nélkül

**Cél:** teljesen visszakövethető, ember által ellenőrzött kommunikáció-előkészítés.

Feladatok:
- Csak jóváhagyott leadhez készülhet piszkozat.
- A címzett e-mail-címe ember által megadott, forrásolt adat.
- Szerkesztés, verziózás, jóváhagyás és elutasítás külön esemény.
- Consent és suppression ellenőrzése külön történik.
- Bejövő válasz csak kategorizált jelzés; JARVIS nem válaszol automatikusan.

**Elfogadási feltételek:** a küldési hard gate kikapcsolva marad; nincs sender worker, provider dispatch vagy automatikus retry.

### P5 – Jogosultság, üzemeltetés és költségvédelem

**Cél:** a kézi folyamat stabil működése után kontrollált háttérműködés.

Feladatok:
1. Reader/admin/operator/anon hozzáférési mátrix izolált stagingben.
2. JWT lejárat, session refresh és RLS tesztelése stagingben.
3. Migrációk replay és schema drift áttekintése production érintése nélkül.
4. Worker pause/resume és scheduler működésének igazolása.
5. Napi hard budget cap és provider actual-cost elszámolás ellenőrzése.
6. Retry, heartbeat, dead-letter és hibajelzések megfigyelhetősége.

**Elfogadási feltételek:** scheduler csak explicit engedéllyel aktiválható; napi költségkorlát tranzakciósan érvényesül; provider-hibák nem okoznak korlátlan újrapróbálkozást.

## 3. Mit ne fejlesszünk most?

- Ne építsük újra a már meglévő grounded cégkutatást, dossier/snapshot tárolást és worker queue-t.
- Ne kezdjünk automatikus outreach vagy e-mail küldés fejlesztésbe.
- Ne adjunk automatikus jóváhagyást leadnek, patternnek vagy SaaS-jelöltnek.
- Ne keverjük a Lead prioritási pontszámot az Opportunity Score-ral.
- Ne állítsunk valós piaci validációt pusztán AI-hipotézis alapján.
- Ne módosítsuk a JARVIS globális oldalsávját/navigációját a Lead Intelligence Center munkája közben.

## 4. Következő konkrét munkamenet

1. A felhasználó friss képernyőképe alapján a P0 UI-ellenőrzés.
2. Ha vizuális vagy funkcionális hiba reprodukálható, célzott javítás a feature branchben.
3. GitHub-fájl visszaolvasás és diff-ellenőrzés.
4. A P1 vertical slice pontos input/output és adatminőségi feltételeinek kialakítása.
5. Csak azután továbblépés az Opportunity Discovery és CRM integrációra.

A felhasználó kérésére külön teszteket nem futtatunk. A kódolvasás nem helyettesíti a böngészős UI-ellenőrzést. Production adatbázis módosítása, migration futtatása, Auth/RLS éles változtatása, PR merge, deploy és e-mail küldés külön, konkrét jóváhagyás nélkül nem történhet.


## P1 – részletes architektúra-ellenőrzés (2026-11-27)

A kód részletesebb áttekintése pontosította a P1 tényleges hiányzó részeit:

1. **A kutatási job queue létezik, de a létrehozó RPC service-role-only.** A `20261126153000_company_research_jobs.sql` migráció visszavonja a `company_research_job_create` végrehajtását a `PUBLIC`, `anon` és `authenticated` szerepköröktől, és csak `service_role` számára engedélyezi. Ez helyes biztonsági alap; a Leadkezelőből nem szabad közvetlenül meghívni, és nem szabad service-role kulcsot a dashboard kliensbe tenni.
2. **A worker futtatása csak explicit backend függvényhívásként létezik.** A `run_company_research_worker_once()` legfeljebb egy jobot claimel, de jelenleg nincs igazolt dashboard-trigger vagy folyamatos scheduleres indítás. A Kutatási műveletek oldal a worker állapotát és pause/resume vezérlését mutatja, nem enqueue felület és nem futtat workert.
3. **A worker snapshot-persister jelenleg nem frissíti a Lead pontozási bemenetét.** A `make_company_research_snapshot_persister()` snapshotot ment, pain hipotéziseket rögzít és market-pattern discoveryt futtat, de nem frissíti a Lead strukturált research assessment mezőit.
4. **A jelenlegi pontozó más adatkontraktust vár.** A `score_researched_lead()` a `Leadkutatás;` kezdetű `notes/research_intelligence` szövegben keresi az üzleti illeszkedési pontszámot, bizonyosságot és alátámasztó jeleket. A worker dossier prompt jelenleg tényeket, döntéshozót és pain hipotéziseket kér, nem egységes lead-fit assessmentet. A snapshotban lévő tények ezért önmagukban nem eredményeznek Lead prioritási pontszámot.
5. **A globális leadkutatás külön adatút.** A `research_global_companies()` már ír strukturált Leadkutatás jegyzetet, `research_evidence` rekordokat és snapshotot, de új cégeket fedez fel; nem célzottan egy meglévő kiválasztott lead frissítésére szolgál. Ezt nem szabad összekeverni a P1 meglévő-lead vertical slice-ével.

### Kötelező P1 építési sorrend

- **P1.1 – Biztonságos enqueue kapu:** új, szűkített authenticated RPC vagy más hitelesített backend határ, amely kizárólag admin/operator számára enged egy meglévő lead kutatását kérni. A kliens nem választhat költségkeretet, worker-azonosítót, státuszt vagy tetszőleges payloadot. A DB/backend ellenőrzi a lead azonosítóját, a cégnév/domain értéket, a szerepkört, az idempotenciát, az óránkénti/domain napi limiteket és a napi költségfoglalást.
- **P1.2 – Kontrollált one-shot worker indítás:** a queue egyetlen jobot dolgozzon fel megbízható backend környezetben, injektált Gemini klienssel és service-role adatbázis-klienssel. Ne fusson a Streamlit request szálában, és ne legyen automatikus, korlátlan scheduler.
- **P1.3 – Egységes kutatási assessment szerződés:** a grounded dossier tények mellett külön, validált lead-fit assessment (score, confidence, indoklás, fit evidence, ajánlott következő kutatási lépés) készüljön. A score és minden fit evidence kizárólag Google-grounding metadata által igazolt URL-hez kapcsolódhat. A hipotézis, tény és üzleti értékelés külön mező marad.
- **P1.4 – Idempotens visszacsatolás:** a snapshot és a strukturált assessment tartósan, verziózva kerüljön mentésre. A lead dashboard a legfrissebb snapshot assessmentjéből számoljon prioritást; ne kelljen modell által írt szabad szöveget parsolni. A lead eredeti megjegyzései és a korábbi snapshotok ne vesszenek el.
- **P1.5 – UI és audit:** a Lead Intelligence Center mutassa a kutatás állapotát (nincs kutatás / sorban / fut / sikeres / újrapróbálás / hibazsák), utolsó kutatási időt, forrásszámot, evidence részleteket, assessmentet és job/audit azonosítót. Csak admin/operator lásson kutatásindító műveletet; reader csak olvasson.

### Biztonsági és működési korlát

A meglévő queue SQL migrationje csak repository/branch artefaktumként kezelendő, és a jelen P1 munka nem jogosít production migrationre. Az új authenticated enqueue kapuhoz migration review és izolált staging jogosultság-ellenőrzés szükséges. A felhasználó kérésére külön tesztet nem futtatunk. A kód és dokumentáció előkészíthető a feature branchben, de production DB módosítás, worker aktiválás, merge és deploy külön engedély nélkül nem történhet.


## P1.1 – admin/operator kutatásindítás implementálva (2026-11-27)

A P1.1 első kódszelete bekerült a feature branchbe:

- Új `lead_research_actions.py`: egyetlen meglévő lead kutatási frissítését készíti elő.
- A művelet előtt friss Supabase Auth ellenőrzés és `research.manage` jogosultság-ellenőrzés történik, kizárólag `admin` vagy `operator` szerepkörrel.
- A service-role kliens csak a sikeres hitelesítés/jogosultság-ellenőrzés után jön létre, kizárólag a szerveroldali Streamlit folyamatban.
- A lead és legfrissebb snapshot alapján a meglévő refresh planner dönt az alkalmasságról; a meglévő queue repository atomikus napi költség-, óránkénti és domain napi limitjeit használja.
- A pricing/token/limit konfiguráció kötelező; hiányzó konfiguráció esetén a kérés fail-closed módon nem kerül sorba.
- A Lead Intelligence Center kiválasztott lead paneljén megjelent a **Kutatás kérése** művelet, csak admin/operator számára.
- A művelet csak queue rekordot hoz létre. Nem indít workert, nem hív Geminit, nem módosít lead státuszt és nem kezdeményez kapcsolatfelvételt.

Érintett commitok:
- `338f70e807214857981c5f81ed3247b16581a0d5` – enqueue szolgáltatás
- `6b1c1f67bfbfa234d5607ca8aeab7c35ed165eeb` – Leadkezelő UI művelet
- `09024c38b4984d402e5d9ead300c4565c3946786` – dashboard Auth/RBAC bekötés
- `926511c6890155ed313200d70e1d2a2b82976d0e` – hiányzó cégnév fail-closed ellenőrzés

A három érintett Python fájlt és a hívási útvonalat GitHubról visszaolvastuk, a kulcsfontosságú jogosultsági és enqueue lépéseket statikusan ellenőriztük. Külön tesztet nem futtattunk, a Streamlit UI-t böngészőben nem ellenőriztük, a queue-t nem hívtuk meg, production DB-t nem módosítottunk. SQL migration nem kellett, mert a meglévő service-role-only enqueue RPC és a meglévő queue táblák használatban maradtak. Merge/deploy nem történt.

**Korlát:** ez a lépés a kutatási kérést tartós sorba helyezi, de worker dispatch/scheduler még nincs bekapcsolva. A P1.2 feladata a kontrollált, explicit one-shot worker végrehajtás szerveroldali megvalósítása; azt külön kell megtervezni és ellenőrizni.


## P1.2 – kontrollált one-shot worker belépési pont (2026-11-27)

Új `company_research_worker_cli.py` került a feature branchbe. Ez a trusted backend folyamat belépési pontja; importáláskor nem fut, és a Streamlit dashboard nem hívja.

Működés:
1. Beolvassa a kötelező `CompanyResearchRuntimeConfig` konfigurációt, és ellenőrzi, hogy a futó Gemini modell egyezik az árazáshoz beállított modellel.
2. Szerveroldali service-role klienssel ellenőrzi a `company_research_runtime_control` singleton rekordot. Hiányzó/hibás vezérlési állapot esetén fail-closed módon leáll; szüneteltetett állapotban nem hoz létre Gemini klienst és nem claimel.
3. Egyedi worker azonosítóval meghívja a meglévő `run_company_research_worker_with_config` útvonalat. Egy futtatás legfeljebb egy jobot claimel.
4. A meglévő worker kezeli a heartbeat/lease állapotot, tokenkorlátot, groundingot, snapshot/pain mentést és tényleges költségelszámolást.
5. A parancs csak státuszt, operation ID-t és nem érzékeny hibakódot ír ki; provider választ vagy cégdossziét nem.

Privát backend környezetben a kézi egyszeri indítás parancsa:

```bash
python -m company_research_worker_cli
```

A futtatáshoz kötelező konfiguráció:
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (vagy a meglévő szerveroldali kompatibilis `SUPABASE_KEY`)
- `GEMINI_API_KEY`, `GEMINI_MODEL` (vagy a kódbeli modell alapértéke)
- `JARVIS_COMPANY_RESEARCH_INPUT_PRICE_MICROUSD_PER_MILLION_TOKENS`
- `JARVIS_COMPANY_RESEARCH_OUTPUT_PRICE_MICROUSD_PER_MILLION_TOKENS`
- `JARVIS_COMPANY_RESEARCH_PRICING_MODEL`
- `JARVIS_COMPANY_RESEARCH_SEARCH_PRICE_MICROUSD_PER_THOUSAND_QUERIES`
- `JARVIS_COMPANY_RESEARCH_MAX_DAILY_COST_MICROUSD`
- `JARVIS_COMPANY_RESEARCH_MAX_JOBS_PER_HOUR`
- `JARVIS_COMPANY_RESEARCH_MAX_JOBS_PER_DOMAIN_PER_DAY`
- `JARVIS_COMPANY_RESEARCH_MAX_CONCURRENT_JOBS`

A queue workerhez a meglévő queue és a `20261127220000_company_research_worker_ops.sql` pause-control migráció szükséges. A migráció repository-ban van; production alkalmazása nincs igazolva és ebben a lépésben nem történt meg. Ha a kontrolltábla vagy a konfiguráció hiányzik, a CLI nem dolgoz fel feladatot.

Ez továbbra is kézi, egyszeri parancs: nincs scheduler, folyamatos worker, Streamlitből indított végrehajtás, deploy vagy automatikus futtatás.

Commit: `9cf0f6b57116383e82de92062d1ca74b1d6d4b93`.

A CLI fájlt GitHubról visszaolvastuk és statikusan ellenőriztük. Külön tesztet nem futtattunk, a CLI-t nem indítottuk el, Gemini API-hívás és queue claim nem történt, production DB-t nem módosítottunk. Merge/deploy nem történt.
