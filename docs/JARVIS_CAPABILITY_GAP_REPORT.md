## Aktuális irányadó állapot – 2026-11-28 (frissítve)

A pillanatfelvétel alapja a PR #35 feature/opportunity-center-readonly ág ca6ba3919df766e4bc5bf6cf5a53e793e428f643 HEAD-je. PR #35 nyitott és draft; merge, production migráció és deploy nincs igazolva.

- A böngészős teszt login állapotnál megvárja a látható címet, jelszómezőt és belépés gombot. A mobil chat fejléc 390 és 320 px-es viewporton is pozíció- és túlcsordulás-ellenőrzést kapott; a login mező és gomb is ellenőrzött mindkét mobilméreten.
- A Research Ops dashboard a hibás/negatív számlálóadatokat biztonságosan normalizálja, és a nulla committed költséget külön kezeli; regressziós tesztek kerültek hozzá.
- A 8412057 commit CI-je f-string szintaktikai hibával bukott a Research Ops dashboardon. A ca6ba391 commit ezt javította; a javító commit friss CI-eredménye még nincs igazolva.
- Az előző futásban a PostgreSQL research integration és backup/restore integration, CodeQL és dependency audit sikeres volt, de a teljes JARVIS CI sikertelen volt. Coverage és az új böngészős screenshotok a javító HEAD-en még nem igazoltak.
- A 82%-os coverage minimum változatlan; régi coverage-érték nem helyettesíti a friss HEAD riportját.
- A PR migrációinak production alkalmazása és a dashboard production deployja nem történt meg.

A részletes prioritások és korlátok a JARVIS javítási naplóban és hiányregiszterben, valamint a friss implementációs roadmapben szerepelnek. Az alábbi korábbi dátumozott jelentés történeti állapotként marad meg.

# JARVIS – képességhiány- és prioritási jelentés

**Dátum:** 2026-11-27  
**Vizsgált kód:** `feature/opportunity-center-readonly`, PR #35  
**Vizsgált HEAD:** `b0965a7ab384fe97ea759ddeb7b63316d7fbb995`  
**PR állapot:** open, draft, nem merge-ölt; base: `feature/daily-hard-budget-cap`  
**CI pillanatfelvétel:** JARVIS CI run [46010506152](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/46010506152): PostgreSQL research integration és backup/restore sikeres; a Python/AppTest/browser teszt job a jelentés készítésekor még futott. A compileall lépés sikeres, a tesztlépés folyamatban volt. Ez nem végleges CI-eredmény.

## 1. Vezetői összefoglaló

A JARVIS-ban sok fontos belső üzleti asszisztensi és kutatási építőelem már létezik: chat, leadkutatás, cégdosszié, lead scoring, jóváhagyásos feladatkezelés, kutatási worker-alapok, Opportunity Engine, Intelligence Graph, Leadkezelő és e-mail-előkészítési workflow.

**A fő probléma jelenleg nem az, hogy hiányoznak az alapmodulok, hanem hogy több modul nincs még teljes, üzemszerű, végponttól végpontig összekötve és éles környezetben igazolva.** A JARVIS ezért jelenleg fejlesztési rendszer, nem tekinthető még önálló, folyamatosan működő, teljesen autonóm üzleti/SaaS ügynöknek.

Fontos különbségek:
- **Kódban implementált:** a funkció modulja vagy adatútja szerepel a vizsgált PR-ágon.
- **CI-ben ellenőrzött:** automatizált teszt igazolja az adott commiton, izolált környezetben.
- **Élőben igazolt:** valós, nem production staging/provider környezetben is kipróbált.
- **Production-kész:** migráció, Auth/RLS, üzemeltetés, monitoring, visszaállítás és release folyamat is jóváhagyott.
  
Ezek nem felcserélhető állapotok. A PR #35 még nincs merge-ölve, a benne lévő migrációk nem kerültek production adatbázisra, és a dashboard nincs production deployolva.

## 2. Ami már megvan a vizsgált kódban

| Terület | Jelenlegi képesség | Fontos korlát |
|---|---|---|
| Üzleti chat | Magyar nyelvű Gemini-alapú chat és üzleti kontextus | Élő szolgáltatói működés és konfigurációfüggő |
| Leadkutatás | Ország-/piacválasztásos, grounding-alapú cégkeresés, duplikációszűrés; napi GitHub Actions ütemezés | A workflow-k secret-gatedek; az élő, folyamatos működés és az operátori vezérlés külön igazolást igényel |
| Cégdosszié | Forrásolt tények, snapshotok, döntéshozói szakmai adatok | Auth-os snapshot olvasási útvonal külön ellenőrzést igényel |
| Kutatási worker | Queue, claim/lease, heartbeat, retry/dead-letter; ütemezett, költségkorlátos dossier-frissítő workflow | Operátori pause/resume, job-monitoring és stagingben igazolt tartós működés még hiányzik |
| Lead scoring | 0–100 prioritás, közös scoring primitive | A pontszám kutatási prioritás, nem üzleti siker-előrejelzés |
| Leadkezelő | Rangsorolt kártyák, dossier, elfogadás/elutasítás, megjegyzés, AI-megbeszélés | Nem teljes CRM és nem kapcsolatfelvételi engedély |
| Opportunity Engine | Forrásolt pain hipotézisek, automatikus cross-company candidate klaszterezés, draft SaaS-jelölt, hatdimenziós score és emberi approval | A klaszterezés heurisztikus; a pattern validálása, score preview és jóváhagyás emberi lépés; stagingben még nincs igazolva |
| Intelligence Graph | Forrásolt entitások és kapcsolatok, read-only vizualizáció | Származtatott nézet; nem helyettesíti a domain adatforrásokat |
| E-mail előkészítés | Személyre szabott draft, szerkesztés, külön jóváhagyás, stílus-visszajelzés | Küldés nincs engedélyezve és kódszinten tiltott |
| Kapcsolatfelvételi kontroll | Címzett-engedély, jogalap-feljegyzés, globális suppression, jogosultsági ellenőrző sor | A `ready_for_manual_review` nem küldési engedély |
| Audit / jogosultság | RLS, admin/operator műveletek, append-only eseménynaplók több workflow-ban | Teljes, staging JWT/Auth szerepkörtesztet és dashboard smoke-ot még dokumentálni kell |
| CI / mentés | PostgreSQL integrációs és backup/restore CI workflow | CI siker nem egyenlő production readiness-szel |

## 3. A fontosabb hiányzó képességek – prioritási sorrendben

### P0 – A rendszer megbízható, napi használatához szükséges

**1. A kutatási ütemezés üzembiztossá tétele – első pause/resume operációs réteg implementálva**
- A `global-lead-research.yml` napi leadkutatást, a `company-research-refresh.yml` napi dossier-frissítést ütemez; mindkettő GitHub Actions cron workflow, secret/config gate-tel.
- A `company_research_refresh_job.py` stale dossier-kat választ, költség/rate limit mellett queue-z és egy korlátozott batch-et feldolgoz. Ez több a one-shot worker-alapnál, de önmagában még nem bizonyít élő, tartós üzemi működést.
- Elkészült a Kutatási műveletek oldal: admin/operator pause/resume, reader read-only, indoklásos append-only audit, queued/running/retry/dead-letter számlálók, legutóbbi jobok és napi költségösszesítő. A pause a queue feltöltését és az atomikus claim RPC-t is megállítja; a már futó job befejeződhet.
- Még kell: piac szerinti konfigurálható gyakoriság, külső riasztás, idősoros provider/költség-monitoring, workflow-run megfigyelés és stagingben több napi ciklusos validáció.
- Elfogadási feltétel: stagingben több egymást követő cron ciklus idempotensen lefut, a kvóta- és költségkorlátokat betartja, a hibák riasztást adnak, és minden eredmény auditálható.

**2. Opportunity Discovery – az automatikus első szakasz már implementálva, validálás még hátravan**
- A cégkutatási prompt strukturált `pain_hypotheses` listát kér; a dossier csak pontosan groundingolt forrás URL-lel, kivonattal és korlátozott confidence értékkel fogadja el.
- A kutatási worker a snapshothoz köti és elmenti a pain rekordokat, majd a `market_pattern_discovery.py` determinisztikus, kategória- és tokenhasonlóság-alapú klaszterezést futtat.
- Legalább két különböző cég szükséges; a mintázat `candidate`, a SaaS-jelölt `draft` státuszú marad. Fingerprint és DB unique index biztosítja az ismételt futás idempotenciáját.
- A rendszer nem validál automatikusan, nem futtat automatikus pontozást, és nem hagy jóvá assessmentet. Az Opportunity Centerben admin/operator külön, kötelező indoklással validálhat, további vizsgálatra tehet vagy elutasíthat egy mintázatot; minden döntés append-only eseménynaplóba kerül. Ezután a validált mintázaton evaluator preview és külön assessment-jóváhagyás következhet.
- Korlát: a token/Jaccard klaszterezés heurisztikus; a stagingben mért precision/recall, téves klaszterek kezelése és valós pain coverage még nincs igazolva. A minimum két cég csak szükséges minimum, nem bizonyít fizetőképes piac.

**3. Auth/JWT/RLS teljes végponttól végpontig ellenőrzése**
- Admin/operator/reader/anon szerepkörök ellenőrzése valós JWT-vel, minden új migrációs táblán és RPC-n.
- Külön ellenőrizni kell a cégdosszié snapshot olvasási útját, a dashboard hibakezelését és a jogosultságvesztést.
- Elfogadási feltétel: reader csak olvas; anon nem fér hozzá; admin/operator kizárólag engedélyezett RPC-ken ír; nincs service-role dashboard megkerülés.

**4. Valós provider/staging smoke és költségvédelem**
- Gemini Search grounding, timeout, 429/503, retry, heartbeat, tokenhasználat és actual-cost mérés élő, nem production stagingben.
- A becsült költségfoglalás és tényleges költség közötti eltérést kezelni kell; overrun-védelem és riasztás szükséges.
- Elfogadási feltétel: kontrollált staging teszt dokumentált költséggel, hibainjektálással és bizonyított napi hard cap viselkedéssel.

**5. Reprodukálható telepítés és release-folyamat**
- Egyértelmű hosting-cél, konfigurációs/secret lista, staging és production környezet elkülönítése.
- Migrációs sorrend, backup előtti ellenőrzés, rollback/restore eljárás, deploy utáni smoke és incidens-visszaállítás.
- Elfogadási feltétel: staging deploy teljes dokumentált runbookkal; production csak külön jóváhagyással.

### P1 – A JARVIS üzleti értékét jelentősen növelő funkciók

**6. CRM / ügyfél-életciklus – első verzió implementálva, további bővítés szükséges**
- Az Ügyfélkapcsolatok oldal a jóváhagyott leadeket státusz szerint követi: jóváhagyott lead, kapcsolatfelvétel, válasz, minősítés, ajánlat, pilot, ügyfél, elvesztett.
- Admin/operator kézzel rögzíthet státuszváltozást, e-mail/telefon/megbeszélés/jegyzet interakciót és következő teendőt határidővel; az események append-only előzményként mentődnek.
- A művelet csak jóváhagyott leadre engedélyezett, RLS és authenticated RPC védi; reader csak olvas.
- Még hiányzik: felelős/owner kezelés, cégcsoport és duplikáció-összevonás, ajánlat/pilot dokumentum- és bevételkövetés, megtartás/lemorzsolódás, valós üzleti eredménymérés.
- A CRM nem küld e-mailt és nem válaszol automatikusan; a kimenő e-mail hard gate változatlanul aktív.

**7. Bejövő kommunikáció és emberi értesítési folyamat**
- Az `email-automation.yml` ütemezett inbox workflow-ja és az `email_inbox.py` már fogadja az új leveleket, leadhez kapcsolja a feladót, leállítja az utánkövetést, kategorizálja a választ, és az E-mail központban emberi felülvizsgálati értesítést jelenít meg.
- Érdeklődés esetén külön „Érdeklődő ügyfél válaszolt” jelzés készül; a levél tárgya és rövid előnézete látható.
- JARVIS nem válaszol automatikusan, nem ígér ajánlatot, nem küld follow-upot; a következő lépés emberi döntés.
- Még szükséges: stagingben IMAP/UID checkpoint és duplikációkezelés igazolása, több címzett/alias megbízható összekötése, külső push értesítési csatorna csak külön döntés esetén, valamint leiratkozás globális suppressionnel való teljes összekötése.

**8. Értékesítési és ajánlatkészítési folyamat**
- Jóváhagyott SaaS-ötletből testreszabott ajánlat, scope, ár, ROI, pilot terv és szerződés-előkészítés.
- Verziózott ajánlatok, belső jóváhagyás, státuszkövetés.
- Ár és ROI csak forrásolt üzleti feltételezésekkel, nem kitalált számokkal.

**9. Ügyfél-visszajelzés és valós piaci validáció**
- Interjúk, pilotok, fizetési hajlandóság, konverzió és megtartás strukturált rögzítése.
- Az Opportunity Score-t tényleges üzleti eredményekkel kell kalibrálni.
- A több cégnél észlelt hasonló probléma nem bizonyítja automatikusan, hogy fizetőképes SaaS-piac létezik.

**10. Megfigyelhetőség és riasztás**
- Központi log/trace, worker és provider hibaarány, queue késés, költség, kvóta, sikertelen migráció és backup-riasztás.
- Operátori dashboard és incidensnapló.
- Adatmegőrzési, titokmentesítési és hozzáférési szabályok.

### P2 – Későbbi, skálázási és autonómia-funkciók

**11. Többfelhasználós / többvállalatos SaaS-termékesítés**
- Tenant izoláció, szervezeti szerepkörök, meghívás, billing, usage limit és ügyfél-admin.
- Csak akkor P0, ha a cél rögtön külső ügyfeleknek értékesíthető JARVIS; belső egyfelhasználós használathoz későbbi.

**12. Önfejlesztő, de kontrollált ügynöki munkafolyamat**
- Önálló kutatási terv és végrehajtás, kódmódosítási javaslat, teszt/build és PR-előkészítés.
- Minden külső mellékhatás külön engedélykapuval; automatikus production deploy vagy e-mailküldés nem lehet alapértelmezett.

**13. Termékfejlesztési végrehajtás**
- SaaS-jelöltből specifikáció, prototípus, backlog, implementáció, QA, staging és release pipeline.
- Ez külön termék- és biztonsági projekt, nem következik automatikusan az Opportunity Engine meglétéből.

## 4. Javasolt végrehajtási sorrend

1. **PR #34/#35 lezárás előtti review:** stacked dependency, migration/RLS review, aktuális CI eredmény és dokumentáció.
2. **Auth/JWT/RLS staging-validáció:** anon/reader/operator/admin teszt, snapshot read path, RPC-k.
3. **Kutatási worker operációs réteg:** a meglévő napi workflow-k secret/config ellenőrzése, pause/resume, job-monitoring és költségriasztás.
4. **Opportunity Discovery vertical slice:** pain → pattern → SaaS candidate → evaluator, explicit indítással.
5. **Gemini staging smoke és hard budget:** valós usage, retry/heartbeat, költség-elszámolás.
6. **Teljes CRM és bejövő válaszkezelés bővítése:** a most bevezetett emberi válaszriasztásra építve, ügyfél-életciklus, interakciótörténet és külső értesítés külön döntésével.
7. **Ajánlat/pilot/ügyfél-validációs workflow.**
8. **Hosting és release runbook; staging deploy.**
9. **Production readiness review és külön döntés.**
10. **Később multi-tenant, billing és kontrollált önfejlesztő funkciók.**

## 5. Kifejezett biztonsági és scope-határok

- PR #35 nyitott draft; ez a jelentés nem engedély merge-re.
- A PR #35 migrációi repository/CI részei; production adatbázison nem futottak le.
- Nincs igazolt production deploy vagy hosting.
- A kimenő e-mailküldés `email_utils.py` fájlban kódszinten hard-disabled; ezt a jelentés nem javasolja feloldani.
- Az e-mail-jóváhagyás, kapcsolatfelvételi engedély, suppression és küldési képesség külön állapot.
- A `ready_for_manual_review` queue státusz nem küldési jogosultság.
- Nincs valós ügyfél-validáció bizonyítva pusztán a kód vagy CI alapján.
- A CI csak az adott commit és izolált tesztkörnyezet állapotát igazolja.

## 6. Rövid döntési javaslat

A következő fejlesztési fókusz **ne újabb dashboard-elemek hozzáadása legyen**, hanem három végponttól végpontig működő és mérhető folyamat:

1. **Automatikus, felügyelhető cégkutatás** – a meglévő napi cron workflow-k üzemi vezérlése, monitoringja, költségkontrollja és staging igazolása.
2. **Bizonyítékból SaaS-lehetőség** – dossier-ból forrásolt pain hipotézis, több céges klaszter, SaaS-jelölt, evaluator preview és emberi jóváhagyás.
3. **Leadből ügyfél** – CRM-életciklus, bejövő válaszok emberi értesítése, ajánlat/pilot és valós üzleti eredménymérés; automatikus ügyfélválasz nélkül.

Ez adná a legnagyobb különbséget a jelenlegi funkciók gyűjteménye és egy valóban használható, önállóan dolgozó JARVIS között.


## 7. Frissítés – bejövő ügyfélválaszok (2026-11-27)

- A bejövő levelek kategorizálása `interested`, `later`, `rejected`, `opt_out` vagy `unknown` értékre történik.
- Az E-mail központ **Beérkezett válaszok** füle a `logs` eseményeiből megjeleníti az ügyfélválaszokat, az érdeklődő válaszokat külön kiemelve.
- Az utánkövetés leáll; a levél rövidített előnézete és tárgya megjelenik.
- **Automatikus válaszadás nincs és nem is része a célfolyamatnak.** Minden további ügyfélkommunikáció előtt a felhasználó döntése szükséges.
- Ez alkalmazáson belüli jelzés, nem telefonos push vagy külső értesítés. A workflow csak akkor működik, ha a GitHub Actions secret/config gate engedélyezett és a szükséges IMAP/Supabase titkok elérhetők.


## 8. Frissítés – automatikus Opportunity Discovery első szakasz (2026-11-27)

A PR #35 fejlesztési ágban elkészült az automatikus út első, forrásbiztonságra épülő része:
- A kutatási provider explicit, strukturált pain hipotéziseket adhat vissza; csak pontosan groundingolt URL, forráskivonat, engedélyezett kategória és 0.10–0.75 confidence fogadható el.
- A pain hipotézis az immutable dossier snapshotban is szerepel, majd a worker külön `business_pain_hypotheses` rekordként menti.
- A `market_pattern_discovery.py` az összes nem elutasított, forrásolt pain rekordot determinisztikusan klaszerezi; legalább két különböző cég szükséges.
- Új mintázat `candidate`, a hozzá tartozó SaaS-jelölt `draft`; automatikus validálás, scoring és jóváhagyás nincs.
- A `20261127190000_cross_company_pattern_discovery.sql` migráció snapshot-szintű pain idempotenciát, pattern fingerprintet és automatikus SaaS-jelölt idempotenciát vezet be. A `20261127200000_market_pattern_review_workflow.sql` admin/operator review RPC-t, kötelező indoklást, append-only döntési eseményt és RLS-t ad. Mindkét migrációhoz CI pgTAP ellenőrzés és replay került.
- A változás még nincs stagingben vagy productionben igazolva; a migráció repository-only, production DB-n nem futott le. A lokális teszteket a felhasználó kérésére nem futtattuk.

- A dashboard már tartalmazza a mintázatok admin/operator felülvizsgálati vezérlőit és a döntési előzmények megjelenítését.


## 9. Frissítés – CRM ügyfél-életciklus első verzió (2026-11-27)

- Elkészült az Ügyfélkapcsolatok dashboard, amely csak jóváhagyott leadeket mutat.
- A CRM státuszai: approved_lead, contacted, responded, qualified, proposal, pilot, customer, lost.
- Admin/operator státuszt, kézzel rögzített interakciót és következő teendőt/határidőt menthet; minden esemény append-only.
- A SECURITY DEFINER RPC ellenőrzi a JWT szerepkört és a lead jóváhagyott állapotát; reader csak olvashat, anon nem fér hozzá.
- A CRM semmilyen levelet nem küld és nem indít follow-upot. A bejövő ügyfélválaszra továbbra is csak értesítés készül.
- Migráció: 20261127210000_lead_customer_lifecycle.sql; CI pgTAP teszt és migráció replay hozzáadva. Production DB-n nem futott le.
