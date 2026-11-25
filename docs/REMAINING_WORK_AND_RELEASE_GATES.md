# JARVIS – fennmaradó feladatok és élesítési kapuk

**Frissítve:** 2026-11-25  
**Vizsgált branch:** `feat/supabase-auth-rbac-foundation`  
**Igazolt commit:** `e6736101405180c220d6b96b5a7a3c1d890813e0`  
**PR:** [#13 – open, draft](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/13)  
**Hatókör:** fejlesztési backlog és release gate; ez a dokumentum nem production change approval.

A dokumentum a repositoryban implementált, CI-ben ellenőrzött, izolált integrációs környezetben igazolt és productionben bizonyított állapotokat külön kezeli. Egy zöld CI nem jelent production-ready Auth/RBAC-ot.

## 1. Aktuális, bizonyítékkal alátámasztott állapot

### PR és CI

- PR #13 nyitott és draft; nincs merge.
- A branch head `e6736101405180c220d6b96b5a7a3c1d890813e0`.
- A [45571463053 CI-futás](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45571463053) ezen a headen teljesen sikeres.
- Python / Streamlit / AppTest / browser tesztek: **762 passed, 3 skipped**.
- Python line coverage: **96.47%** (3,799 statement; 134 missed).
- CloudFormation validáció, Playwright böngészőtelepítés és `compileall`: sikeres.
- PostgreSQL 17 integrációs job: sikeres; audit/RBAC migrációk és pgTAP ellenőrzések lefutottak.
- Age titkosítású backup/restore round-trip: sikeres, izolált CI PostgreSQL környezetben.
- Coverage artifact: [15002127458](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45571463053/artifacts/15002127458).
- A [45571470452 futás](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45571470452) ugyanezen a commiton szintén teljesen sikeres: 762 passed, 3 skipped, 96.47% coverage; mindkét job zöld.

**A 45571463053 eredménye a 20 korábbi teszthiba javítását igazolja.** Nem bizonyítja a production AWS/S3 mentést, production restore-t, valós Supabase Auth/JWT/RLS viselkedést vagy éles e-mail-kézbesítést.

### Kód- és tesztjavítások a jelenlegi headen

- A dashboard kompatibilitási `audit_event` és `report_error` delegate-jei megőrzik a központi modulimplementációt és a monkeypatchelhető tesztfelületet.
- Az audit UI AppTest fixture a hitelesített admin kliens izolált stubját a rerun előtt telepíti; a login tesztek címke alapján választják a submit gombot.
- A célzott regressziós tesztfutás 762 passed / 3 skipped eredményt adott.
- A változtatások nem kapcsolják be a production Auth flaget és nem módosítják a production adatbázist.

## 2. P0 – kötelező blokkolók bármilyen production Auth/RBAC előtt

### P0.1 – Supabase migrációs drift és schema reconciliation

**Felelős terület:** adatbázis / platform  
**Állapot:** részben előkészített, productionben nem lezárt.

Feladatok:
- [ ] Aktuális, read-only schema-only snapshot készítése és archiválása.
- [ ] A remote migration ledger és a repo migrációk verziónkénti összevetése, különösen a két `20261117` repo-only verzióé.
- [ ] A live `settings`, `posts`, `logs` legacy struktúrák és constraint/index/default eltéréseinek dokumentálása.
- [ ] A migrációk pontos, determinisztikus sorrendjének és minden precondition/postcondition SQL-jének rögzítése.
- [ ] Forward-recovery és rollback/kompenzációs terv készítése; destruktív vagy nem visszafordítható lépések külön jelölése.
- [ ] Clean bootstrap és production-shape PostgreSQL 17 teszt, negatív precondition tesztekkel.
- [ ] Független review az SQL-csomagon és az alkalmazási sorrenden.

**Elfogadási kritérium:** minden remote/repo verzióeltérés magyarázott; a teljes migrációs lánc tiszta és production-shape izolált adatbázison reprodukálható; minden pre/postcondition zöld; a recovery tervet szárazpróbán ellenőrizték.

**Tiltás:** production `supabase db push`, `migration repair`, DDL/DML, ledger-módosítás vagy migrációs futtatás nem végezhető külön, pontos felhasználói jóváhagyás nélkül.

### P0.2 – Production backup és restore bizonyítása

**Felelős terület:** infrastruktúra / üzemeltetés  
**Állapot:** a CI lokális round-trip zöld; production backup nincs igazolva.

Feladatok:
- [ ] AWS backup stack telepítése és CloudFormation outputok ellenőrzése.
- [ ] GitHub Actions secrets/variables meglétének és jogosultságainak ellenőrzése: DB URL, AWS role ARN, age identity/recipient, bucket, KMS key, régió.
- [ ] Production dump titkosított feltöltése S3-ba.
- [ ] Feltöltött objektum letöltése, visszafejtése, manifest- és hash-ellenőrzése.
- [ ] Restore külön izolált PostgreSQL adatbázisba.
- [ ] Restore utáni integritás-, sémaszám-, rekordszám- és alkalmazási smoke teszt dokumentálása.
- [ ] Rendszeres backup ütemezés, retention, riasztás és hozzáférési kontroll ellenőrzése.

**Elfogadási kritérium:** van dátummal, forrásazonosítóval, objektumazonosítóval, hash-sel és restore jegyzőkönyvvel igazolt, titkosított production mentés; a visszaállítás sikeres külön adatbázisba; a titkok nem kerülnek logba vagy Gitbe.

### P0.3 – Valós Supabase Auth/JWT/RLS validáció

**Felelős terület:** alkalmazásbiztonság / Supabase  
**Állapot:** repository tesztek zöldek; valós Auth/RLS validáció nincs igazolva.

Feladatok:
- [ ] Csak már létező, külön engedélyezett izolált Supabase környezet használata; production nem lehet tesztkörnyezet.
- [ ] Admin/operator/reader provisioning és trusted `app_metadata.role` kiosztás ellenőrzése.
- [ ] Pozitív és negatív SELECT/INSERT/UPDATE/DELETE/RPC/view teszt minden érintett táblára.
- [ ] JWT refresh, lejárat, revoke, logout, role demotion és user-váltás teszt.
- [ ] Több user és session közötti adatszivárgás/izoláció negatív teszt.
- [ ] Audit append fail-closed útvonal bizonyítása user-JWT mellett.
- [ ] Admin bootstrap és elveszett admin hozzáférés visszaállítási eljárás próbája.

**Elfogadási kritérium:** minden szerepkör minden táblaműveletére dokumentált allow/deny mátrix; a valós Supabase tesztkörnyezetben a negatív tesztek is sikeresek; nincs service-role fallback felhasználói útvonalon; audit append hibája esetén a védett művelet nem fut tovább.

**Production Auth flag: OFF marad.** Bekapcsolás csak külön jóváhagyott change terv és az összes P0 kapu teljesülése után lehetséges.

## 3. P1 – alkalmazás és üzleti folyamatok

### P1.1 – Dashboard Auth átállás

- [ ] Minden chat-, analitika-, admin- és exportadatútvonal explicit user-JWT vagy szűk szerveroldali job besorolást kap.
- [ ] Service-role kliens kizárólag szerveroldali, minimális jogosultságú háttérműveletben használható.
- [ ] A `get_supabase()` kompatibilitási alias hívóinak leltározása és fokozatos kivezetése.
- [ ] Login, logout, session refresh/expiry, role demotion, admin bootstrap end-to-end tesztje.

**Elfogadási kritérium:** minden DB-hívó dokumentált principal- és jogosultsági kontextussal rendelkezik; Auth módban hiányzó/lejárt session esetén nincs legacy/service-role fallback; regressziós teszt védi ezt.

### P1.2 – Jóváhagyás és üzleti mellékhatások

- [ ] `task_actions` audit + user-JWT/RLS útvonal valós integrációs tesztje.
- [ ] Jóváhagyás egyszer használható, lejáró, userhez és művelet-payload hashhez kötött legyen.
- [ ] Párhuzamos kérés, replay, race condition és hálózati hiba tesztje.
- [ ] E-mail küldés role-, approval- és szerveroldali feature flag védelme.
- [ ] Leadkutatás, célpiacmódosítás és minden módosító workflow jogosultságtesztje.
- [ ] Sikertelen auditírás esetén a külső mellékhatás blokkolása.

**Elfogadási kritérium:** minden mellékhatás előtt szerveroldali jogosultság és audit; egy jóváhagyás legfeljebb egyszer fogyasztható; párhuzamos/replay próbák nem eredményeznek dupla műveletet.

### P1.3 – Külső integrációk

- [ ] Gemini timeout/retry/quota/hibaválasz és titok-redakciós teszt.
- [ ] SMTP/IMAP tesztfiókkal küldés/fogadás, retry/idempotencia és hibakezelés.
- [ ] Ütemezett workflow-k deduplikációja, lockolása és auditálása.
- [ ] E-mail kézbesítési eredmény bizonyítása tesztcímzettel; éles címzett csak külön engedéllyel.

**Elfogadási kritérium:** minden külső hívás timeouttal, korlátozott retry-val, redaktált loggal és megfigyelhető audit eseménnyel működik; kézbesítés csak kontrollált tesztből állítható.

## 4. P2 – üzemeltetés és hosszú távú biztonság

- [ ] Restore-gyakorlat és RPO/RTO célok meghatározása.
- [ ] Backup retention, riasztások, least-privilege AWS role és artifact hozzáférés.
- [ ] Incidenskezelési, kulcsrotációs és helyreállítási runbook.
- [ ] Több-tenant adatmodell és tenant-szintű RLS – csak több ügyfél kiszolgálása előtt.
- [ ] Audit hash-chain külső hash-ankorral/WORM tárolással, retention és legal hold.
- [ ] Független riasztás auditlánc-megszakadásra és jogosultsági anomáliákra.
- [ ] Függőségek és GitHub Actions verziók rendszeres frissítése, SBOM és sebezhetőség-ellenőrzés.

## 5. Tesztelési és release kapuk

- [x] Aktuális head teljes Python/AppTest/browser CI: 762 passed, 3 skipped.
- [x] Aktuális head line coverage: 96.47%, 80% küszöb felett.
- [x] PostgreSQL 17 + pgTAP integráció és lokális age backup/restore round-trip.
- [ ] Valós Supabase Auth/JWT/RLS integráció engedélyezett izolált környezetben.
- [ ] Production encrypted backup + külön DB restore bizonyítéka.
- [ ] Production migrációs drift feloldása és független SQL review.
- [ ] E-mail és task approval race/replay/failure integrációs tesztek.
- [ ] Üzemeltetési runbook és restore-gyakorlat.

## 6. Production állapot – legutóbbi ismert read-only bizonyíték

A 2026-11-24 18:51 UTC read-only revalidation dokumentált eredménye:
- 8 public tábla; mindegyiken RLS engedélyezve.
- 0 alkalmazott RLS policy.
- 0 Supabase Auth-felhasználó.
- Hiányzó `audit_chain_state`.
- A `logs` táblában 12 ellenőrzött strukturált auditmezőből 0 található.

Ez történeti read-only bizonyíték, nem friss lekérdezés. A következő production ellenőrzés kizárólag read-only lehet, és nem járhat migrációval vagy Auth flag változtatással.

## 7. Kötelező végrehajtási sorrend

1. PR #13 kódreview, CI és dokumentáció konzisztencia.
2. Read-only schema snapshot és migration drift reconciliation.
3. Izolált PostgreSQL 17 migrációs dry-run + recovery próba.
4. AWS production backup és külön adatbázisba restore bizonyítása.
5. Valós Auth/JWT/RLS teszt meglévő, engedélyezett izolált környezetben.
6. P1 üzleti műveletek és külső integrációk validációja.
7. Pontos production change terv, rollback/forward recovery, karbantartási ablak és ellenőrző SQL.
8. Minden éles SQL/migráció/flag módosítás előtt külön, kifejezett jóváhagyás.
9. Read-only post-deploy ellenőrzés, monitorozás és dokumentációfrissítés.

## 8. Kapcsolódó dokumentumok

- [Teljes műszaki dokumentáció](JARVIS_DOCUMENTATION.md)
- [Auth/RBAC production reconciliation](AUTH_RBAC_PRODUCTION_RECONCILIATION.md)
- [Supabase klienshozzáférési leltár](SUPABASE_CLIENT_ACCESS_INVENTORY.md)
- [Production migration recovery](production-migration-recovery.md)
- [Production read-only revalidation](PRODUCTION_REVALIDATION_2026-11-24_1851UTC.md)
- [PR #13 CI validation](PR13_CI_VALIDATION_2026-11-24.md)
- [PR #13](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/13)

**Biztonsági állapot:** production Supabase nem módosult; production Auth flag OFF; PR #13 nem merge-ölhető automatikusan.


## P0 Supabase / backup / real Auth-RLS execution update (2026-11-25)

The latest read-only evidence and implementation artifacts are now recorded:

- [Production schema snapshot](PRODUCTION_SCHEMA_SNAPSHOT_2026-11-25.md): complete public table/column/index/constraint/RLS/grant/default-ACL inventory, exact five-version remote ledger, and absent audit schema.
- [Migration drift reconciliation](SUPABASE_MIGRATION_DRIFT_RECONCILIATION.md): two 20261117 effects already present but not ledgered; three later audit/RBAC migrations remain unapplied.
- [Production recovery plan](production-migration-recovery.md): ordered branch-first validation and forward-only recovery sequence.

### P0.1 – Migration drift

<badge>Evidence captured; production repair blocked</badge>

- [x] Fresh read-only schema snapshot.
- [x] Exact remote ledger list.
- [x] Supabase Security Advisor: 8 RLS-enabled/no-policy findings.
- [ ] Create disposable Supabase branch and replay migrations in order.
- [ ] Validate two 20261117 baseline/ledger reconciliation behavior on the branch.
- [ ] Verify audit expansion → hash-chain → RBAC postconditions and failure recovery.
- [ ] Prepare exact production ledger repair/forward migration plan; production operation requires separate approval.

### P0.2 – Production backup and separate restore

- [x] Existing encrypted public-schema backup code reviewed.
- [x] Workflow extended to verify S3 SSE-KMS metadata, download/decrypt/hash-check the object, then restore into a separate disposable PostgreSQL 17 container.
- [ ] Configure/verify the required GitHub secrets and variables.
- [ ] Deploy/verify the AWS CloudFormation stack and main-branch GitHub OIDC trust.
- [ ] Run the production backup workflow from trusted `main`.
- [ ] Capture S3 object key/version, KMS metadata, manifest hashes, restored table inventory, and row-count evidence.

The backup archive covers JARVIS `public` schema only; Supabase-managed schemas and Storage object binaries are excluded. This limitation is explicit in the recovery plan.

### P0.3 – Real Supabase Auth/JWT/RLS

- [x] Live test harness creates temporary Auth users with server-managed `app_metadata.role`.
- [x] Harness exercises real Auth-issued JWTs through PostgREST, including admin/operator/reader permissions, user_metadata spoof rejection, audit append/read separation, role refresh and logout.
- [x] Manual GitHub workflow uses a dedicated `supabase-integration` environment and test-only credentials.
- [ ] Create/approve disposable Supabase branch (quoted compute cost: **$0.01344/hour**).
- [ ] Add branch-only URL, publishable key, service-role key and project ref to the protected GitHub environment.
- [ ] Execute live Auth/RLS workflow and archive evidence.
- [ ] Delete the disposable branch after evidence is captured.

**Production safety:** production schema, migration ledger, Auth users and policies remain unchanged. Production Auth flag stays OFF. No production migration or Auth provisioning is authorized by this documentation update.

## Supabase test-environment constraint (2026-11-25)

The user explicitly requires use of the existing Jarvis Supabase project only and prohibits
creating a new Supabase test account or development branch. The connected account currently
exposes only project `kiutreccucbegskxowek`; its branch list is empty.

This supersedes the earlier branch-creation steps in this roadmap. Migration replay,
failure-injection and recovery validation must run in the existing GitHub Actions isolated
PostgreSQL 17 production-shape fixture. Do not create a Supabase project/branch and do not
run production migrations or migration repair. The existing Jarvis project is read-only
for this phase. The 20261117 ledger discrepancy remains open until local fixture tests
prove the exact CLI-compatible reconciliation operation. Production Auth stays OFF.
