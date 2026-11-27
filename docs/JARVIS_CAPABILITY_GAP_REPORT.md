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
| Opportunity Engine | Pain hipotézisek, legalább két cégre épülő pattern-validáció, SaaS jelöltek, hatdimenziós score, approval | A pain → cross-company pattern → SaaS candidate automatikus teljes adatút nincs igazolva |
| Intelligence Graph | Forrásolt entitások és kapcsolatok, read-only vizualizáció | Származtatott nézet; nem helyettesíti a domain adatforrásokat |
| E-mail előkészítés | Személyre szabott draft, szerkesztés, külön jóváhagyás, stílus-visszajelzés | Küldés nincs engedélyezve és kódszinten tiltott |
| Kapcsolatfelvételi kontroll | Címzett-engedély, jogalap-feljegyzés, globális suppression, jogosultsági ellenőrző sor | A `ready_for_manual_review` nem küldési engedély |
| Audit / jogosultság | RLS, admin/operator műveletek, append-only eseménynaplók több workflow-ban | Teljes, staging JWT/Auth szerepkörtesztet és dashboard smoke-ot még dokumentálni kell |
| CI / mentés | PostgreSQL integrációs és backup/restore CI workflow | CI siker nem egyenlő production readiness-szel |

## 3. A fontosabb hiányzó képességek – prioritási sorrendben

### P0 – A rendszer megbízható, napi használatához szükséges

**1. A már meglévő kutatási ütemezés üzembiztossá tétele és operációs vezérlése**
- A `global-lead-research.yml` napi leadkutatást, a `company-research-refresh.yml` napi dossier-frissítést ütemez; mindkettő GitHub Actions cron workflow, secret/config gate-tel.
- A `company_research_refresh_job.py` stale dossier-kat választ, költség/rate limit mellett queue-z és egy korlátozott batch-et feldolgoz. Ez több a one-shot worker-alapnál, de önmagában még nem bizonyít élő, tartós üzemi működést.
- Kell kezelhető futtatási szabály: piac, gyakoriság, napi limit, batch limit, költségplafon, pause/resume és biztonságos kézi újraindítás.
- Kell operációs nézet: queued/running/retry/dead-letter jobok, utolsó siker, hibaok, költség és workflow futási állapot.
- Elfogadási feltétel: stagingben több egymást követő cron ciklus idempotensen lefut, a kvóta- és költségkorlátokat betartja, a hibák riasztást adnak, és minden eredmény auditálható.

**2. Teljes Opportunity Discovery adatút**
- A meglévő pain, pattern, opportunity és evaluator elemeket egy explicit indítású pipeline-ba kell kötni.
- Lead/dossier → bizonyítékos pain hipotézis → több cégen át történő deduplikáció/csoportosítás → market pattern → SaaS-jelölt → evaluator preview → emberi jóváhagyás.
- A minimum két külön céghez kötött bizonyíték csak szükséges minimum, nem elégséges piaci validáció.
- Elfogadási feltétel: ismert tesztadatokon a pipeline megismételhető, a források visszakövethetők, téves klaszterek emberileg javíthatók, és nincs automatikus jóváhagyás.

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

**6. Teljes CRM / ügyfél-életciklus**
- Egy helyen legyen látható lead → kapcsolat → beszélgetés → ajánlat → pilot → ügyfél → megtartás állapot.
- Következő teendők, felelős, határidő, üzleti eredmény és elvesztési ok.
- Duplikáció- és cégcsoport-kezelés, kapcsolat- és interakciótörténet.
- Jelenlegi Leadkezelő nem helyettesíti ezt a teljes CRM-et.

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

1. **Automatikus, felügyelhető cégkutatás** – schedulerrel, költségkontrollal és operátori vezérléssel.
2. **Bizonyítékból SaaS-lehetőség** – több cég problémáinak klaszterezése és emberi jóváhagyás.
3. **Leadből ügyfél** – teljes CRM, bejövő válaszfeldolgozás, ajánlat/pilot és valós üzleti eredménymérés.

Ez adná a legnagyobb különbséget a jelenlegi funkciók gyűjteménye és egy valóban használható, önállóan dolgozó JARVIS között.
