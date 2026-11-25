# JARVIS – fejlesztési backlog

**Alapág:** `main`  
**Szabály:** ez a részletes technikai backlog az [elsődleges fejlesztési útitervet](JARVIS_DEVELOPMENT_ROADMAP.md) szolgálja ki. A munkát mindig a roadmap sorrendje vezérli; a backlog nem jogosít fel későbbi területek előrehozására.

## 1. Megbízhatóság és biztonság

1. **Backup workflow javítása és igazolása – KÉSZ.** A CLI importútvonal, S3 shell quoting és Python indentation hibák javítva PR #18–#20-ban. A `main` CI `45655131500` sikeres. A production backup workflow `45655512387` minden lépése sikeres: titkosított dump, S3/SSE-KMS feltöltés és ellenőrzés, letöltés/visszafejtés/hash, külön PostgreSQL 17 restore és táblainventár/rekordszám ellenőrzés. Ez a backup gate teljesült.
2. **Task approval race – kódoldali megoldás kész, productionre nem telepített.** A DB-szintű atomikus consume, expiry, principal/payload kötés, replay védelem és concurrency tesztek implementálva vannak a migrációban/RPC-ben. A production private schema és RPC-k hiányoznak; deploy és live smoke külön release gate.
3. **Teljes műveleti idempotencia.** A task approval/execute RPC operation ID-val és concurrency-védelemmel implementált és tesztelt. A task update/close teljes műveleti lefedettségét és a külső szolgáltatók idempotenciáját még külön igazolni kell.
4. **Audit fail-closed lefedettség.** Készíts érzékeny műveleti útvonal-leltárt, majd bizonyítsd teszttel, hogy auditírási hiba esetén minden kritikus művelet leáll.
5. **Külső e-mail integritás.** PR #23 hard-disable mainbe merge-elve (`c1364e8`); production deploy nem történt. SMTP nem kínál natív idempotency key-t. Provider API szükséges; Resend API dokumentáltan támogat `Idempotency-Key` fejlécet azonos request body-hoz 24 órás ablakban. Stabil event-key, változatlan payload/outbox és 24 órán túli automatikus retry tiltása szükséges. Provider-választás és secret/domain setup még hiányzik.

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


## Coverage-prioritás – 2026-11-25

A PR #23 head push CI (`45658587888`) 759 passed / 3 skipped és 90.75% line coverage (3 729/4 109) eredményt adott. A branch coverage nincs mérve. A célzott tesztelési sorrend:
1. `scripts/supabase_auth_rls_smoke.py`: 17% (42/243) – mockolt Auth/JWT/RLS hibautak, invalid/expired token, hiányzó konfiguráció, timeout és cleanup ágak.
2. `task_actions.py`: 81% (136/167) – approval hiány/lejárat/rossz principal, RPC hibák, idempotens ismétlés és audit-hiba.
3. `scripts/supabase_backup.py`: 93% (253/273) és `dashboard.py`: 94% (867/927) – hibakezelés, rollback/unknown kimenetek, külső szolgáltatás-határok.

A 90.75% line coverage jó általános alap, de nem helyettesíti az ág-lefedettséget, a live integration teszteket vagy a production smoke-ot.


## Production audit evidence – 2026-11-25 17:06 UTC

Read-only audit eredmény: PostgreSQL 17.11; 8 public tábla, 8 RLS enabled, 0 policy; anon és authenticated közvetlen SELECT/INSERT/UPDATE/DELETE jogosultság false minden public táblán; service_role teljes DML jogosultság true. `private` schema és task approval/operation táblák, `public.audit_chain_state`, execute RPC hiányzik; `tasks.operation_id` hiányzik. Migration ledger 5 bejegyzés (20261119). Advisor 8 INFO policy nélküli RLS táblák miatt. Nem történt production írás.

A külső provider idempotencia implementációjához dönteni kell a provider/API-ról. Resend jelenleg dokumentált `Idempotency-Key` támogatást ad a POST /emails végponton; azonos kulcs + azonos payload 24 órán belül ugyanazt az eredményt adja, más payload 409-et eredményez. Hivatkozás: https://resend.com/blog/engineering-idempotency-keys. SMTP maradjon hard-disabled, amíg a provider adapter, tartós idempotens outbox, tesztek, provider secret és ellenőrzött feladói domain nincs validálva.
