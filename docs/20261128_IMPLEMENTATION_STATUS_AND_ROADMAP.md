# JARVIS – aktuális funkcióleltár, hiánylista és fejlesztési terv

## Kiegészítés – P1/P2 fejlesztési lépések (2026-11-28)

- **P1 CRM konverziós tölcsér:** a státusz- és append-only eseménytörténetből számolt, deduplikált funnel-riport bekerült a CRM oldalra; az elvesztett leadek külön látszanak.
- **P2 Research Ops helyi riasztások:** a hibazsák, napi budget-kihasználtság és lejárt/hiányzó worker lease-ek figyelmeztetése megjelenik az operátori oldalon. Külső push/email értesítés nincs bekapcsolva.
- A friss mobilos üdvözlőfejléc-javítás és ezek az új változások csak a branch kódját jelentik addig, amíg az aktuális HEAD teljes CI-je nem zöld. Productionben nem aktívak.


## Korábbi állapotfelvétel – ca6ba391 (történeti napló)

A legfrissebb fejlesztési állapotot a javítási napló és hiányregiszter részletezi. Az azóta elkészült módosítások:

- Playwright böngészős smoke: login felület megjelenésének explicit megvárása; mobil chat fejléc 390/320 px-es elhelyezésének és túlcsordulásának ellenőrzése; login mező/gomb 390/320 px-es ellenőrzése és kis mobil screenshot.
- Research Ops dashboard: RPC-ből érkező számlálók biztonságos normalizálása; nulla committed budget helyes megjelenítése; regressziós tesztek.
- A 8412057 commit CI-je f-string szintaktikai hibával bukott a Research Ops dashboardon. A hibát a ca6ba391 commit javította. **A javító HEAD CI-je még nem igazolt; a coverage és az új screenshotok nem tekinthetők kész bizonyítéknak.**
- Az előző CI-futásban a PostgreSQL research integration, backup/restore integration, CodeQL és dependency audit sikeres volt; ez nem teszi sikeressé a teljes CI-t.

**Aktuális fókusz:** (1) a friss HEAD CI-hibamentességének igazolása; (2) a 320/390 px login és chat, valamint az analitika screenshotok újraellenőrzése; (3) Research Ops költség- és számlálóadatok edge case-ei; (4) Opportunity Discovery E2E; (5) CRM owner/follow-up és inbound email integráció; (6) élő provider-korlátok, monitoring és staging/production release-runbook.

A korábbi b22635b commitra vonatkozó CI/coverage pillanatkép történeti adat; nem a mostani HEAD eredménye. Production migráció, merge és deploy továbbra sincs igazolva.

**Frissítve:** 2026-11-28  
**Vizsgált ág:** `feature/opportunity-center-readonly`  
**PR:** #35 → `main`, nyitott, draft; a PR állapotát és CI-jét minden új commit után külön kell ellenőrizni.

## Friss dokumentációs állapot – 2026-11-28

A részletes, priorizált hiánylista és a legutóbbi párhuzamossági javítás naplója külön dokumentumba került: [JARVIS javítási napló és hiányregiszter](20261128_JARVIS_GAP_REGISTER.md).

- Legutóbbi ismert PR #35 HEAD a dokumentációs frissítés előtt: `d3e449e9acb39de6c4e83be75c495414b9f21a34`; PR nyitott, draft, nem merge-ölt.
- A rejected-opportunity assessment guard most `FOR SHARE` zárolással olvassa a SaaS-jelöltet; az approval pgTAP terv 12 assertionre bővült.
- A `ba210ce` kódcommit JARVIS CI, CodeQL és dependency audit futásai megszakadtak. A dokumentációs HEAD sikeres CI-je nincs igazolva; a korábbi 83,33%-os coverage nem friss HEAD-eredmény.
- Production migráció, merge és deploy nem történt a most dokumentált javítás részeként.

A hiányok végrehajtási sorrendje: (1) friss, zöld CI és migráció/security review; (2) CI izolált PostgreSQL-es Auth/RLS és UI smoke; (3) Opportunity Discovery teljes E2E; (4) ügyfélinterjú/pilot és fizetési hajlandóság; (5) CRM owner/follow-up és inbound email integráció; (6) scheduler, provider oldali hard budget és monitoring; (7) SaaS terméktervezési/fejlesztési pipeline. A részletes elfogadási feltételek a hiányregiszterben vannak.


> Ez a dokumentum a repositoryban dokumentált és az aktuális PR-ágon azonosított képességeket választja szét. A „kódban megvan” nem jelent automatikusan CI-vel igazolt, CI-ben vagy productiontól elkülönített tesztfutásban élő vagy productionben működő állapotot. Ahol a bizonyíték hiányzik, ott ezt külön jelezzük.

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
- Admin/operator pattern-validálás, további vizsgálat vagy elutasítás, kötelező indoklással és append-only előzményekkel.
- SaaS-jelöltek külön emberi review életciklusa: `under_review`, `shortlisted`, `rejected`; shortlist csak validált patternből, elutasítás terminális, a döntések append-only naplózottak.
- Elutasított SaaS-jelölt evaluator- és DB approval-védelemmel rendelkezik.
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
1. **Opportunity Discovery E2E:** pain → pattern → SaaS candidate → candidate review → evaluator → emberi döntés; a candidate review és a rejected státusz DB-szinten is védett, minden döntés auditált.
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
- [JARVIS javítási napló és hiányregiszter](20261128_JARVIS_GAP_REGISTER.md)
- [Opportunity Engine](OPPORTUNITY_ENGINE.md)
- [CRM lifecycle](LEAD_CUSTOMER_LIFECYCLE.md)
- [Email workflow](LEAD_EMAIL_WORKFLOW.md)
- [Research worker operations](RESEARCH_WORKER_OPERATIONS.md)


## Irányadó állapotfrissítés – 2026-11-28 16:32 CET

Ez a blokk felülírja a dokumentum korábbi, más HEAD-re, CI-futásra vagy release-állapotra vonatkozó „aktuális” pillanatképeit. A korábbi dátumozott részek történeti naplóként maradnak meg.

- **Vizsgált ág:** `feature/opportunity-center-readonly`; **PR:** [#35](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/35), nyitott, draft, nem merge-ölt; **vizsgált HEAD:** `cb17d197b17325e86b78b9565f8ba95528f66e02`.
- A PR API szerint a mergeability jelenleg `false`. A HEAD-hez a lekérdezéskor nem volt visszaadott PR workflow-run; ezért erre a commitra friss zöld CI, coverage, CodeQL vagy dependency-audit eredmény nem állítható.
- A korábban mért 83,3%-os coverage és korábbi sikeres integrációs/security jobok **nem** bizonyítják a jelenlegi HEAD állapotát. A legutóbbi ismert mobil böngészőteszt-hiba javításának eredményét új, a jelenlegi HEAD-hez kötött futásból kell igazolni.
- P1/P2 funkciók a feature branchben implementációs állapotúak; ez nem jelent production aktiválást. A PR migrációi nincsenek production adatbázison alkalmazva, a branch UI nincs production deployolva.
- A P2 Research Ops dashboard helyi riasztásai: dead-letter, budget-kihasználtság/túllépés és lejárt/hiányzó lease. Külső értesítés nincs bekötve.
- A scheduler kill switch kódban és workflow-ban fail-closed; a `JARVIS_COMPANY_RESEARCH_SCHEDULE_ENABLED` nincs engedélyezve. A workert és schedulert nem indítottuk el.
- A Gemini beépített Google Search grounding egyetlen kérésére nincs igazolt, konfigurálható query-count hard limit. A metadata utólagos elszámolásra használható, nem előzetes korlátozásra. A napi budget jelenlegi foglalása ezért nem garantálja az egyetlen hívás költségének plafonját.
- A production Auth könyvtár korábban ellenőrzött állapotában 0 felhasználó volt; CRM owner assignmenthez nincs aktív assignable Auth user. Ezt nem szabad automatikus user-létrehozással vagy meghívóval megkerülni.

### Környezeti döntés – nincs fizetős staging adatbázis

A projektben **nem hozunk létre külön Supabase development/staging ágat vagy fizetős staging projektet**. A CI migrációs és SQL-tesztjeihez kizárólag a workflow által felállított ideiglenes, izolált PostgreSQL használható. Ez nem staging és nem production. A production Supabase projekt marad az egyetlen tartós adatbázis; azon nincs próbamigráció és nincs tesztadat-módosítás. Éles migráció csak a release gate-ek lezárása után, ellenőrzött sorrendben és backup/rollback tervvel történhet. Az alkalmazás böngészős smoke-ja jelenleg a CI-ben elérhető tesztkörnyezetre korlátozódik; nem állítunk be külön fizetős staging infrastruktúrát.

### Következő kötelező munkák

1. A jelenlegi HEAD-re automatikus JARVIS CI indítása/megérkezése és teljes sikerének ellenőrzése; coverage legalább 82%.
2. A mobil login/chat és dashboard screenshotok friss artifactjainak ellenőrzése; a böngészőtesztek zöld eredménye önmagában nem helyettesíti a screenshot review-t.
3. CodeQL és dependency audit futtatása és zöld eredményének igazolása ugyanezen a HEAD-en.
4. Migrációs, RLS, GRANT, SECURITY DEFINER, search_path és Auth/JWT jogosultsági review.
5. P2: provideroldali query-korlát helyett egyenként vezérelt keresőadapter vagy más, bizonyítható alkalmazásszintű query-budget; alert history; költség/latency/usage idősoros megfigyelés.
6. P1 üzleti validáció: Opportunity Discovery végponttól végpontig, CRM owner/follow-up, ajánlat/pilot/outcome és valós ügyfélinterjúk. A technikai pontszám nem bizonyít fizetési hajlandóságot.
7. Release után: production migráció és deploy csak külön ellenőrzött lépésben; scheduler és outbound e-mail továbbra is kikapcsolva marad, amíg külön jóváhagyás nincs.

### Prioritási sorrend

- **P0 – release gate:** friss teljes CI, coverage ≥82%, CodeQL, dependency audit, migráció/security review, UI smoke és rollback/backup runbook.
- **P1 – üzleti folyamat:** Opportunity pain→pattern→SaaS candidate→review→assessment E2E; CRM owner és follow-up; inbound reply audit/CRM; ajánlat/pilot és valós WTP-validáció.
- **P2 – üzemi megbízhatóság:** valódi query/cost limit, alert history/notification (külön döntés után), provider latency/usage monitoring, scheduler többciklusos ellenőrzése az aktiválás előtt. A scheduler marad opt-in.
- **P3 – termékesítés:** PRD→backlog→prototípus→build/test/release, multi-tenant és billing csak akkor, ha külső SaaS értékesítési cél lesz.
