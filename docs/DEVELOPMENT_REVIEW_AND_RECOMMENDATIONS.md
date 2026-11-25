# JARVIS – fejlesztési backlog

**Alapág:** `main`  
**Szabály:** ez a részletes technikai backlog az [elsődleges fejlesztési útitervet](JARVIS_DEVELOPMENT_ROADMAP.md) szolgálja ki. A munkát mindig a roadmap sorrendje vezérli; a backlog nem jogosít fel későbbi területek előrehozására.

## 1. Megbízhatóság és biztonság

1. **Backup workflow javítása és igazolása – KÉSZ.** A CLI importútvonal, S3 shell quoting és Python indentation hibák javítva PR #18–#20-ban. A `main` CI `45655131500` sikeres. A production backup workflow `45655512387` minden lépése sikeres: titkosított dump, S3/SSE-KMS feltöltés és ellenőrzés, letöltés/visszafejtés/hash, külön PostgreSQL 17 restore és táblainventár/rekordszám ellenőrzés. Ez a backup gate teljesült.
2. **Task approval race.** Az egyszer használatos jóváhagyás jelenlegi UI-session kezelése nem garantál atomikus, több processz közötti one-use fogyasztást. Vezess be DB-szintű atomikus consume műveletet, lejáratot, principal- és payload-kötést, konkurens teszteket.
3. **Teljes műveleti idempotencia.** A task approval/execute RPC operation ID-val és concurrency-védelemmel implementált és tesztelt. A task update/close teljes műveleti lefedettségét és a külső szolgáltatók idempotenciáját még külön igazolni kell.
4. **Audit fail-closed lefedettség.** Készíts érzékeny műveleti útvonal-leltárt, majd bizonyítsd teszttel, hogy auditírási hiba esetén minden kritikus művelet leáll.
5. **Külső e-mail integritás.** SMTP unknown kimenetel után nincs bizonyított szolgáltatói idempotencia; az automatikus retry duplikált küldést okozhat. Kimenő küldés maradjon tiltott, amíg a deduplikáció és a végponttól végpontig tesztek nincsenek készen.

## 2. Supabase és jogosultságkezelés

**Aktuális állapot:** a production backup/restore gate teljesült (`45655512387`), de a schema/ledger drift továbbra is nyitott. A következő feladat friss read-only snapshot, nem migrációfuttatás.

- A két 20261117 migration ledger eltérés rendezési tervének bizonyítása.
- Production-shape PostgreSQL 17 migrációs replay és adatmegőrzési ellenőrzés.
- Audit/hash-chain/RBAC/idempotencia migrációk független SQL review-ja.
- Auth/RLS live smoke teszt meglévő, engedélyezett izolált Supabase környezetben.
- Auth session refresh, szerepkörváltozás, invalid/lejárt JWT, reader/operator/admin negatív tesztjei.
- Különválasztani és dokumentálni a user-JWT dashboard klienst és a háttérfolyamat service-role kliensét; a service-role kulcs soha ne kerüljön felhasználói kliensbe.
- [KÉSZ] A production logikai backup tényleges külön PostgreSQL 17 adatbázisba restore-ja igazolt (`45655512387`).
- A Supabase platformon kívüli mentési igények (Storage objektumok, Auth/Realtime és konfiguráció) tisztázása.

## 3. Önállóbb üzleti asszisztens

- Proaktív lead- és üzletiváltozás-figyelés minőségének és megbízhatóságának javítása.
- Lehetőségfelismerés indoklással, forrásokkal és bizonytalansági jelzéssel.
- Jóváhagyásra váró feladat- és következőlépés-javaslatok.
- Bizonyítani, hogy jóváhagyás nélkül nem történik külső vagy üzleti hatású végrehajtás.

## 4. Üzleti munkafolyamatok automatizálása

- Leadkutatás → minősítés → stratégia → feladat → jóváhagyás → utánkövetés → eredménymérés folyamat állapotmodellje.
- Minden lépés bemenetének, kimenetének, felelősének, hibakezelésének és idempotenciájának meghatározása.
- Megszakítás, folytatás, audit és eredménymérés végponttól végpontig tesztelése.

## 5. Tudás és hosszú távú memória

- Forrásolt, jogosultságkezelt üzleti kontextus és tartós visszakeresés.
- Leadek, ügyfelek, interakciók, döntések, feladatok és eredmények közötti kapcsolatok.
- Korábbi döntések és eredmények alapján visszakereshető tanulságok.
- Frissesség, bizonytalanság, megőrzés és törlés kezelése.
- Tények, források és modellkövetkeztetések világos elkülönítése.

## Közös mérnöki követelmények

- A tartós ág `main`; rövid életű feature ág csak integrációhoz.
- Egy változtatás = célzott kód + teszt + releváns dokumentáció.
- Production változtatás csak a külön dokumentált release gate-ek és konkrét jóváhagyás után.
- SMTP kimenő küldés maradjon tiltva, amíg az idempotencia és a végponttól végpontig tesztek nem teljesek.
