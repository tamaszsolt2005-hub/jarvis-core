# JARVIS – production és release gate-ek

Ez a dokumentum csak azt határozza meg, mi kell egy production változtatás vagy élesítés előtt. A fejlesztési teendők a [fejlesztési backlogban](DEVELOPMENT_REVIEW_AND_RECOMMENDATIONS.md) vannak.

## Jelenlegi döntési állapot

**Production Auth/RBAC: OFF. Production migráció: blokkolt. Production deploy: nincs jóváhagyva.**

A PR #13 merge-elve a `main` ágba (`bb5788e94b60a11185c45502b45d351ab2b2189b`). Ez kódintegráció, nem production release.

## Kötelező kapuk

### 1. Repository és CI
- A pontos main commit minden kötelező CI jobja befejezett és sikeres.
- A backup workflow teljes, friss futása sikeres; a dump, titkosítás, S3 feltöltés, letöltés, visszafejtés és hash ellenőrzés is igazolt.
- A tényleges production archívum külön, izolált PostgreSQL 17 adatbázisba történő restore-ja sikeres.
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

A production állapot részletes, időponthoz kötött tényállása: [Production állapot és migrációs terv](PRODUCTION_STATE_AND_MIGRATION_PLAN.md).
