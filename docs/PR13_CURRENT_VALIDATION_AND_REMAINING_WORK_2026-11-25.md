# PR #13 – aktuális ellenőrzési és hátralévő feladatjelentés

> **Frissítési megjegyzés (2026-11-25):** ez a jelentés a korábbi `7fc8875` állapotot rögzíti, ezért a későbbi Auth/approval/task-idempotency módosítások és a Jarvis productiontől való eltérések teljes, aktuális leltárához lásd: [PR #13 – branch-only változások és éles Jarvis hiányok](PR13_BRANCH_ONLY_CHANGES_AND_LIVE_GAPS_2026-11-25.md). A régi CI-eredmény nem igazolja az újabb commitok tesztjeit.

**Dátum:** 2026-11-25  
**Branch:** `feat/supabase-auth-rbac-foundation`  
**Ellenőrzött head:** `7fc8875b111a481bd95efbb386e034386dcecdb5`  
**PR:** [#13](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/13) – open, draft, unmerged  
**CI:** [JARVIS CI #1733 / run 45592450445](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45592450445) – success

## 1. Friss ellenőrzési eredmény

A PR head SHA-ja megegyezik a vizsgált commit SHA-val. A CI mindkét jobja sikeres:

- Python / AppTest / browser: **770 passed, 3 skipped**, **93.09% line coverage** (3,980 statement; 275 missed).
- CloudFormation template validation, Playwright böngészőtelepítés és Python compileall: sikeres.
- PostgreSQL 17 integrációs job: sikeres.
- Két `20261117` additive migráció drift/replay és legacy adatmegőrzési ellenőrzése: sikeres.
- Supabase CLI 3.4.0 migration-repair applied/reverted/applied fixture teszt: sikeres.
- Audit és shared-workspace RBAC migrációk, pgTAP security tesztek: sikeres.
- Catalog postcondition teszt: sikeres (tábla ownership, RLS/policy, grants, function ACL, trigger, index és default ACL ellenőrzések).
- Titkosított age backup → letöltés/visszafejtés/hash ellenőrzés → külön lokális PostgreSQL restore round-trip: sikeres.

A logban megjelenő két `division by zero` hiba szándékos failure-injection: a CI a megszakítás és az azt követő forward-recovery viselkedését teszteli; a teljes job ettől sikeresen zárult.

## 2. Elsődleges hátralévő feladatok

**3 elsődleges P0 release-gate maradt nyitva.** A repository/CI bizonyítékok jelentősen bővültek, de egyik kapu sem tekinthető productionben lezártnak.

### P0.1 – Production migration drift rendezése és független SQL review
- [x] Read-only production schema és migration-ledger snapshot dokumentálva.
- [x] Két `20261117` migráció ismételt replay-je és legacy rekordok megőrzése izolált PG17 fixture-ben.
- [x] Supabase CLI 3.4.0 `migration repair` applied/reverted/applied viselkedése lokális fixture-ben ellenőrizve.
- [x] Audit/RBAC migrációs replay, recovery és catalog postcondition tesztek zöld CI-ben.
- [ ] A két repo-only `20261117` verzió production ledgerbeli eltérésének pontos, külön review-zott rendezési javaslata.
- [ ] Független SQL/security review és production előtti, pontos precondition/postcondition + forward-recovery terv.
- **Korlát:** a lokális CLI-teszt nem engedélyezi és nem bizonyítja a production ledger javítását. Production repair/DDL csak külön, konkrét felhasználói jóváhagyással.

### P0.2 – Valódi production backup és külön adatbázisba restore
- [x] Izolált CI-ben titkosított backup/restore round-trip bizonyítva.
- [ ] AWS CloudFormation stack, OIDC trust, GitHub secrets/variables és bucket/KMS konfiguráció ellenőrzése.
- [ ] Titkosított production backup S3-ba, objektum letöltése, decrypt/hash/manifest validálás.
- [ ] Restore külön adatbázisba és dátumozott jegyzőkönyv (objektumazonosító, hash, tábla- és rekordszámok).
- **Korlát:** a CI round-trip nem production mentés és nem bizonyítja az AWS/S3 production útvonalat.

### P0.3 – Valós Supabase Auth/JWT/RLS validáció
- [x] Auth/JWT tesztharness és lokális PostgreSQL pgTAP security tesztek a repóban.
- [x] JWT role spoofing elleni regresszió tesztelve: a `user_metadata.role` nem írhatja felül a trusted `app_metadata.role` értéket.
- [ ] Valós Auth-issued JWT/PostgREST tesztfuttatás és archivált bizonyíték.
- [ ] Csak már létező, kifejezetten engedélyezett izolált Supabase környezet használható. A jelenlegi ellenőrzésben csak a Jarvis production projekt ismert, branch listája üres; új project/account/branch nem hozható létre.
- **Korlát:** a Jarvis production Supabase projekt read-only; production Auth flag OFF.

## 3. További, P1/P2 szintű feladatcsoportok

A három P0 kapun felül három további fejlesztési/üzleti feladatcsoport és egy üzemeltetési csoport marad:

1. **P1 – Dashboard és teljes alkalmazási Auth átállás:** minden DB-hívás principal/service-role besorolása, session lifecycle, fail-closed és user-JWT útvonalak teljes leltára.
2. **P1 – Jóváhagyási és üzleti mellékhatások:** approval race/replay/idempotencia, audit fail-closed, task/e-mail/lead módosító folyamatok.
3. **P1 – Külső integrációk:** Gemini, SMTP/IMAP, ütemezett workflow-k kontrollált integrációs és hibakezelési tesztjei.
4. **P2 – Üzemeltetés:** RPO/RTO, retention/riasztás, restore-gyakorlat, incidenskezelés és kulcsrotációs runbook.

## 4. Végrehajtási és biztonsági korlátok

- Production Supabase-en nem történt DDL/DML, migration repair, ledger edit, policy-változtatás vagy Auth-user provisioning.
- Production Auth/RBAC feature flag **OFF** marad.
- Nem jött létre új Supabase account, projekt vagy branch.
- A migrációs replay és repair-szemantika kizárólag a GitHub Actions izolált PostgreSQL 17 fixture-ben futott.
- PR #13 **draft és unmerged** marad; automatikus merge nem történt.

## 5. Következtetés

A repository/CI oldali elsődleges tesztelési munka jelenleg zöld: 770 Python teszt sikeres, a PostgreSQL 17 migrációs/security/catalog ellenőrzések és a lokális titkosított backup/restore is sikeres. **A hátralévő elsődleges feladatok száma 3 (P0.1–P0.3)**: production drift/change terv és független review, production backup/restore bizonyítása, valamint valós Auth/JWT/RLS validáció egy már létező és engedélyezett izolált Supabase környezetben. Ezek lezárása előtt production Auth/RBAC aktiválás és PR merge nem javasolt.
