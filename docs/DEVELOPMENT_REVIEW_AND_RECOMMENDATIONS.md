# JARVIS – fejlesztési backlog

**Alapág:** `main`  
**Alap commit:** `bb5788e94b60a11185c45502b45d351ab2b2189b`  
**Szabály:** ez az egyetlen fejlesztési backlog. A megvalósítás státuszát a kóddal és az aktuális CI-vel kell ellenőrizni.

## P0 – következő javítások

1. **Backup workflow importhiba javítása.** A merge utáni `45624735241` futás a `scripts/supabase_backup.py` importjánál elbukott: `ModuleNotFoundError: jarvis_errors`. Javítsd az indítási/import útvonalat, adj regressziós tesztet, majd futtasd újra a workflow-t. Ne állíts sikeres backupot, amíg a teljes friss futás nem zöld.
2. **Task approval race.** Az egyszer használatos jóváhagyás jelenlegi UI-session kezelése nem garantál atomikus, több processz közötti one-use fogyasztást. Vezess be DB-szintű atomikus consume műveletet, lejáratot, principal- és payload-kötést, konkurens teszteket.
3. **Teljes műveleti idempotencia.** A task-create kapott stabil operation ID-t és deduplikációt. A task update/close és külső mellékhatások teljes replay/idempotencia védelme hiányos.
4. **Audit fail-closed lefedettség.** Készíts érzékeny műveleti útvonal-leltárt, majd bizonyítsd teszttel, hogy auditírási hiba esetén minden kritikus művelet leáll.
5. **Külső e-mail integritás.** SMTP unknown kimenetel után nincs bizonyított szolgáltatói idempotencia; az automatikus retry duplikált küldést okozhat. Kimenő küldés maradjon tiltott, amíg a deduplikáció és a végponttól végpontig tesztek nincsenek készen.

## P1 – biztonság és integráció

- Gemini/SMTP/IMAP timeout, retry, rate limit, részleges hiba és redakció integrációs mátrixának teljessé tétele.
- Titokredakció regressziós tesztjeinek fenntartása minden log/audit útvonalon.
- Auth/RLS live smoke teszt meglévő, engedélyezett izolált Supabase környezetben.
- Auth session refresh, szerepkörváltozás, invalid/lejárt JWT, reader/operator/admin negatív tesztjei.
- Különválasztani és dokumentálni a user-JWT dashboard klienst és a háttérfolyamat service-role kliensét; a service-role kulcs soha ne kerüljön felhasználói kliensbe.
- Ha tenantok kiszolgálása cél, külön tenant-azonosító és tenant-szintű RLS architektúra szükséges. A jelenlegi modell shared workspace, nem multi-tenant.

## P1 – production adatbázis

- A két 20261117 migration ledger eltérés rendezési tervének bizonyítása.
- Production-shape PostgreSQL 17 migrációs replay és adatmegőrzési ellenőrzés.
- Audit/hash-chain/RBAC/idempotencia migrációk független SQL review-ja.
- A production logikai backup tényleges külön adatbázisba restore-jának igazolása.
- A Supabase platformon kívüli mentési igények (Storage objektumok, Auth/Realtime és konfiguráció) tisztázása.

Részletek és aktuális tények: [Production állapot és migrációs terv](PRODUCTION_STATE_AND_MIGRATION_PLAN.md).

## P2 – termék és üzemeltetés

- RPO/RTO, retention, riasztás, kulcsrotáció, restore runbook és incidenskezelés meghatározása.
- Proaktív monitor és briefing production schedulerének tényleges működés- és hibafigyelése.
- Külső szolgáltatások költség-, rate-limit- és kvótamonitorozása.
- Üzleti eredmény metrikák: lead minőség, kutatási pontosság, utánkövetés konverziója, feladat-végrehajtás sikeressége.
- Ha az adat- vagy ügyfélszám nő, teljesítménytesztek, indexek és tenant izoláció újratervezése.

## Fejlesztési szabályok

- A tartós ág `main`; rövid életű feature ág csak integrációhoz.
- Egy változtatás = célzott kód + teszt + releváns dokumentáció.
- Ne készíts újabb dátumozott állapotjelentést, ha a backlog frissíthető.
- A production release gate nem backlog: azt külön dokumentum kezeli.
