# JARVIS – aktuális állapot és még hiányzó feladatok

**Állapotfelvétel:** 2026-11-28
**Repo:** tamaszsolt2005-hub/jarvis-core
**Ág / PR:** feature/opportunity-center-readonly / PR #35 → main
**Vizsgált commit:** 3432f5fe542608303f73d9d8d026a6ce9087baaa
**Release:** PR nyitott, draft; nincs merge vagy új production deploy.

## Vezetői összefoglaló

A P1 leadkutatási és Opportunity/CRM kódfolyamatok nagy része elkészült a feature ágon. A fő blokkoló a böngészős CI: a tesztcsomag 83,17% line coverage-et ért el (82% a küszöb), 1350 teszt sikeres, 3 kihagyott, de a mobil fejléc-pozíciót vizsgáló teszt mindhárom böngészőben elbukott. A PostgreSQL-integráció, backup/restore, CodeQL és dependency audit sikeres volt.

## Legutóbbi CI bizonyíték

| Ellenőrzés | Állapot |
|---|---|
| Python / AppTest / Playwright csomag | 1350 sikeres, 3 sikertelen, 3 kihagyott |
| Line coverage | 83,17% – teljesíti a 82%-os célt |
| Mobil chat fejléc Chromium | sikertelen: mért y=13 px, elvárt legalább 96 px |
| Mobil chat fejléc Firefox | sikertelen: mért y=13 px, elvárt legalább 96 px |
| Mobil chat fejléc WebKit | sikertelen: mért y=13 px, elvárt legalább 96 px |
| Company research PostgreSQL integration | sikeres |
| Backup/restore integration | sikeres |
| CodeQL | sikeres |
| pip-audit | sikeres |

A böngészőteszt javításában a mobil viewportváltás után a lap tetejére állítjuk a scroll pozíciót, mielőtt a fejléc helyzetét mérjük. Ez kódmódosítás, még nem bizonyított javítás; a következő CI-nek kell zöldre igazolnia.

## P1 funkciók állapota

| Terület | Kódban | CI / integráció | Staging | Production |
|---|---|---|---|---|
| P1.1–P1.5 grounded lead research vertical slice | elkészült a feature ágon | több kapcsolódó teszt és integráció sikeres; teljes CI még piros | nem igazolt | teljes slice nincs release-elve |
| Lead Intelligence / jóváhagyás / evidence | elkészült | izolált DB- és Python-tesztek a CI-ben | nem igazolt | korábbi workflow-migrációk aktívak; friss UI nincs deployolva |
| CRM overdue és Task Center read-only híd | elkészült | regressziós tesztek a csomagban; teljes CI még piros | nem igazolt | új kód nincs release-elve |
| CRM felelős-hozzárendelés | elkészült; Auth-védett RPC, UI és audit | 12 pgTAP assertion izolált PostgreSQL-en sikeres | nincs külön staging DB | migráció nincs alkalmazva |
| Opportunity Discovery és review/evaluator gate | kódban elkészült | izolált PostgreSQL integráció sikeres; teljes üzleti E2E nincs élőben igazolva | nincs | új funkciók nincsenek merge-elve/deployolva |

## Production és Auth tények

- A production Supabase Auth adatbázisának olvasási ellenőrzése 0 Auth-felhasználót, 0 megerősített fiókot és 0 hozzárendelhető admin/operator fiókot adott.
- Emiatt a CRM felelőslista jelenleg üres; a régi közös jelszavas belépés nem kaphat személyhez kötött írási jogot.
- A CRM owner assignment migrációja csak a feature ágon van; productionben nem futott le.
- Nem történt e-mailküldés, Gemini worker futtatás vagy scheduler-aktiválás.
- Nem hoztunk létre fizetős staging DB-ágat. A költségmentes, meglévő JARVIS projekt kerete marad érvényben.

## Mi hiányzik még – prioritási sorrendben

1. **P0 – Mobil UI smoke zöldre hozása:** a scroll-ellenőrzés javítása utáni CI futtatása; 390/320 px login és chat, analitika screenshotok ellenőrzése Chromium/Firefox/WebKit alatt. A screenshot artifactot kézzel is át kell nézni.
2. **P0 – PR és release-integritás:** a feature ág 2 commit-tal le van maradva a main ágtól; a main változásainak biztonságos integrálása, új CI, majd CodeQL és dependency audit ellenőrzése. Merge csak minden kötelező check zöld állapotában.
3. **P1 – CRM Auth felhasználók:** a JARVIS Auth adminisztrátori beállítása és megerősített admin/operator fiókok létrehozása külön jóváhagyott adminfolyamatban. Amíg ez nincs, owner assignment UI nem tud érvényes felelőst kínálni.
4. **P1 – CRM teljes üzleti folyamat:** felelős-hozzárendelés production migrációja csak zöld CI és release review után; inbound válaszok strukturált CRM-frissítése; kapcsolattartó-duplikáció és biztonságos összevonás; owner/follow-up és konverziós riportok.
5. **P1 – Opportunity Discovery E2E:** cégkutatás → dossier/evidence → pain hypothesis → cross-company pattern → SaaS candidate → shortlist → assessment/approval teljes, emberi döntési kapukkal tesztelt folyamat. A fixture-alapú teszt nem helyettesíti a valós üzleti validációt.
6. **P1 – Üzleti validáció:** valós célügyfél-interjúk, pilot, probléma-súlyosság és fizetési hajlandóság mérése. A technikai candidate nem bizonyított termék/piaci illeszkedés.
7. **P2 – Provider költségkorlát:** a Google Search provider oldali query limit és az egyetlen hívásból eredő túllépés valódi hard cap védelme még nem teljes.
8. **P2 – Üzemeltetés:** worker/provider latency, hibaarány, token/költség trend, riasztás, több napi működési ciklus és release/rollback runbook.
9. **P2 – Auth/RLS és UI éles validáció:** külön staging adatbázis nélkül a productionben csak kontrollált, jóváhagyott smoke végezhető; Auth/JWT/RLS admin/operator/reader mátrixot release előtt igazolni kell.

## Következő végrehajtási lépések

- Megvárni a CI-t a mobil scroll-ellenőrzés javításával.
- Ha a UI smoke zöld, átnézni a screenshot artifactot és integrálni a main két új commitját.
- Friss CI után review-zni a teljes migrációs láncot; csak ezután lehet PR merge és production migráció.
- A production CRM owner assignment csak megerősített Auth admin/operator fiókok megléte után használható.

**Fontos:** a kódban elkészült, a CI-vel igazolt, a stagingben ellenőrzött és a productionben aktív állapot külön kategória. Jelenleg a teljes P1 csomag nem tekinthető productionben késznek.