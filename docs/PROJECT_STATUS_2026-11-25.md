# JARVIS – projektállapot, hátralévő feladatok és lefedettség

**Állapotfelvétel:** 2026-11-25  
**Repository:** `tamaszsolt2005-hub/jarvis-core`  
**Production Supabase:** `kiutreccucbegskxowek` (PostgreSQL 17.11)  
**Cél:** a bizonyított fejlesztési eredmények és az élesítéshez szükséges hátralévő lépések szétválasztása.

> Ez a jelentés nem tekinti a CI-ben izolált PostgreSQL-en sikeres migrációt vagy backup/restore tesztet production változtatásnak. A production DDL, DML, migration-ledger javítás és deploy külön release-lépés.

## 1. Vezetői összefoglaló

- **PR #18:** összevonva a `main` ágba; merge commit: `0f02a4399df530a6e3b31314e3cd4e7b46da0a2b`.
- **PR #19:** nyitott, nem merge-ölt javító PR az S3 backup ellenőrzés shell/Python idézőjelezési hibájára. Head: `bbca0bb0668639ca39c6b7b4cf3e6ec9521d18ca`.
- **PR #19 CI, run #45652611537:** mindkét job sikeres (`test`, `backup-restore-integration`). A teszt job eredménye 759 passed, 3 skipped, 90.75% line coverage. A dokumentációs commit után indult #45653353882 futás az állapotfrissítéskor még futott.
- **Legutóbbi teljes, befejezett CI a PR #19 kódjavításán:** run #45652611537, commit `bbca0bb0668639ca39c6b7b4cf3e6ec9521d18ca`: 759 passed, 3 skipped, 90.75% line coverage. A coverage XML artifact [itt érhető el](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45652611537/artifacts/15041113174).
- **Production backup:** a run #45652336576 elkészítette és S3-ba feltöltötte a titkosított logikai DB-archívumot, de az objektum-ellenőrzés idézőjelhibával elbukott. A letöltés/hash ellenőrzés és a tényleges archívum izolált restore-ja ennél a production backupnál nem igazolt.
- **Production adatbázis:** a jelentés készítésekor nem történt DDL/DML vagy migration-ledger módosítás. Az aktuális read-only ledger továbbra is öt verziót mutat.
- **Deploy:** az új RPC-alapú alkalmazás production telepítése nem igazolt; a végleges service-role task DML-lockdown migrációt ezért tilos előrehozni.

## 2. Elkészült és tesztekkel igazolt fejlesztések

| Terület | Eredmény | Bizonyíték / korlát |
|---|---|---|
| Backup CLI import | Közvetlen scriptindításkor a repo root importútvonal kezelése javítva; regressziós teszt hozzáadva | A CI isolated backup/restore jobja zöld |
| Task approval | Egyszer használatos, principal- és payload-kötött DB approval; expiry/replay védelem; atomikus consume és task+audit+operation RPC | PostgreSQL 17 pgTAP és valódi párhuzamos végrehajtási teszt zöld |
| Task idempotencia | Operation ID és concurrency-védelem; duplikált művelet nem hoz létre második taskot | CI concurrency setup/execute/verify zöld |
| SMTP bizonytalan kimenetel | SMTP-attempt utáni bizonytalan eredmény `unknown`; automatikus retry kizárva | Unit/regressziós tesztek; szolgáltatói end-to-end idempotencia ettől még nincs bizonyítva |
| Audit/hash chain | Audit mezők, hash-chain SQL, fix `search_path` hardening | Izolált PostgreSQL 17 migrációs és pgTAP tesztek |
| RBAC/RLS | Közvetlen authenticated task DML korlátozása; service-role legacy write path csak későbbi migrációban záródik | 34 shared-workspace pgTAP assertion és catalog postcondition zöld |
| Migration drift teszt | A két 20261117-es hiányzó ledger-verzió helyzetének izolált fixture-ben modellezése; idempotens SQL és CLI repair ledger-only teszt | Ez nem production ledger-repair, és nem helyettesíti az élő séma újbóli összevetését |
| Backup–restore integráció | Titkosított dump, letöltés/visszafejtés/hash és izolált PostgreSQL 17 restore teszt | CI-ben sikeres; nem a production S3-archívum visszaállítása |
| S3 ellenőrzési kódhiba | Python/Bash idézőjelütközés javítva a PR #19-ben | A PR #19 backup-restore jobja már zöld; a teljes CI még futott a mérés pillanatában |

## 3. Még hátralévő feladatok és nehézség

A nehézség 1–5 skálán: 1 = egyszerű, 5 = nagy kockázatú/összetett. A becslés a jelenlegi ismert állapotot és a szükséges ellenőrzéseket veszi figyelembe.

| Prioritás | Feladat | Állapot | Nehézség | Miért / következő bizonyíték |
|---|---|---|---:|---|
| P0 | PR #19 teljes CI lezárása, majd review és merge | Folyamatban | 1/5 | A backup-restore job zöld; a fő teszt job eredményét még meg kell várni |
| P0 | Javított production backup workflow újrafuttatása | Hátra van | 2/5 | A meglévő S3 objektum feltöltése önmagában nem elég; friss futásban letöltés, titkosítási/hash ellenőrzés és izolált restore kell |
| P0 | Friss production schema + migration ledger read-only snapshot és drift elemzés | Részben kész / újraellenőrzendő | 4/5 | A remote ledger öt verziót tartalmaz; a két 20261117 migration hatása látszott, de verzióik hiányoztak a ledgerből |
| P0 | A hiányzó ledger-bejegyzések biztonságos rendezése | Hátra van | 5/5 | Tilos vakon SQL-t újrafuttatni vagy automatikusan `migration repair`-t használni; pontos postcondition és review kell |
| P0 | Audit/RBAC/idempotencia migrációs lánc production tervének jóváhagyása | Hátra van | 4/5 | A teljes lánc izolált PG17-en tesztelt, de production sémához illesztett végső SQL-review és konkrét engedély szükséges |
| P1 | Új RPC-alapú alkalmazás deployja | Hátra van / nincs igazolva | 3/5 | Környezet, secret-ek, release target és health check ellenőrzése; Auth/RBAC flag maradjon OFF |
| P1 | Deploy utáni task RPC smoke és régi útvonalak ellenőrzése | Hátra van | 3/5 | Csak a ténylegesen telepített appal bizonyítható, hogy minden task művelet az új RPC-t használja |
| P1 | Végleges service-role task DML lockdown (`20261125170000`) | Blokkolt, szándékosan | 3/5 | Kizárólag az új app deployja és RPC smoke sikere után; korai futtatása leállást okozhat |
| P1 | Live Auth/JWT/RLS smoke és szerepkörök validálása | Hátra van | 4/5 | Meglévő, engedélyezett izolált környezet és tesztidentitások szükségesek; production Auth/RBAC flag nem kapcsolható be automatikusan |
| P2 | Storage/Auth/Realtime/platform konfiguráció backup-scope tisztázása | Hátra van | 3/5 | A logikai PostgreSQL backup nem teljes Supabase platform backup |
| P2 | Alacsonyabb lefedettségű modulok célzott tesztjei | Hátra van | 3/5 | Különösen `scripts/supabase_auth_rls_smoke.py` és `task_actions.py`; előbb a tesztelhetőségi határokat kell tisztázni |
| P2 | `main` branch protection és kötelező checkek beállítása | Ajánlott | 2/5 | A GitHub API állapotfelvételekor a `main` nem volt védett, required status check nélkül |

## 4. Production Supabase – aktuális ismert állapot

A Supabase read-only eszközök a jelentés készítésekor:
- Projekt: Jarvis, régió `eu-west-1`, státusz `ACTIVE_HEALTHY`, PostgreSQL `17.11.0.019`.
- Remote migration ledger:
  - `20261119191911`
  - `20261119192040`
  - `20261119192145`
  - `20261119192412`
  - `20261119192559`
- A korábbi read-only schema auditban a két `20261117` migráció hatása látszott, miközben a ledger-verziók hiányoztak.
- Az audit/hash-chain, shared-workspace RBAC, task idempotencia és approval/operation migrációk nem tekinthetők productionben alkalmazottnak, amíg a remote ledger és postcondition ezt nem igazolja.

**Tilos a staged sorrend felborítása:**
1. Friss production backup + tényleges restore bizonyíték.
2. Migration drift és legacy adatmegőrzés rendezése.
3. Audit/hash-chain/RBAC/idempotencia/approval migrációk ellenőrzött, jóváhagyott alkalmazása.
4. Új RPC-alapú app deploy és smoke.
5. Csak ezután `20261125170000_enforce_atomic_task_write_privileges.sql`.
6. Auth/RBAC flag és user provisioning külön döntés/engedély alapján.

## 5. Kódlefedettség – mit jelent a 90.75%?

A legutóbbi teljes CI coverage artifactja:
[Coverage artifact – run #45649264268](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45649264268/artifacts/15038164257)

- Mért sorok: **4 109**
- Lefedett sorok: **3 729**
- Nem lefedett sorok: **380**
- Line coverage: **90.75%**
- CI küszöb: **80%**, tehát 10.75 százalékponttal felette.
- Tesztek: **759 passed, 3 skipped**.
- Branch coverage: a jelenlegi konfiguráció nem mérte (0/0); a 90.75% kizárólag sorlefedettség, nem elágazáslefedettség.

Alacsonyabb lefedettségű, a coverage XML-ben azonosított fájlok:
- `scripts/supabase_auth_rls_smoke.py`: **17.3%** (42/243 sor)
- `task_actions.py`: **81.4%** (136/167 sor)
- `proactive_monitor_job.py`: **88.9%** (8/9 sor)
- A `scripts` csomag összesített sorlefedettsége: **57.17%**.

A 90.75% jó általános eredmény, de nem jelenti azt, hogy minden üzleti vagy production útvonal bizonyított. Különösen a live Auth/RLS smoke script alacsony értéke és a task action modul hiányzó sorai célzott tesztelést indokolnak. A coverage artifact a PR #19 javítása előtti, korábbi teljes futásból származik; a PR #19 végleges CI-jéből új coverage értéket kell rögzíteni.

## 6. CI hivatkozások

- [PR #18 – atomikus task approval és auth hardening](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/18)
- [PR #19 – S3 backup ellenőrzés javítása](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/19)
- [PR #19 CI run #45652611537 – sikeres](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45652611537)
- [Dokumentációs frissítés CI run #45653353882](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45653353882)
- [Sikertelen első production backup run #45652336576](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45652336576)
- [Utolsó teljes coverage run #45649264268](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45649264268)

## 7. Döntési összegzés

A fejlesztési kód jelentős része elkészült és izolált tesztekkel bizonyított. A legnagyobb fennmaradó kockázat már nem a unit tesztek száma, hanem a production és repository közötti eltérés biztonságos rendezése, a valódi production backup restore-jának bizonyítása, valamint az app deploy és a jogosultságzárás helyes sorrendje.

A production migráció és deploy nem tekinthető késznek. A következő biztonságos lépés: PR #19 teljes CI-jének megvárása, merge, majd a javított production backup workflow újrafuttatása és a mentés tényleges restore-jának igazolása.
