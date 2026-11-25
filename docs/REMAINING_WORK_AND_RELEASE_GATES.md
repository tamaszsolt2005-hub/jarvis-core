# JARVIS – production és release gate-ek

Ez a dokumentum csak azt határozza meg, mi kell egy production változtatás vagy élesítés előtt. A fejlesztési teendők a [fejlesztési backlogban](DEVELOPMENT_REVIEW_AND_RECOMMENDATIONS.md) vannak.

## Jelenlegi döntési állapot

**Production Auth/RBAC: OFF. Production migráció: blokkolt. Production deploy: nincs jóváhagyva. A produkciós logikai backup és izolált PostgreSQL 17 restore 2026-11-25-én igazoltan sikeres.**

A `main` aktuális commitja `2e2a97e182687c9b9d018da99b87095b75a21054` (PR #20 squash merge). A main CI `45655131500` sikeres. Ez kódintegráció, nem production release.

## Kötelező kapuk

**2026-11-25 friss bizonyíték:** [backup+restore workflow #45655512387](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45655512387) minden lépése sikeres. A mentés ellenőrzési kapuja teljesült; a többi kapu ettől függetlenül nyitott.


### 1. Repository és CI
- [x] A pontos main commit (`2e2a97e`) CI-je befejezett és sikeres (`45655131500`).
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
