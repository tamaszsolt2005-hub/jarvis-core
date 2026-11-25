> **Aktuális státuszfrissítés (2026-11-25):** A régi backlog egyes pontjai azóta elkészültek. A kész kód és CI-bizonyíték, valamint a még hátralévő production feladatok részletes, dátumozott állapota a [projektállapot-jelentésben](PROJECT_STATUS_2026-11-25.md) található. A korábbi alábbi pontok nem tekintendők mind nyitottnak: a task approval race, task operation idempotencia, SMTP unknown/no-retry kezelés, backup CLI importhiba és a PostgreSQL 17 izolált backup/restore teszt elkészült. A PR #19 S3 ellenőrzési javítása még CI/merge folyamatban volt az állapotfelvételkor.

# JARVIS – fejlesztési backlog

**Alapág:** `main`  
**Szabály:** ez a részletes technikai backlog az [elsődleges fejlesztési útitervet](JARVIS_DEVELOPMENT_ROADMAP.md) szolgálja ki. A munkát mindig a roadmap sorrendje vezérli; a backlog nem jogosít fel későbbi területek előrehozására.

## 1. Megbízhatóság és biztonság

1. **Backup workflow importhiba javítása.** A merge utáni `45624735241` futás a `scripts/supabase_backup.py` importjánál elbukott: `ModuleNotFoundError: jarvis_errors`. A kivizsgálás két hibát azonosított: közvetlen scriptindításkor a repository gyökere nincs a Python importútvonalán, továbbá a workflow konfigurációellenőrzése escape-elt Bash változókat használt. Mindkettőhöz regressziós teszt szükséges; ezután futtasd újra a workflow-t. Ne állíts sikeres backupot, amíg a teljes friss futás nem zöld.
2. **Task approval race.** Az egyszer használatos jóváhagyás jelenlegi UI-session kezelése nem garantál atomikus, több processz közötti one-use fogyasztást. Vezess be DB-szintű atomikus consume műveletet, lejáratot, principal- és payload-kötést, konkurens teszteket.
3. **Teljes műveleti idempotencia.** A task-create kapott stabil operation ID-t és deduplikációt. A task update/close és külső mellékhatások teljes replay/idempotencia védelme hiányos.
4. **Audit fail-closed lefedettség.** Készíts érzékeny műveleti útvonal-leltárt, majd bizonyítsd teszttel, hogy auditírási hiba esetén minden kritikus művelet leáll.
5. **Külső e-mail integritás.** SMTP unknown kimenetel után nincs bizonyított szolgáltatói idempotencia; az automatikus retry duplikált küldést okozhat. Kimenő küldés maradjon tiltott, amíg a deduplikáció és a végponttól végpontig tesztek nincsenek készen.

## 2. Supabase és jogosultságkezelés

- A két 20261117 migration ledger eltérés rendezési tervének bizonyítása.
- Production-shape PostgreSQL 17 migrációs replay és adatmegőrzési ellenőrzés.
- Audit/hash-chain/RBAC/idempotencia migrációk független SQL review-ja.
- Auth/RLS live smoke teszt meglévő, engedélyezett izolált Supabase környezetben.
- Auth session refresh, szerepkörváltozás, invalid/lejárt JWT, reader/operator/admin negatív tesztjei.
- Különválasztani és dokumentálni a user-JWT dashboard klienst és a háttérfolyamat service-role kliensét; a service-role kulcs soha ne kerüljön felhasználói kliensbe.
- A production logikai backup tényleges külön adatbázisba restore-jának igazolása.
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
