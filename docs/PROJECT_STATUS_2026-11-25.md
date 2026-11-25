# JARVIS – projektállapot, hátralévő feladatok és lefedettség

**Állapotfelvétel:** 2026-11-25 (frissítve a PR #20 merge és backup/restore után)  
**Repository:** `tamaszsolt2005-hub/jarvis-core`  
**Main:** `71d6a1cdc755607a9598bf9b2c19c50730f5e036` (PR #21 squash merge)  
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



## 8. Frissített ellenőrzési eredmények – 2026-11-25, PR #21 után

**Main:** PR #21 squash merge-elve; aktuális commit: `71d6a1cdc755607a9598bf9b2c19c50730f5e036`. A PR #21 mindkét workflow-futásában mindkét job sikeres: [run 45656372633](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45656372633) és [run 45656331519](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45656331519). A backup/restore job a 20261117 drift fixture-t, az audit/RBAC pgTAP- és katalógus-ellenőrzéseket, valamint a titkosított backup–restore kört is lefuttatta. Ezek izolált PostgreSQL 17 tesztek, nem production migrációk.

**Production read-only snapshot (2026-11-25, 16:44 UTC körüli lekérdezések):**
- A projekt elérhető; a public sémában 8 tábla található, mindegyiknél RLS enabled, de 0 RLS policy.
- A `private` séma nem létezik (nem pusztán üres).
- A remote migration ledger továbbra is pontosan 5 verziót tartalmaz: `20261119191911`, `20261119192040`, `20261119192145`, `20261119192412`, `20261119192559`.
- A `leads.website` és `logs.level` oszlop létezik, de a két `20261117` migráció verziója nincs a ledgerben. A `20261119192040_complete_jarvis_runtime_schema.sql` nem hozza létre ezeket az oszlopokat.
- A `public.logs` továbbra is legacy oszlopkészletű (`id`, `module`, `message`, `created_at`, `level`); hiányoznak a strukturált auditmezők és a hash-chain mezők.
- A `public.tasks.operation_id` hiányzik; a `public.audit_chain_state` tábla nincs jelen.
- A `private.task_approvals`, `private.task_action_operations` táblák és az approval/task RPC-k productionben nem találhatók.
- A közvetlen `anon` és `authenticated` DML-jogok a public táblákon vissza vannak vonva; a `service_role` a `tasks` és `logs` táblákon teljes DML/DDL-jellegű táblajogokat tartalmazó grantkészlettel rendelkezik (SELECT/INSERT/UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER).
- Security Advisor: 8 INFO jelzés, mind RLS policy nélküli táblákra. Performance Advisor: 7 használatlan indexre vonatkozó INFO jelzés. Health Advisor: nincs találat.

**Kód- és működési következtetések:**
- A `task_actions.py` egyetlen `execute_approved_task_action` RPC-t hív; mivel ez a RPC productionben hiányzik, a kód jelenlegi production adatbázissal nem tekinthető élesben működőképesnek. A végső `20261125170000` service-role task DML-lockdown migráció továbbra is blokkolt.
- Az `audit_event` strukturált mezőket ír a `logs` táblába, és hiba esetén `False`-t ad. A jelenlegi production oszlopkészlet ezeket nem tartalmazza, ezért az auditot előfeltételként használó érzékeny műveleteknek fail-closed módon meg kell állniuk; az éles RPC/audit működés ettől még nincs bizonyítva.
- A kimenő SMTP-küldés külön kódmódosításig hard-disabled: `email_utils.EMAIL_DELIVERY_ENABLED = False`, nem környezeti változóból olvasott kapcsoló. A `send_email()` azonnal, Auth/DB/secret elérés előtt hibával leáll; a scheduled outbound workflow-lépés is explicit módon ki van kapcsolva. A chatből készített tervezet és jóváhagyási UI megmarad, de a tényleges küldés nem lehetséges. A bejövő IMAP-válaszok és leiratkozások figyelése külön konfigurációval tovább működhet. A `send_unknown` állapot és az automatikus retry tiltása továbbra is tesztelt; a külső SMTP-szolgáltató idempotenciája és a live E2E nincs igazolva.
- A fail-closed audit és SMTP-állapotkezelés regressziós tesztjei léteznek, de ezek izolált unit/CI tesztek; nem helyettesítik a production schema és a külső szolgáltató validálását.

**Változtatási határ:** az audit során nem történt production DDL/DML, migration repair, GRANT/REVOKE, RLS-módosítás, Auth provisioning vagy deploy. A következő lépés kizárólag drift-egyeztetés, SQL review és production-shape migrációs replay; éles módosítás külön jóváhagyás nélkül továbbra sem végezhető.


**Kimenő e-mail biztonsági kapu – PR #23:** a kimenő SMTP-küldés kódszinten letiltva, a környezeti `EMAIL_DELIVERY_ENABLED` érték nem képes aktiválni. A scheduled küldési lépés workflow-szinten is tiltott; az inbound IMAP monitor külön maradt. Újraengedélyezés kizárólag külön security review, szolgáltatói idempotencia-bizonyíték és célzott E2E tesztek után történhet.
