# JARVIS – production és release gate-ek

Ez a dokumentum csak azt határozza meg, mi kell egy production változtatás vagy élesítés előtt. A fejlesztési teendők a [fejlesztési backlogban](DEVELOPMENT_REVIEW_AND_RECOMMENDATIONS.md) vannak.

## Jelenlegi döntési állapot

**Production Auth/RBAC: OFF. Production migráció: blokkolt. Production deploy: nincs jóváhagyva. A produkciós logikai backup és izolált PostgreSQL 17 restore 2026-11-25-én igazoltan sikeres.**

A `main` aktuális commitja a PR #22 merge után `1f401d0dacb1333c3050829fa710197dfa523c6e`. A PR #23 SMTP hard-disable még nyitott PR-ben van; a PR head push CI-je sikeres, a PR-triggerelt tesztjob utolsó ellenőrzéskor még futott. Ez kódintegráció, nem production release.

## Kötelező kapuk

**2026-11-25 friss bizonyíték:** [backup+restore workflow #45655512387](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45655512387) minden lépése sikeres. A mentés ellenőrzési kapuja teljesült; a többi kapu ettől függetlenül nyitott.


### 1. Repository és CI
- [x] PR #23 head push CI (`58d9e33`, run `45658587888`) mindkét jobja sikeres; 759 passed, 3 skipped, 90.75% line coverage.
- [ ] PR #23 pull_request workflow (`45658617612`) minden jobja sikeres – utolsó ellenőrzéskor a test job még futott.
- [x] A backup workflow teljes, friss futása sikeres (`45655512387`): dump, age titkosítás, S3 feltöltés, SSE-KMS/KMS key ellenőrzés, letöltés, visszafejtés és manifest SHA-256 ellenőrzés.
- [x] A tényleges production archívum külön, izolált PostgreSQL 17 konténerbe restore-olása sikeres; 8 public tábla és kijelölt rekordszámok ellenőrizve.
- A sikertelen vagy futó workflow nem tekinthető sikeresnek.

### 2. Migration drift
- Friss read-only production schema és remote ledger snapshot készült.
- A két 20261117 verzió ledger-eltérése dokumentáltan és függetlenül rendezett.
- Az öt visszanyert történeti migráció és a repository migrációk tartalma/postconditionjei ellenőrzöttek.
- A teljes migrációs sorrend production-shape izolált PostgreSQL 17 környezetben sikeres.
- A pontos SQL-készletet független review és külön, konkrét production jóváhagyás fedi.

### 3. Auth/RLS
- A live Auth/JWT/RLS smoke csak már létező, kifejezetten engedélyezett izolált Supabase környezetben sikeres.
- Admin Auth user, szerepkörök, session refresh, invalid/lejárt token és admin/operator/reader jogosultságok ellenőrzöttek.
- A production RLS/GRANT utófeltételek és visszaellenőrző lekérdezések előre definiáltak.
- Auth/RBAC flag csak a migráció után, külön jóváhagyással kapcsolható be.

### 4. Üzemeltetés
- RPO/RTO, retention, riasztás, kulcsrotáció, hozzáférés és incidenskezelés dokumentált.
- Restore runbook és felelősök kijelölve.
- A logikai DB backup határain túli igények (Storage objektumok, Auth/Realtime platformadatok, projektkonfiguráció) kezelése tisztázott.

## Kifejezetten tiltott külön jóváhagyás nélkül

- Production DDL/DML és adatírás.
- `supabase db push`, `supabase migration repair`, migration ledger kézi átírása.
- GRANT/REVOKE, RLS policy és Auth user módosítás.
- Production Auth/RBAC feature flag bekapcsolása.
- AWS production deploy vagy backup infrastruktúra változtatása.
- Új Supabase projekt vagy branch létrehozása.

A backup sikeres, de ez nem jelenti a Supabase migration drift vagy az élesítés lezárását. A production állapot részletes, időponthoz kötött tényállása: [Production állapot és migrációs terv](PRODUCTION_STATE_AND_MIGRATION_PLAN.md).


## Friss audit és CI állapot – 2026-11-25

- PR #22 squash merge-elve; main commit `1f401d0dacb1333c3050829fa710197dfa523c6e`.
- PR #23 nyitott; push CI [45658587888](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45658587888) sikeres (759 passed, 3 skipped, 90.75% line coverage), PR CI [45658617612](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45658617612) még nem zárult le az utolsó ellenőrzéskor.
- A production read-only audit szerint a `private` schema, a structured logs mezők, a `tasks.operation_id`, az audit-chain state, a private approval táblák és a task/approval RPC-k hiányoznak. Nyolc public tábla RLS-enabled, de policy nélküli; a remote ledger 5 migrációt tartalmaz, a két 20261117 verzió hiányzik.
- A két 20261117 migráció sémabeli hatása látható (`leads.website`, `logs.level`), de a ledger eltérése nincs rendezve. A CI fixture ezt modellezi és teszteli, nem javítja a production ledgert.
- A PR #23 kódszinten hard-disable-re állítja a kimenő SMTP-t és letiltja a workflow sender lépést; ez még nem része a mainnek, amíg a PR nincs merge-elve. A GitHub secret értékekhez nem nyúltunk. SMTP provider idempotencia/live E2E bizonyíték továbbra sincs.
- A production DDL/DML, migration repair, grants, RLS, Auth provisioning és deploy továbbra is tiltott külön jóváhagyás nélkül.

A release gate-ek **nem teljesültek** pusztán attól, hogy a PR CI zöld: előbb drift-egyeztetés, teljes PG17 replay, SQL review, külön production jóváhagyás, majd deploy és RPC smoke szükséges.


## PR #23 és coverage frissítés – 2026-11-25

- A PR #23 push workflow teljesen zöld: [45658587888](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45658587888). A backup–restore és a test job is sikeres.
- A PR workflow [45658617612](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45658617612) backup–restore jobja sikeres; a test job utolsó ismert állapota futó Playwright install. A PR nem merge-elhető, amíg ez nem zárul sikeresen.
- A PR head coverage-e 90.75% line coverage (3 729/4 109), 759 passed / 3 skipped; branch coverage nincs mérve. [Artifact](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45658587888/artifacts/15043089238).
- A PR #23 hard-disable csak merge után kerül a mainbe; production SMTP konfigurációt/secreteket és production alkalmazást nem módosít.
