# JARVIS – javítási napló és rendezett hiánylista

## P1 CRM konverziós tölcsér és P2 Research Ops riasztások (2026-11-28)

- A CRM konverziós riport a jóváhagyott leadeket kizárólag lead-azonosítónként egyszer számolja; az aktuális lifecycle státuszt és az append-only eseménytörténetből elért korábbi szakaszokat együtt veszi figyelembe.
- A `responded` szakaszba a strukturált bejövő válasz-esemény is beleszámít. Az elvesztett lead külön kimenetként jelenik meg, és nem törli a korábban elért funnel-szakaszokat.
- A Research Ops dashboard helyi operátori jelzéseket számol a hibazsák, a napi költségkeret és a futó jobok lejárt/hiányzó lease-e alapján. A jelzések a már létező, hitelesített read-only RPC pillanatképből készülnek.
- Külső értesítés, scheduler-aktiválás, Gemini-hívás és adatbázis-módosítás nem része ennek a változásnak.
- A változások feature branchben vannak; CI- és production-állapotukat külön kell igazolni.

## P1 CRM–Feladatközpont összekötés (2026-11-28)

- A Feladatközpont külön, read-only CRM-teendő táblázatot jelenít meg a jóváhagyott leadek `lead_customer_lifecycle` állapotából.
- A meglévő `tasks.lead_id` mezővel összekapcsolja a CRM-teendőt a kapcsolódó nyitott feladatokkal, és jelzi a kapcsolt feladat címét/számát.
- A lejárt CRM-teendőket Budapest helyi dátuma szerint jelöli.
- A CRM-teendő és a task külön rekord marad; nincs automatikus feladatlétrehozás, módosítás, e-mail vagy production DB változás.
- Új helper regressziós teszt ellenőrzi az approved lead szűrést, a lejáratot és a lezárt feladat kizárását.
- A változás CI-ellenőrzése még folyamatban van; valódi böngészős UI smoke még nem történt.

## P1 Opportunity Discovery – shortlist-kapu javítása (2026-11-28)

A P1 vertical slice felülvizsgálatakor kiderült, hogy az evaluator a `draft` és `under_review` SaaS-jelölteket is provider-hívásra engedte. Ez megkerülte volna a jelölt emberi előszűrését és szükségtelen AI-költséget okozhatott.

- Az `opportunity_evaluator.py` most csak `shortlisted` jelöltet enged értékelni; a tiltás a provider meghívása előtt történik.
- A dashboard értékelési listája kizárólag shortlistelt jelölteket kínál fel.
- Regressziós teszt ellenőrzi, hogy `draft` és `under_review` állapotban a provider nem fut le.
- Az `OPPORTUNITY_ENGINE.md` folyamatleírása frissült.
- A változás a feature branchben van; a CI még folyamatban van, staging/production validáció nem történt.

A következő Opportunity P1 ellenőrzési lépés a teljes lánc CI-ben történő igazolása, majd külön stagingben provider nélküli/fixture-alapú UI és DB workflow smoke. Ez nem indítja el a Gemini workert vagy az ütemezőt.

## Friss állapotfelvétel – 2026-11-28, HEAD ca6ba3919df766e4bc5bf6cf5a53e793e428f643

**PR #35:** nyitott, draft; merge és production deploy nincs igazolva.

### Az előző állapotfelvétel óta elkészült módosítások

- A böngészős login smoke megvárja a JARVIS címet, jelszómezőt és belépés gombot, így a screenshot nem készülhet a Streamlit felület hidratálódása előtt.
- A mobil chat fejléc tesztje 390 és 320 px szélességen is ellenőrzi a láthatóságot, a függőleges elhelyezkedést és a vízszintes túlcsordulást.
- A login smoke 390 és 320 px szélességű mobil viewporton is ellenőrzi a jelszómező és gomb elhelyezkedését, és külön screenshotot készít.
- A kutatási műveleti dashboard számlálóinak és költségmezőinek kezelése védi a felületet hibás, negatív vagy nem numerikus RPC-adatoktól. A nulla committed összeg nem helyettesítődik a reserved összeggel.
- A kutatási műveleti dashboardhoz regressziós tesztek kerültek a hibás számlálóértékekre és a nulla committed költségre.

### CI-pillanatkép és ismert javítandó pont

- A korábbi 8412057ae366cadf24853b7e0f3e6f3ddf51de34 HEAD JARVIS CI runja 46146849978 hibával zárult. A research PostgreSQL integration és a backup/restore integration sikeres volt; CodeQL és dependency audit szintén sikeres volt.
- A teszt job a company_research_ops_dashboard.py egyik f-string sorában szintaktikai hibát jelzett. A hibát a ca6ba3919df766e4bc5bf6cf5a53e793e428f643 commit külön változóba emelt számlálóértékkel javította.
- **A javító commit friss CI-eredménye még nincs igazolva.** Coverage és browser screenshot artifact csak új, sikeres futásból fogadható el.
- A korábban elkészült Playwright screenshot csomag 27 PNG-t tartalmazott; kézi áttekintéskor az analitika mobil elrendezése megfelelőnek látszott, a chat mobil fejléc részben a felső toolbar alá csúszott, a login screenshot pedig a teszt túl korai screenshot-időzítése miatt üres volt. A login timing és a chat elhelyezés tesztje/javítása azóta bekerült, de az új screenshotokon még nem igazolt.
- Helyi tesztet nem futtattunk. Production DB-módosítás, e-mailküldés, Gemini worker futtatás és scheduler aktiválás nem történt.

> Ez a friss állapotfelvétel felülírja a dokumentum korábbi, d3e449e / ba210ce HEAD-re és megszakított CI-re vonatkozó pillanatképét. A régebbi bejegyzések történeti naplóként maradnak meg.

**Állapotfelvétel:** 2026-11-28  
**Vizsgált ág:** `feature/opportunity-center-readonly`  
**Pull request:** [#35](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/35) → `main`  
**A dokumentum létrehozásakor ismert HEAD:** `d3e449e9acb39de6c4e83be75c495414b9f21a34`  
**Release-státusz:** PR nyitott, draft, nem merge-ölt; production deploy nincs igazolva.

> A státuszok jelentése: **Kódban kész** = a branch tartalmazza; **CI-vel igazolt** = az adott commiton sikeres automatizált ellenőrzés van; **Stagingben igazolt** = elkülönített, valós konfigurációs környezetben kipróbált; **Productionben aktív** = éles környezetben ténylegesen működik. Ezek nem felcserélhető állapotok.

## 1. Legutóbbi javítás – elutasított SaaS-jelölt és párhuzamos assessment

### Probléma

Az elutasított SaaS-jelöltek evaluator- és adatbázis-védelme már korábban elkészült, de a DB-trigger eredeti lekérdezése nem zárolta a jelölt sorát. Két párhuzamos tranzakció esetén az assessment beszúrása a régi, még nem elutasított státuszt olvashatta, miközben egy másik tranzakció ugyanazt a jelöltet elutasította.

### Javítás

A `supabase/migrations/20261128100000_reject_assessments_for_rejected_opportunities.sql` migráció `reject_assessment_for_rejected_opportunity()` triggerfüggvényének jelöltlekérdezése most `FOR SHARE` zárolást használ.

- Az assessment beszúrása megosztott sorzárat vesz fel a jelölt rekordjára.
- A párhuzamos státuszváltás ugyanazon soron ütköző zárolás miatt sorosodik.
- Az assessment trigger a zárolás feloldása után a tranzakció által látható státuszt ellenőrzi; elutasított jelöltnél `23514` hibával megszakítja a beszúrást.
- A változás nem írja át az elutasítási üzleti szabályt, és nem nyitja újra az elutasított jelöltet.

### Regressziós ellenőrzés és dokumentáció

- A `supabase/tests/opportunity_assessment_approvals.test.sql` tervszáma 11-ről 12-re nőtt.
- Új pgTAP assertion ellenőrzi, hogy a trigger definíciója tartalmazza a `FOR SHARE` zárolást.
- Az Opportunity Engine leírása rögzíti a párhuzamossági védelmet és a tesztszámot.
- A javítás a feature branchben van; production migráció nem történt.

### Ellenőrzési korlát

A GitHub Actions az egymást gyorsan követő commitokhoz tartozó futásokat megszakította. A legutóbb lekérdezett kódcommit `ba210ce` futásai (JARVIS CI, CodeQL, dependency audit) `cancelled` állapotúak voltak. A dokumentációs HEAD `d3e449e` sikeres CI-je nincs igazolva. A 83,33%-os korábbi coverage nem tekinthető a mostani HEAD coverage-eredményének. Helyi tesztet nem futtattunk.

## 2. Mi van már meg a JARVIS-ban?

Az alábbiak a vizsgált feature branchben dokumentált és implementált építőelemek. Nem állítják önmagukban, hogy stagingben vagy productionben végig működnek.

| Terület | Kódban rendelkezésre áll | Fennmaradó bizonyítás / hiány |
|---|---|---|
| Alkalmazás és chat | Streamlit dashboard, magyar üzleti asszisztens, moduláris oldalak | Teljes böngészős UI smoke és staging/production elérhetőség |
| Leadkutatás | Grounding-alapú cégfelderítés, strukturált leadadatok és scoring | Élő provider smoke, minőség- és frissességmérés |
| Cégdosszié | Forrásolt dossier, snapshot history, provenance | Teljes Auth/RLS hozzáférés-mátrix stagingben |
| Research worker | Queue, claim/lease, heartbeat, retry, dead-letter, one-shot runtime, pause/ops és költségelszámolás | Folyamatos scheduler-üzem, provider oldali kemény költségkorlát |
| Leadkezelő | Rangsorolás, részletek, emberi approve/reject, audit | Lead → task → follow-up → outcome teljes E2E |
| Task workflow | Jóváhagyásos belső feladatműveletek | Owner, határidő, lejárat és outcome egységes kezelése |
| CRM | Kapcsolatfelvétel → válasz → minősítés → ajánlat → pilot → ügyfél/elvesztett életciklus, interakciós napló | Owner, ajánlat/pilot/bevétel és megtartás teljes követése |
| E-mail központ | Forrásolt draft, szerkesztés, jóváhagyás, feedback, contact permission és suppression | Bejövő válasz teljes CRM-integrációja és staging E2E |
| Kimenő e-mail | Biztonsági kapuk és tiltás | Szándékosan hard-disabled; nincs automatikus küldés |
| Opportunity Engine | Pain hipotézis, cross-company pattern, SaaS candidate, pattern review, candidate review, scoring preview és explicit approval | Teljes E2E staging-validáció és valós piaci bizonyíték |
| Intelligence evidence | Központi append-only evidence index | Evidence coverage/frissesség monitorozása |
| Intelligence Graph | Származtatott, read-only gráf | Domain-adatokkal való folyamatos konzisztencia-ellenőrzés |
| Analitika és audit | Alap analitika, audit és worker-műveleti nézetek | Teljes funnel, CAC/unit economics, külső riasztás és idősoros monitoring |
| Adatbázis és biztonság | Supabase schema/RLS/RPC migrációk és CI PostgreSQL tesztek | Feature branch migrációinak release előtti alkalmazása és staging role-mátrix |
| Hosting és release | GitHub repository és CI folyamat | JARVIS staging/prod app-host, deploy, rollback és üzemeltetési runbook |

## 3. Hiánylista – prioritás és függőségek

### P0 – Release-biztonság és a jelenlegi ág lezárása

1. **Friss CI a legutolsó PR HEAD-en.** JARVIS CI, CodeQL és dependency audit mind sikeres legyen. A megszakított futás nem siker.
2. **Coverage minimum.** A felhasználó által elfogadott minimum 82%; 90%-os cél nem szükséges. A küszöböt a friss CI riportból kell ellenőrizni.
3. **Migrációs és jogosultsági review.** PR #35 összes új migrációjának sorrendje, RLS, GRANT, SECURITY DEFINER/INVOKER, üres search_path, trigger és idempotencia felülvizsgálata.
4. **Staging release gate.** Külön staging adatbázis és alkalmazás nélkül ne tekintsük az új dashboardot és migrációkat élesre késznek.
5. **UI smoke.** A fő oldalak, üres állapotok, hibás adatforrások, reader/admin/operator jogosultságok böngészős ellenőrzése.
6. **Release dokumentáció.** Migrációs sorrend, backup/restore, rollback, környezeti változók és operátori ellenőrzőlista.

**Elfogadási feltétel:** minden kötelező CI check zöld a legfrissebb HEAD-en, coverage legalább 82%, a migrációk review-zva, a staging smoke jegyzőkönyvezve. Csak ezután merge/release.

### P1 – Az üzleti folyamatok tényleges összekapcsolása

1. **Opportunity Discovery E2E.** Egy explicit, reprodukálható folyamat: kiválasztott cégek → grounded kutatás → dossier/snapshot → pain hypothesis → cross-company pattern → SaaS candidate → emberi review → evaluator → assessment approval.
2. **E2E adatminőség.** Mérni kell, hogy a pain-ek hány százaléka forrásolt, hány kerül patternbe, hány pattern validálható, mennyi a duplikáció és a téves klaszter.
3. **Valós probléma-validáció.** Ügyfélinterjú, probléma gyakorisága/súlyossága, jelenlegi workaround, döntéshozó és költségkeret rögzítése. Két cég hasonló problémája önmagában nem bizonyít fizetési hajlandóságot.
4. **Pilot és willingness-to-pay.** Strukturált pilotcél, mérőszám, időtartam, résztvevő, visszajelzés és fizetési szándék rögzítése.
5. **CRM follow-up és felelős.** Owner, következő teendő, határidő, lejárt teendő, emlékeztető és outcome összekötése.
6. **Bejövő válasz → CRM.** A bejövő e-mailből javasolt státusz-/adatfrissítés, forrás és emberi jóváhagyás után kerüljön a CRM-be.
7. **Kapcsolattartó és cégcsoport.** Aliasok, duplikált kapcsolattartók, leányvállalatok és kézi jóváhagyású rekord-összevonás.
8. **Ajánlat és pilot követés.** Ajánlatverzió, érték, határidő, pilot státusz, eredmény és bevétel.

### P2 – Megbízható automatizálás és operáció

1. **Scheduler.** A már meglévő one-shot worker ütemezett indítása, operátori pause/resume, kill switch, piac/ország szerinti limit és idempotens futás. A scheduler maradjon opt-in.
2. **Élő Gemini staging smoke.** Grounding minőség, timeout, 429/503, retry, heartbeat, provider usage és költség ellenőrzése.
3. **Valódi hard budget.** Provider oldali query/token limit vagy olyan konzervatív foglalási mechanizmus, amely egyetlen hívásnál sem engedi túllépni a napi limitet. A jelenlegi elszámolás a következő jobokat blokkolja, de egyetlen hívás túllépheti a becsült query allowance-t.
4. **Monitoring és riasztás.** Worker elakadás, dead-letter, költségkeret, provider hiba, scheduler kimaradás, e-mail ingest hiba és adatfrissesség.
5. **Backup/restore és DR.** Rendszeres ellenőrzés, RPO/RTO cél, helyreállítási gyakorlat és runbook.
6. **Hosting és release automatizálás.** Megbízható staging/prod app-host, deploy, health check, rollback és környezetek közötti konfigurációs kontroll.

### P3 – A hosszú távú JARVIS-termékvízió

1. **SaaS terméktervezés:** validált opportunityból PRD, célcsoport, user journey, scope és elfogadási kritériumok.
2. **Termék-backlog és prototípus:** ember által jóváhagyott backlog, prototípus, becslés és függőségek.
3. **AI-assisted fejlesztési pipeline:** kódgenerálás, teszt, security review, preview/staging és release – minden külső hatás külön jóváhagyással.
4. **Termékportfólió és ütközésvizsgálat:** hasonló ötletek, meglévő termékek, célpiacok és erőforrások összevetése.
5. **Üzleti eredménymérés:** MRR/ARR, gross margin, CAC, LTV, churn, pilot-to-paid és opportunity-to-customer konverzió.
6. **Tanulási visszacsatolás:** elutasítási okok, interjúk, pilotok és tényleges vásárlási eredmények visszavezetése a rangsorolásba – bizonyíték és emberi kontroll mellett.

## 4. Javasolt végrehajtási sorrend

| Sorrend | Munkacsomag | Miért ebben a sorrendben? | Késznek tekinthető, ha |
|---:|---|---|---|
| 1 | PR #35 CI + security/migration review | Release előtt minden más erre épül | Friss HEAD zöld, coverage ≥82%, review lezárva |
| 2 | Staging környezet + Auth/RLS/UI smoke | Production kockázat nélkül igazolja a valós működést | Migráció, role-mátrix és böngészős smoke dokumentált |
| 3 | Opportunity Discovery E2E | A JARVIS megkülönböztető üzleti képessége | Egy végigkövethető, forrásolt minta teljes életciklusa működik |
| 4 | Ügyfélinterjú és pilot validáció | A technikai score nem helyettesíti a piacot | Strukturált interjú/pilot eredmény és fizetési jel rögzíthető |
| 5 | CRM owner/follow-up és inbound email integráció | A kutatásból végrehajtható értékesítési folyamatot csinál | Minden leadnek felelőse, következő lépése és mérhető outcome-ja van |
| 6 | Scheduler + költségvédelem + monitoring | Csak bizonyított kézi folyamat automatizálása | Kill switch, provider cap, alert és több ciklusos staging futás igazolt |
| 7 | SaaS product factory | Validált igényből építsen terméket, ne hipotézisből | Jóváhagyott PRD → backlog → prototípus → tesztelt release útvonal |

## 5. Kifejezett biztonsági és scope-határok

- Ne építsük újra a már meglévő leadkutatást, dossier/snapshot rendszert vagy one-shot worker infrastruktúrát; a hiány a teljes folyamat igazolása és összekapcsolása.
- A kimenő e-mail maradjon hard-disabled, amíg külön engedélyezett, tesztelt küldési projekt nincs.
- Ne legyen automatikus ügyfélválasz vagy automatikus kapcsolatfelvétel.
- Scheduler csak explicit konfigurációval, költségkorláttal, pause/resume és kill switch mellett aktiválható.
- Production DB-migráció, Auth/RLS/GRANT, secret-változás és deploy csak release-ellenőrzés után.
- Nincs adat törlése; üzleti döntések append-only auditot kapnak.
- A JARVIS oldalsávja/navigációja nem része ennek a fejlesztési csomagnak.
- Nem tekintjük a CI-t production validációnak, és a dokumentációban a nem ellenőrzött állapotot nem nevezzük késznek.

## 6. Kapcsolódó dokumentumok

- [Aktuális implementációs állapot és roadmap](20261128_IMPLEMENTATION_STATUS_AND_ROADMAP.md)
- [Opportunity Engine – működés és biztonsági modell](OPPORTUNITY_ENGINE.md)
- [Capability Gap Report](JARVIS_CAPABILITY_GAP_REPORT.md)
- [JARVIS Master Documentation](JARVIS_MASTER_DOCUMENTATION.md)
- [CRM lifecycle](LEAD_CUSTOMER_LIFECYCLE.md)
- [Email workflow](LEAD_EMAIL_WORKFLOW.md)
- [Research worker operations](RESEARCH_WORKER_OPERATIONS.md)
