# JARVIS – hátralévő feladatok és release gate-ek

> **Állapotfrissítés:** 2026-11-25 14:11 CET  
> **Elsődleges munkavégzési ág:** `main`  
> **Részletes fejlesztési áttekintés:** [DEVELOPMENT_REVIEW_AND_RECOMMENDATIONS.md](DEVELOPMENT_REVIEW_AND_RECOMMENDATIONS.md)

Ez a dokumentum a korábbi checklisták státuszait a fenti felülvizsgálati időpontban ellenőrzött GitHub-adatokhoz igazítja. A történeti bejegyzések nem aktuális állapotjelentések; a jelen fejezet az irányadó.

## Aktuális repository állapot

- `main`: `2fb9081f80741692a05d08f805c04d0a23ad1350`
- PR #13 head: `32aef539c0128c1fedaa9e03768477433e93abe1`
- PR #13: draft, open, not merged.
- Branch összehasonlítás: 282 commit ahead, 5 behind (a dokumentációs main-commitok után ellenőrizve).
- [PR push CI #45620664359](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45620664359): sikeres.
- [PR CI #45620672894](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45620672894): backup-restore-integration sikeres, test job a felülvizsgálatkor futott.
- A korábbi `09bde885...` head sikeres CI-je nem bizonyítja az újabb `32aef539...` head teljes CI-jét.

## P0 – merge előtti feladatok

- [ ] Várd meg a `32aef539...` head teljes PR CI-jének sikerét.
- [ ] Review-zd a teljes PR diffet és a 282 commitnyi történetet.
- [ ] Ellenőrizd a migrációs fájlokat, RLS/GRANT szabályokat, Auth trust boundary-t, backup workflow-t és approval/idempotencia útvonalakat.
- [ ] Zárd le a dokumentációs ellentmondásokat; a fejlesztési review dokumentum legyen az összefoglaló státuszforrás.
- [ ] Ellenőrizd újra a mergeability-t közvetlenül a merge döntés előtt.
- [ ] Merge csak külön, kifejezett döntés után; utána a további munka `main`-en folytatódjon.

## P1 – alkalmazáskód és integrációk

- [ ] Több worker/process között atomikus, one-use approval consumption és párhuzamos race tesztek.
- [ ] Általános replay/idempotencia védelem a task- és külső mellékhatásokat végző műveletekhez.
- [ ] E-mail kézbesítési idempotencia, bizonytalan SMTP-kimenetel és retry-kezelés.
- [ ] Gemini/SMTP/IMAP kontrollált integrációs tesztek: timeout, retry, rate limit, részleges hiba és titokredakció.
- [ ] Audit fail-closed tesztek minden érzékeny műveleti útvonalra.
- [ ] Független kód- és SQL-review.

## P1 – Supabase / Auth / migráció

- [ ] Két 20261117 remote migration-ledger eltérés pontos CLI-kompatibilis reconciliation terve és független review-ja.
- [ ] Teljes catalog postcondition egyezés: owner, grant, policy, function ACL, SECURITY DEFINER, trigger, index és default privileges.
- [ ] Valós Auth-issued JWT/PostgREST smoke teszt, kizárólag már létező és kifejezetten engedélyezett izolált környezetben.
- [ ] A live smoke workflow szükséges titkainak és változóinak ellenőrzése, majd a futás bizonyítékának archiválása – csak ha az izolált környezet ténylegesen rendelkezésre áll.

## P1 – backup / recovery / operáció

- [ ] A konkrét production backup archívum külön adatbázisba való visszaállítása és post-restore jegyzőkönyv.
- [ ] AWS stack és OIDC trust aktuális státuszának ellenőrzése.
- [ ] Retention, riasztások, RPO/RTO, kulcsrotáció, incidenskezelés és restore runbook.
- [ ] A public-schema logikai backupon kívüli Supabase platform- és Storage mentési igények tisztázása.

## Production korlátozások

- Production Supabase read-only.
- Auth/RBAC production flag OFF.
- Tilos a külön jóváhagyás nélküli production DDL/DML, `supabase db push`, `supabase migration repair`, ledger edit, GRANT/REVOKE, RLS policy módosítás, Auth-user provisioning és AWS deploy.
- Új Supabase projekt vagy branch nem hozható létre.
- A GitHub Actions PostgreSQL 17 fixture a migrációs replay és recovery tesztek engedélyezett helye ebben a fázisban.

## Release döntés

**Jelen állapot: merge döntés függőben.** A PR legfrissebb CI-je a dokumentum készítésekor még nem zárult le teljesen, és a 282 commitnyi változáscsomag review-ja is szükséges. A production aktiválás ettől független, későbbi kapu.
