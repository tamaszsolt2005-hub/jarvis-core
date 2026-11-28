# JARVIS – aktuális funkcióleltár, hiánylista és fejlesztési terv

**Frissítve:** 2026-11-28  
**Vizsgált ág:** `feature/opportunity-center-readonly`  
**PR:** #35 → `main`, nyitott, draft; a PR állapotát és CI-jét minden új commit után külön kell ellenőrizni.

> Ez a dokumentum a repositoryban dokumentált és az aktuális PR-ágon azonosított képességeket választja szét. A „kódban megvan” nem jelent automatikusan CI-vel igazolt, stagingben élő vagy productionben működő állapotot. Ahol a bizonyíték hiányzik, ott ezt külön jelezzük.

## 1. Vezetői összefoglaló

A JARVIS már rendelkezik a belső üzleti asszisztens, leadkutatás, cégdosszié, lead scoring, jóváhagyásos taskkezelés, CRM-életciklus, e-mail-előkészítés, Opportunity Discovery és Intelligence Graph jelentős építőelemeivel. A következő fejlesztési szakasz fő célja nem újabb elszigetelt modulok létrehozása, hanem a meglévő komponensek teljes, mérhető és biztonságosan üzemeltethető folyamatokká kapcsolása.

**Aktuális PR #35 CI-pillanatkép:** a `b22635b` commiton a JARVIS CI tesztjobja 2 tesztharness-hibával bukott; 1340 teszt sikeres, 3 kihagyott, 2 sikertelen; összesített line coverage 83,33%. A PostgreSQL research integration, backup/restore integration, CodeQL és dependency audit sikeres volt. A két hibát a teszt UI-fake-jében javítottuk a következő commitban; ennek az új commitnak a CI-eredménye még nem tekinthető igazoltnak. A felhasználó 82%-os coverage célt elfogadott; a jelenlegi 83,33% meghaladta ezt, de a friss commiton újra kell ellenőrizni.

## 2. Funkcióleltár

Állapotjelölések:
- **Implementált:** a funkció dokumentáltan szerepel a fejlesztési ág kódjában.
- **Részleges:** az alapmodul megvan, de a teljes folyamat vagy egyes fontos képességek hiányoznak.
- **Nem igazolt:** nincs megbízható staging/élő/production bizonyíték.
- **Tiltott / emberi kapu:** szándékosan nincs automatikusan engedélyezve.

### 2.1 Alaprendszer, chat és jogosultság
- Streamlit-alapú JARVIS alkalmazás, chat és moduláris dashboard.
- Központi konfiguráció- és hibakezelési minták, korlátozott retry és biztonságos hibaüzenetek.
- Supabase Auth/RBAC és admin/operator/reader szerepkörökre épülő műveleti határok.
- Audit és append-only eseménynaplók több üzleti workflow-ban.
- **Hátralék:** a teljes dashboard manuális smoke és a staging Auth/JWT/RLS szerepkörmátrix friss, végponttól végpontig igazolása.

### 2.2 Leadgenerálás és cégkutatás
- Grounding-alapú cégfelderítés és kutatás, strukturált dossier, snapshot-előzmények.
- Forrás URL-ek validálása, kutatási bizonyítékok és confidence/provenance kezelés.
- Lead scoring és emberi jóváhagyási workflow.
- Cégazonosítás és normalizált cégnév/domain alapú duplikációvédelem, tranzakciós RPC-vel.
- Research job queue, idempotencia, claim/lease, heartbeat, retry és dead-letter.
- One-shot worker és Gemini grounded provider adapter.
- **Hiányos / nem igazolt:** automatikus, folyamatos scheduler-üzem; élő Gemini staging smoke; több napi ciklusos működés; szolgáltatói usage és actual-cost hard cap teljes bizonyítása; adatfrissesség és kutatási minőség idősoros mérése.

### 2.3 Leadkezelő és task workflow
- Rangsorolt leadlista, leadrészletek, kutatási bizonyítékok és döntési előzmények.
- Jóváhagyás/elutasítás, indoklás és audit.
- Forrásolt leadből belső task-javaslat készíthető; a task létrehozása külön emberi jóváhagyást és atomikus műveletet igényel.
- **Hiányos:** teljes lead → task → follow-up → outcome E2E állapotmodell és end-to-end teszt; feladatfelelős/owner kezelés és lejárt teendők egységes kezelése.

### 2.4 CRM és ügyfél-életciklus
- Jóváhagyott leadek ügyfél-életciklus státuszai: kapcsolatfelvétel, válasz, minősítés, ajánlat, pilot, ügyfél, elvesztett.
- Kézi státuszváltás, interakció naplózás és következő teendő határidővel.
- Append-only eseménytörténet és szerepkör-ellenőrzés.
- **Hiányos:** felelős-hozzárendelés; lejárt és elmaradt teendők aktív figyelése; cégcsoport/leányvállalat kapcsolatok; kapcsolattartó-duplikáció és biztonságos összevonás; ajánlat/pilot dokumentum- és bevételkövetés; megtartás/lemorzsolódás; egységes konverziós riport.

### 2.5 E-mail intelligencia és kommunikáció
- Forrásolt, jóváhagyott leadhez kötött AI e-mailtervezet.
- Draft szerkesztés, jóváhagyás/elutasítás, verzióelőzmény és stílus-visszajelzés.
- Kapcsolattartási engedélyek, suppression lista és küldési sor fail-closed ellenőrzése.
- Bejövő levelek workflow-ja: leadhez kapcsolás, kategorizálás és emberi felülvizsgálati jelzés.
- **Tiltott:** automatikus outbound küldés és automatikus válaszadás; a kimenő e-mail hard-disabled.
- **Hiányos / nem igazolt:** teljes levelezési szál és alias-kezelés; IMAP UID checkpoint és duplikációmentes feldolgozás staging bizonyítéka; bejövő válaszok strukturált CRM-adatfrissítése; külső push értesítés (külön döntést igényel); provider idempotencia élő E2E igazolása.

### 2.6 Opportunity Discovery és SaaS-jelöltek
- Grounded céges pain/problémahipotézisek.
- Különböző cégek forrásolt problémáinak determinisztikus klaszterezése.
- Candidate market pattern és draft SaaS candidate.
- Hatdimenziós, bizonyítékhoz kötött scoring és evaluator preview.
- Admin/operator validálás, további vizsgálat vagy elutasítás, kötelező indoklással és append-only előzményekkel.
- **Hiányos:** klaszterezési precision/recall és téves klaszterek mérése; teljes pain → pattern → candidate → evaluator E2E staging-validáció; valós ügyfélinterjúk, pilotok és fizetési hajlandóság rögzítése. A két céges alátámasztás önmagában nem bizonyít fizetőképes piacot.

### 2.7 Intelligence evidence és Graph
- Központi append-only evidence/provenance index lead-, dossier- és pain-forrásokhoz.
- Intelligence áttekintő és származtatott Graph nézet.
- A gráfban a domain rekordokból származtatott kapcsolatok jelennek meg; AI által kitalált kapcsolatok nem válnak automatikusan bizonyított ténnyé.
- **Hiányos:** evidence coverage és frissesség üzleti minőségmérése; gráf és domain-adatok közötti konzisztencia folyamatos monitorozása.

### 2.8 Analitika és rendszerfelügyelet
- Alap analitika és esemény-/auditnézetek.
- Research job státuszok, pause/resume és költségfoglalási/elszámolási adatok.
- **Hiányos:** end-to-end értékesítési funnel; elfogadott lead, kapcsolatfelvétel, válasz, ajánlat, pilot és bevétel konverzió; leadenkénti és ügyfélszerzési költség; külső riasztás; provider-latencia, tokenhasználat, workflow-run és dead-letter idősoros monitorozása.

### 2.9 Hosting, staging és production
- Repository/CI migrációs és izolált PostgreSQL integrációs tesztek.
- Korábban sikeres backup/restore integrációs workflow.
- **Nem igazolt:** JARVIS production app-host és URL, staging deploy, élő provider-integráció, teljes staging Auth/JWT/RLS smoke, production deploy és rollback runbook.
- PR #35 migrációi a branch részei; a production alkalmazásuk és a dashboard deployja külön release-feladat. CI-siker nem production readiness.

## 3. Következő fejlesztési javaslatok – prioritás szerint

### P0 – jelenlegi ág stabil lezárása
1. A friss PR #35 head CI-jének ellenőrzése; a két UI fake teszthiba javításának igazolása.
2. 82% coverage minimum megtartása; nem kell 90%-ra emelni.
3. PR #35 kód-, migráció-, RLS- és dokumentációs review; csak minden kötelező check sikeres állapotban merge.
4. A merge után a staging/production migráció és deploy külön release-gate marad.

### P1 – üzleti folyamatok összekapcsolása
1. **Opportunity Discovery E2E:** pain → pattern → SaaS candidate → evaluator → emberi döntés; minden átmenet auditált és idempotens.
2. **CRM follow-up és owner:** felelős, határidő, lejárt teendő, következő belső task és outcome összekötése.
3. **Kapcsolattartó- és cégcsoport-azonosítás:** e-mail/domain/név normalizálás, aliasok, leányvállalatok, kézi jóváhagyású összevonás és audit.
4. **Bejövő e-mail → CRM:** válasz besorolásának és bizonyítékának biztonságos, ember által felülvizsgált strukturált rögzítése.
5. **Értékesítési funnel analitika:** lead elfogadástól ügyféllé válásig, költség- és konverzióméréssel.

### P2 – megbízható automatizálás és üzemeltetés
6. Kutatási scheduler operátori vezérléssel, piac szerinti ütemezéssel és kill switch-csel.
7. Gemini staging smoke: grounding, usage, timeout, 429/503, retry, heartbeat és actual-cost ellenőrzés.
8. Költségkeret túllépés elleni provider oldali query/token limit és reservation-overrun védelem.
9. Külső riasztások és workflow-run monitoring (csak kiválasztott csatorna és külön konfiguráció mellett).
10. Staging Auth/JWT/RLS, manuális dashboard smoke, hosting és rollback runbook.

### P3 – későbbi terméképítési képességek
11. Ügyfélinterjúk, pilotok és fizetési hajlandóság strukturált rögzítése az Opportunity Engine-ben.
12. Piaci mintázatok pontosságmérése, klaszterhibák felülvizsgálata és emberi feedback visszacsatolása.
13. Ajánlat- és pilot dokumentumok, bevétel, megtartás és lemorzsolódás kezelése.
14. AI-assisted SaaS terméktervezés, prototípus, backlog, build/test/staging/release pipeline – minden külső mellékhatás külön jóváhagyási kapuval.

## 4. Első végrehajtási menet

A jelenlegi első munka a PR #35 CI tesztharness hibáinak javítása. Ezt követően az első funkcionális vertical slice az **Opportunity Discovery E2E ellenőrizhető összekapcsolása** legyen. A megvalósítás sorrendje:

1. A meglévő domain táblák, repository/service függvények és dashboard actionök adatútjának feltérképezése.
2. A hiányzó átmenetek és idempotencia-határok megnevezése.
3. Egyetlen explicit, ember által indított, read/preview lépésű vertical slice tesztelése.
4. A mintázat-validáció és evaluator approval meglévő jogosultsági kapuinak megtartása.
5. Izolált PostgreSQL és alkalmazástesztek hozzáadása; production adatbázis, automatikus scheduler, Gemini-költség és outbound kommunikáció nélkül.
6. CI-eredmény, coverage és dokumentáció frissítése.

## 5. Biztonsági és működési korlátok

- Nincs automatikus outbound e-mail vagy ügyfélnek küldött AI-válasz.
- Nincs automatikus production deploy.
- Scheduler csak explicit konfigurációval, költségkorlátokkal és operátori kontrollal aktiválható.
- Production DB-migráció, Auth/RLS/GRANT, secret-változás és provider-élesítés csak külön release-ellenőrzés után.
- Nincs adat törlése; minden üzleti döntés auditálható.
- Az ismeretlen adat ismeretlen marad; hiányzó bizonyítékból nem következtetünk tényre.

## 6. Kapcsolódó dokumentumok

- [JARVIS Master Documentation](JARVIS_MASTER_DOCUMENTATION.md)
- [Current State and Next Steps](CURRENT_STATE_AND_NEXT_STEPS.md)
- [Capability Gap Report](JARVIS_CAPABILITY_GAP_REPORT.md)
- [Opportunity Engine](OPPORTUNITY_ENGINE.md)
- [CRM lifecycle](LEAD_CUSTOMER_LIFECYCLE.md)
- [Email workflow](LEAD_EMAIL_WORKFLOW.md)
- [Research worker operations](RESEARCH_WORKER_OPERATIONS.md)
