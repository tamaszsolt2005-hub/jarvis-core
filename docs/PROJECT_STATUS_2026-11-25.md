# JARVIS – projektállapot, hátralévő feladatok és lefedettség

**Állapotfelvétel:** 2026-11-25 (frissítve a PR #20 merge és backup/restore után)  
**Repository:** `tamaszsolt2005-hub/jarvis-core`  
**Main:** `2e2a97e182687c9b9d018da99b87095b75a21054`  
**Production Supabase:** `kiutreccucbegskxowek` (PostgreSQL 17.11)

> Ez a jelentés külön kezeli a kódbeli implementációt, CI-t, production backupot, production sémamódosítást és deployt. A sikeres backup/restore nem jelent production migrációt vagy deployt.

## 1. Vezetői összefoglaló

- PR #18, #19 és #20 squash merge-elve a `main` ágba.
- Aktuális main: `2e2a97e`; main CI run `45655131500` sikeres.
- PR #20 javította a S3 objektumellenőrző Python-blokk behúzását.
- **Production backup + ellenőrzés + restore: sikeres**, workflow-dispatch run `45655512387`.
- A backup futás minden lépése sikeres: age titkosított logikai dump, privát S3 feltöltés, SSE-KMS és KMS kulcs ellenőrzés, S3 objektum letöltés, age visszafejtés és manifest SHA-256 ellenőrzés, külön PostgreSQL 17 restore, 8 public tábla és kijelölt rekordszámok ellenőrzése.
- A restore izolált, eldobható runner konténerbe történt; a workflow summary szerint production DB írás nem történt.
- Production migration ledger/séma drift továbbra sincs rendezve; production DDL/DML, ledger repair, Auth/RBAC és deploy nem történt/engedélyezett.

## 2. Legutóbbi bizonyítékok

| Bizonyíték | Állapot | Mit igazol |
|---|---|---|
| Main CI `45655131500` | Sikeres | A `2e2a97e` main commit CI-je |
| PR #20 CI `45654575685` | Sikeres | A Python indentation javítás tesztjei |
| Backup workflow `45655512387` | Sikeres | Production dump → S3/KMS → letöltés/hash → izolált PG17 restore |
| Korábbi hibás backup `45654544915` | Sikertelen, már javított | PR #20 előtti indentation hiba; nem a jelenlegi eredmény |

Hivatkozások: [Main CI](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45655131500) · [PR #20](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/20) · [Sikeres backup+restore](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45655512387).

## 3. Az öt fő fejlesztési terület állapota

| # | Terület | Állapot |
|---|---|---|
| 1 | Megbízhatóság és biztonság | Kódjavítások és CI zöld; production backup+restore igazolt. Külső SMTP szolgáltatói idempotencia és teljes audit fail-closed lefedettség még nem igazolt. |
| 2 | Supabase és jogosultságkezelés | Részben előkészítve. Production drift friss read-only felmérése, migrációs rendezés, SQL review, deploy utáni RPC smoke és Auth/RLS validáció hátra van. |
| 3 | Önállóbb üzleti asszisztens | Részben implementálva. Leadkutatás, scoring, proaktív monitor és javaslati alapok vannak; minőségi mérés és éles működés nincs lezárva. |
| 4 | Üzleti munkafolyamatok automatizálása | Részben implementálva. Task és approval építőelemek vannak; teljes lead→eredménymérés E2E folyamat és üzleti KPI-k hiányoznak. |
| 5 | Tudás és hosszú távú memória | Alapok implementálva. Memória és analitika van; forrásolt, jogosultságkezelt, életciklus-kezelt tudásréteg minőségi bizonyítása hátra van. |

## 4. Elkészült és tesztekkel igazolt fejlesztések

- Backup CLI közvetlen futtatás importútvonalának javítása.
- S3 verification shell quoting és Python indentation javítása (PR #19/#20).
- DB-szintű egyszer használatos approval: principal/payload kötés, expiry/replay védelem, atomikus consume.
- Atomikus task+audit+operation RPC, operation ID és concurrency védelem.
- SMTP-attempt utáni bizonytalan kimenetel `unknown`; automatikus retry kizárása.
- Audit/hash-chain SQL és fix `search_path` hardening.
- Authenticated közvetlen task DML korlátozása; a service-role végső lockdown későbbre ütemezve.
- PostgreSQL 17 CI migrációs, pgTAP, katalógus és backup–restore integrációs tesztek.
- A tényleges production archívum külön PostgreSQL 17 restore próbája sikeres a run #45655512387-ben.

A legutóbbi korábban mért coverage: 90.75% line coverage, 759 passed / 3 skipped; ez a PR #20 utáni friss runból még nem újramért adat. Branch coverage nincs mérve. Korábbi artifact: [coverage XML](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45652611537/artifacts/15041113174).

## 5. Hátralévő feladatok és sorrend

| Prioritás | Feladat | Állapot | Következő bizonyíték |
|---|---|---|---|
| P0 | Production backup és restore | **Kész** | Run #45655512387 |
| P0 | Friss production schema + migration ledger read-only snapshot | Hátra / frissítendő | Új schema és remote ledger snapshot |
| P0 | 20261117 ledger drift rendezési terv | Hátra | A tényleges postcondition és a két verzió eredetének egyeztetése |
| P0 | Teljes migration lánc production-shape PG17 replay + adatmegőrzés | Részben kész | Friss, teljes lánc teszt és független SQL review |
| P0 | Audit/RBAC/idempotencia/approval production migrációs terv | Hátra | Pontos SQL review és külön production engedély |
| P1 | RPC-alapú app production deploy | Nem igazolt | Deploy target, secret-ek, health check |
| P1 | Deploy utáni task RPC smoke | Hátra | Élő RPC végrehajtás és régi write path kizárása |
| P1 | `20261125170000_enforce_atomic_task_write_privileges.sql` | Blokkolt, szándékosan | Csak deploy + RPC smoke után |
| P1 | Live Auth/JWT/RLS smoke | Hátra | Már létező, engedélyezett izolált Supabase környezet |
| P2 | Storage/Auth/Realtime/platform backup scope | Hátra | Logikai PostgreSQL backupon túli scope és runbook |
| P2 | Alacsony coverage modulok célzott tesztjei | Hátra | Új coverage artifact és célzott tesztek |
| P2 | Main branch protection / required checks | Ellenőrizendő | GitHub ruleset/branch protection read-only állapot |

## 6. Production Supabase – ismert korábbi állapot

A legutóbbi dokumentált read-only auditban:
- projekt `ACTIVE_HEALTHY`, PostgreSQL 17.11.0.019, régió `eu-west-1`;
- remote migration ledger öt visszanyert verziót tartalmazott;
- a két `20261117` migráció hatása látszott a sémában, de verzióik hiányoztak a ledgerből;
- 8 public tábla RLS-e engedélyezett volt, 0 policy-t talált a lekérdezés;
- `auth.users` üres volt;
- audit/hash-chain/RBAC/approval migrációk production alkalmazása nem volt igazolt.

**Fontos:** ez a 2026-11-25-i korábbi snapshot, nem friss ellenőrzés a backup után. Production módosítás előtt újra kell kérdezni.

## 7. Production tiltások és sorrend

Továbbra sem történt production DDL/DML, `supabase db push`, migration repair, ledger átírás, GRANT/REVOKE, RLS policy változtatás, Auth user provisioning vagy deploy. Auth/RBAC flag OFF.

Kötelező sorrend:
1. Backup+restore – **teljesült**.
2. Friss read-only production schema/ledger snapshot és drift egyeztetés.
3. SQL review és production migrációs terv jóváhagyása.
4. Engedélyezett migrációk szakaszos alkalmazása.
5. RPC-alapú app deploy és smoke.
6. Csak utána a végső service-role task DML lockdown.
7. Auth/RBAC bekapcsolás külön döntéssel.

