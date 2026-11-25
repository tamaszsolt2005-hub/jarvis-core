# PR #13 – a Jarvisban még nem élesített frissítések és integrációs hiányok

**Dátum:** 2026-11-25  
**Branch:** `feat/supabase-auth-rbac-foundation`  
**PR:** [#13](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/13) – nyitott, draft, nincs merge  
**Vizsgált kódállapot:** a dokumentációs commit előtti PR-head `96595388cd82bcaa591cef476073d7a7b28a01a0`  
**Production Supabase:** `kiutreccucbegskxowek` – kizárólag read-only állapotfelmérés történt

## 1. A dokumentum célja

Ez a jelentés elkülöníti:
- mi került be a GitHub PR ágába és milyen tesztbizonyítéka van;
- mi nincs még telepítve vagy bekapcsolva a futó Jarvis/production környezetben;
- mely munkák maradtak nyitva.

A PR ágban lévő kód nem azonos az éles Jarvisban aktív funkcióval. A dokumentumban a „branch-only” kifejezés azt jelenti, hogy a módosítás a PR-ban megtalálható, de production telepítése/aktiválása nem igazolt.

## 2. Ellenőrzött, PR ágban meglévő frissítések

### 2.1 Supabase Auth és fail-closed hozzáférés
- Opt-in, szerveroldali `JARVIS_SUPABASE_AUTH_LOGIN_ENABLED` kapcsoló; alapértelmezésben OFF.
- Felhasználói session ellenőrzése/frissítése Streamlit rerunoknál.
- Auth módon verified user JWT-vel történő üzleti adat-hozzáférés; service-role fallback nélkül.
- Admin/operator/reader jogosultságok szerveroldali ellenőrzése.
- A task műveletek közös enforcement kapun keresztül kérik a `tasks.write` jogosultságot, admin/operator szerepkörrel.
- A dashboard/Auth tesztek lefedik a session frissítést, lejárt/visszavont session elutasítását és a legacy kliens használatának tiltását Auth módban.

**Production állapot:** az Auth/RBAC flag OFF; valós production Auth provisioning vagy bekapcsolás nem történt. Valós Auth-issued JWT/PostgREST ellenőrzés még hiányzik.

### 2.2 Jóváhagyási payload védelme
- A pending művelet a beállításkor mély másolatot kap.
- A payload SHA-256 hash-e a jóváhagyáskor rögzül, fogyasztáskor újraellenőrződik.
- A jóváhagyás felhasználói principalhoz, nonce-hoz és ötperces TTL-hez kötött; fogyasztás után a sessionből törlődik.
- A payload-módosítás, hibás hash, hiányzó principal, másik felhasználó és lejárt jóváhagyás regressziós tesztekkel lefedett.

**Korlát:** ez Streamlit session-szintű védelem. Nem jelent adatbázis-szintű, több worker/process között atomikus „consume once” tranzakciót. Általános approval race elleni teljes megoldás még nincs.

### 2.3 Feladat-létrehozás idempotenciája
- A chat által előkészített `create` task művelet stabil UUID `operation_id`-t kap még a jóváhagyás előtt.
- Az azonosító része a hash-sel védett payloadnak, és a jóváhagyás elfogyasztásakor megmarad.
- A task create ezt az azonosítót menti az adatbázisba.
- A `tasks.operation_id` nullable UUID oszlopot és részleges unique indexet kapó migráció: `20261125150000_task_creation_idempotency.sql`.
- Egy azonos `operation_id`-val érkező retry egyediütközés esetén visszakeresi a már létrejött feladatot, és nem hoz létre második rekordot.
- A séma-bootstrap (`supabase/schema.sql`) is tartalmazza az oszlopot és indexet.
- SQL fixture teszt ellenőrzi az oszlopot, indexet, duplikáció elutasítását és a migráció ismételt futtathatóságát.

**Korlát:** ez jelenleg a task create műveletre vonatkozik. Nem ad általános idempotenciát e-mail küldéshez, lead módosításhoz vagy minden jóváhagyott művelethez. Az alkalmazáskód és a DB-migráció csak akkor működik együtt, ha az adott környezetben a migráció biztonságosan telepítve van.

### 2.4 Audit és RBAC adatbázis-alapok
- Strukturált auditmezők, műveletazonosító, státusz és eredmény metaadatok.
- Audit hash-chain és ellenőrző függvény; audit rekordok append-only védelme.
- Shared-workspace admin/operator/reader hozzáférési modell, RLS/policy/grant tesztek.
- JWT role spoofing regressziós teszt: a felhasználó által írható `user_metadata.role` nem írhatja felül a trusted `app_metadata.role` szerepet.

**Korlát:** a PR-ban lévő migrációk nem bizonyítják, hogy a production adatbázisban már alkalmazva vannak. A production read-only snapshot szerint az audit chain táblája és a strukturált audit oszlopok hiányoznak; a későbbi audit/RBAC migrációk nem szerepelnek a production ledgerben.

### 2.5 Migrációs és backup/restore CI
- A két eredetileg azonos `20261117` verziójú legacy migráció egyedi 14 számjegyű verzióra rendezése (`20261117090000`, `20261117100000`); a CI fixture ezek külön ledger-repair, replay és legacy-adat-megőrzési ellenőrzését futtatja. Az új CI-futás eredménye még ellenőrzendő.
- Supabase CLI 3.4.0 migration repair applied/reverted/applied szemantikájának vizsgálata kizárólag lokális fixture-ben.
- Audit/RBAC migrációs replay, failure-injection és forward recovery.
- Catalog postcondition és pgTAP security tesztek.
- Titkosított age backup/restore round-trip külön lokális PostgreSQL adatbázisba.

**Korlát:** ez nem production AWS/S3 backup és nem production restore. A CI repair tesztje nem engedélyezi a production migration ledger javítását.

## 3. Mi nincs még igazoltan benne az éles Jarvisban

| Terület | PR ág állapota | Production / futó Jarvis |
|---|---|---|
| Supabase Auth login | Implementálva, opt-in | OFF; nincs aktiválva |
| User-JWT üzleti DB hozzáférés | Kódban előkészítve | Valós Auth-issued JWT-vel nem validált |
| RBAC/RLS policy-k | Migráció és CI tesztek | Productionre nem alkalmazva |
| Audit hash-chain | Migráció és CI tesztek | Productionben nincs aktiválva |
| Task `operation_id` | Kód + migráció + fixture teszt | Migráció productionre nem alkalmazva |
| Approval payload hash | Session helper + tesztek | Nem cross-process/DB-atomikus |
| Production backup S3/KMS | CI helyi round-trip | Nem bizonyított |
| Külső integrációk | Részleges alkalmazáskód | Gemini/SMTP/IMAP teljes integrációs tesztje hiányzik |

A production read-only állapotfelméréskor a projektben 8 public tábla volt, mindegyiken RLS engedélyezve; policy-k nem voltak, a structured audit mezők és `audit_chain_state` hiányoztak, az Auth user állomány üres volt. Ez a korábbi snapshot időpontjára vonatkozó adat, nem folyamatos monitorozás.

## 4. Nyitott feladatok és release gate-ek

### P0 – Production előfeltételek
1. **Migration drift:** a két legacy migráció egyedi verzióra rendezése elkészült a PR ágban; a CI bizonyítása, majd a két production ledger-bejegyzés külön jóváhagyással történő history-only repairje és a négy későbbi migráció biztonságos rendezése még hátravan.
2. **Valós production backup/restore:** AWS OIDC, S3, KMS és GitHub konfiguráció ellenőrzése; titkosított mentés; külön adatbázisba visszaállítás és hash/rekordszám jegyzőkönyv.
3. **Valós Auth/JWT/RLS:** kizárólag már létező, kifejezetten engedélyezett izolált Supabase környezetben. Új projektet, accountot vagy branch-et nem szabad létrehozni.

### P1/P2 – Alkalmazás és üzemeltetés
- Az összes DB-hívás principal/service-role besorolásának lezárása.
- Több worker/process közötti atomikus approval consumption és általános replay/idempotencia.
- E-mail küldéshez delivery idempotency és SMTP/IMAP hibakezelés.
- Gemini és ütemezett workflow-k kontrollált integrációs tesztjei.
- RPO/RTO, retention, riasztás, restore-gyakorlat, incidenskezelés és kulcsrotációs runbook.

## 5. Ellenőrzési állapot és biztonsági korlátok

- A `df8bf69` commit CI futása: [JARVIS CI #1758](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45595952734). A dokumentum elkészítésekor a Python/AppTest/browser job még futott; a PostgreSQL 17 migration/RBAC/catalog és backup/restore job sikeresen befejeződött. A teljes futás ekkor még nem volt zöldnek nyilvánítható.
- A CI közben a pending approval payload másolatát ellenőrző tesztben hibás fixture-t találtunk; a teszt fixture javítása a `9659538` commitban történt. Ennek a commitnak külön CI-ellenőrzése szükséges.
- A teljes tesztfutás sikerét addig nem állítjuk, amíg az új head CI-je nem zárult sikeresen.

**Szigorú korlátok:**
- Production Supabase-en nem történt DDL/DML, migration repair, ledger edit, policy-módosítás vagy Auth-user provisioning.
- Production Auth/RBAC flag OFF marad.
- Nem jött létre új Supabase account, projekt vagy branch.
- A migrációk és repair-szemantika tesztelése kizárólag izolált GitHub Actions PostgreSQL 17 fixture-ben történt.
- PR #13 draft és unmerged; automatikus merge nem történt.

## 6. Következtetés

A PR jelentős Auth/RBAC, audit, jóváhagyás-védelem és task-create idempotencia fejlesztéseket tartalmaz, de ezek nem azonosak az éles Jarvisban már telepített és bekapcsolt funkciókkal. A task idempotencia migráció és a többi adatbázis-módosítás productionre történő alkalmazása külön jóváhagyást, drift-rendezést és ellenőrzött mentést igényel. A következő mérföldkő az aktuális PR-head teljes CI-jének lezárása, majd a P0 release gate-ek külön-külön történő bizonyítása.


## Aktuális ellenőrzés – 2026-11-25 (a korábbi CI-státuszt felülírja)

A legfrissebb ellenőrzött PR-head `09bde885407643146238ecc77811eded1ad8aef8`.
A [JARVIS CI #45619101972](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45619101972)
mindkét jobja sikeres: a `test` és a `backup-restore-integration` is zöld; a commiton 4/4 GitHub check sikeres.
A PostgreSQL 17 job a teljes migrációs/pgTAP/catalog ellenőrzést és az izolált CI backup/restore körutat futtatta. Ez nem production archive restore és nem valós Supabase Auth/JWT/RLS bizonyíték.

GitHub jelenlegi állapota: `mergeable=true`, `mergeable_state=clean`, 0 commit behind `main`. A PR továbbra is draft, unmerged. A PR merge és a production release külön döntés; production Auth/RBAC flag maradjon OFF.

A még nyitott, kifejezetten dokumentált fejlesztési hiányok:
- több worker/process közötti adatbázis-atomikus approval consumption;
- nem-create műveletek általános replay/idempotencia védelme és e-mail delivery idempotencia;
- Gemini/SMTP/IMAP valós integrációs tesztek;
- production backup külön adatbázisba restore-ja, migration history rendezése és valós Auth/JWT/RLS validáció – ezek production release gate-ek, nem bizonyított CI-eredmények.
