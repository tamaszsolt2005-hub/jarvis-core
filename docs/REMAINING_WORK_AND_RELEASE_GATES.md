# JARVIS – fennmaradó feladatok és élesítési kapuk

**Frissítve:** 2026-11-25  
**Vizsgált branch:** `feat/supabase-auth-rbac-foundation`  
**Korábbi CI-baseline commit:** `e6736101405180c220d6b96b5a7a3c1d890813e0` (nem a legfrissebb head).  
**PR:** [#13 – open, draft](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/13)  
**Hatókör:** fejlesztési backlog és release gate; ez a dokumentum nem production change approval.

A dokumentum a repositoryban implementált, CI-ben ellenőrzött, izolált integrációs környezetben igazolt és productionben bizonyított állapotokat külön kezeli. Egy zöld CI nem jelent production-ready Auth/RBAC-ot.

## 1. Korábbi CI-baseline és aktuális release-gate állapot

### PR és CI

- PR #13 nyitott és draft; nincs merge.
- A `e6736101405180c220d6b96b5a7a3c1d890813e0` egy korábbi, teljesen tesztelt baseline; nem a jelenlegi PR head. A friss branch head és CI a [PR #13 oldalán](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/13) követhető.
- A [45571463053 CI-futás](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45571463053) ezen a headen teljesen sikeres.
- Python / Streamlit / AppTest / browser tesztek: **762 passed, 3 skipped**.
- Python line coverage: **96.47%** (3,799 statement; 134 missed).
- CloudFormation validáció, Playwright böngészőtelepítés és `compileall`: sikeres.
- PostgreSQL 17 integrációs job: sikeres; audit/RBAC migrációk és pgTAP ellenőrzések lefutottak.
- Age titkosítású backup/restore round-trip: sikeres, izolált CI PostgreSQL környezetben.
- Coverage artifact: [15002127458](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45571463053/artifacts/15002127458).
- A [45571470452 futás](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45571470452) ugyanezen a commiton szintén teljesen sikeres: 762 passed, 3 skipped, 96.47% coverage; mindkét job zöld.

**A 45571463053 eredménye a 20 korábbi teszthiba javítását igazolja.** Nem bizonyítja a production AWS/S3 mentést, production restore-t, valós Supabase Auth/JWT/RLS viselkedést vagy éles e-mail-kézbesítést.

### Kód- és tesztjavítások az e673 korábbi CI-baseline-ban

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
**Állapot:** a production age-titkosított logikai dump S3-feltöltése, SSE-KMS metaadat-ellenőrzése, letöltése, visszafejtése és manifest-hash ellenőrzése sikeres (`45611038142`). Az izolált PostgreSQL 17 CI backup/restore round-trip is zöld (`45617334463`). A production backup külön adatbázisba történő tényleges visszaállítása és a restore-jegyzőkönyv még nyitott.

Feladatok:
- [ ] AWS backup stack telepítése és CloudFormation outputok ellenőrzése.
- [ ] GitHub Actions secrets/variables meglétének és jogosultságainak ellenőrzése: DB URL, AWS role ARN, age identity/recipient, bucket, KMS key, régió.
- [x] Production dump titkosított feltöltése S3-ba (`45611038142`, SSE-KMS).
- [x] Feltöltött objektum letöltése, visszafejtése, manifest- és hash-ellenőrzése (`45611038142`).
- [ ] Ugyanezen production archívum restore-ja külön izolált PostgreSQL adatbázisba (a CI lokális fixture restore-ja nem helyettesíti ezt).
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

- [x] Korábbi e673 CI-baseline teljes Python/AppTest/browser CI: 762 passed, 3 skipped (nem a jelenlegi PR head).
- [x] Aktuális head line coverage: 96.47%, 80% küszöb felett.
- [x] PostgreSQL 17 + pgTAP integráció és lokális age backup/restore round-trip.
- [ ] Valós Supabase Auth/JWT/RLS integráció engedélyezett izolált környezetben.
- [x] Production encrypted backup S3 upload + decrypt/hash verification.
- [x] Isolated PostgreSQL 17 CI restore round-trip.
- [ ] A production archívum külön adatbázisba történő restore-ja és dokumentált post-restore ellenőrzése.
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
- [x] Supabase branch létrehozása elvetve: a felhasználói korlátozás szerint új Supabase branch nem hozható létre; a migrációs replay a meglévő GitHub Actions PostgreSQL 17 fixture-ben történik.
- [ ] A két 20261117 ledger-eltérés pontos, CLI-kompatibilis rendezésének bizonyítása lokális fixture-ben; a replay/adatmegőrzés teszt már kész, de a remote ledger javítása nem igazolt.
- [x] Audit expansion → hash-chain → RBAC migrációs sorrend és fájlok közötti forward-recovery CI-ben tesztelve; a részleges audit DDL-prefix utáni replay is lefedett. [ ] Teljes owner/grant/policy/function ACL/trigger postcondition review még szükséges.
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
- [x] Új Supabase branch létrehozása kifejezetten tiltott; nincs meglévő fejlesztői branch. Live Supabase teszt csak már létező, külön engedélyezett izolált környezetben végezhető.
- [ ] Ha rendelkezésre áll már létező, engedélyezett izolált Supabase környezet: annak URL/anon-publishable key/service-role key/project ref értékeinek beállítása a védett GitHub environmentben.
- [ ] Execute live Auth/RLS workflow and archive evidence.
- [x] Nincs törlendő Supabase branch; új branch nem jött létre.

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

### Migration drift progress update — 2026-11-25

Added local-only regression coverage:
- `supabase/tests/migration_drift_recovery.test.sql` seeds the five observed remote
  migration versions and represents both existing 20261117 schema effects.
- CI now creates a dedicated PostgreSQL 17 fixture, replays both 20261117 additive
  migrations twice, and checks preservation of lead/log/settings/posts rows and the
  integer sequence-backed settings ID.

Commit: `d995fe5e577e7bdc455aec67083c6fd894f982c4`.

Status: implementation committed; CI result pending at documentation time. This test
does not repair or modify the remote ledger. The exact CLI-compatible resolution of
the two missing versions and failure-injection recovery for later audit/RBAC migrations
remain open. Production stays read-only and Auth stays OFF.

---

## 2026-11-25 – állapotfrissítés a tényleges branch-head alapján

**Ez a szakasz felülírja a dokumentum korábbi, elavult branch-head/CI adatait és minden Supabase branch-létrehozást javasló lépést.** A státuszok a d76e8e859bca9021a4d5d491e49e04591dc5a26f branch-head ellenőrzésekor érvényesek.

### Elkészült és repository/CI-ben lefedett tételek

- [x] Az öt remote migration-ledger SQL-forrás visszanyerése és verziózott fájlként tárolása.
- [x] Production schema snapshot és az öt remote ledger-verzió read-only rögzítése.
- [x] A két 20261117 migráció már meglévő hatásának és legacy adatoknak a külön PostgreSQL 17 fixture-ben történő modellezése.
- [x] A két additive 20261117 migráció ismételt replay-je, valamint a lead/log/settings/posts rekordok és az integer, sequence-backed settings ID megőrzésének ellenőrzése.
- [x] Audit mező migráció utáni megszakítás és forward replay ellenőrzése; részlegesen előkészített audit DDL-prefix utáni teljes migráció replay-je.
- [x] Hash-chain migráció utáni megszakítás és forward replay ellenőrzése; RBAC migráció ismételt replay-je.
- [x] Audit és shared-workspace RBAC pgTAP tesztek a PostgreSQL 17 CI fixture-ben.
- [x] JWT trust-boundary regresszió: a user_metadata.role=admin nem írhatja felül az app_metadata.role=reader értéket; ismeretlen app_metadata role esetén a hozzáférés megtagadott. A shared-workspace tesztterv 32 assertiont tartalmaz.
- [x] A CI elvárása frissítve a 32 pgTAP assertionre.
- [x] A production-shape migrációs és backup/restore CI infrastruktúra a repository workflow-ban létezik.
- [x] Valós Supabase Auth-issued JWT/PostgREST smoke tesztharness és manuális workflow elkészült; a futtatáshoz szükséges védett környezeti titkok/értékek és futási bizonyíték még hiányzik.
- [x] Az Auth/RBAC implementáció, migrációk, tesztek és dokumentáció a PR #13 branch-en vannak; a production Auth flag továbbra is OFF.

### Legfrissebb CI állapot – ne keverd össze a korábbi zöld futásokkal

A d76e8e859bca9021a4d5d491e49e04591dc5a26f headhez tartozó legutóbbi futások az ellenőrzés pillanatában még futottak:

- Push: https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45589657934 – in_progress.
- PR: https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45589669569 – in_progress.
- A korábbi 45571463053 és 45571470452 futások a 762 passed / 3 skipped / 96.47% coverage baseline-t igazolták. A négy közös fájl main/PR összevezetése után új PR CI futás szükséges; a korábbi baseline nem a jelenlegi head bizonyítéka.
- A korábbi, 762 passed / 3 skipped / 96.47% coverage eredmény korábbi headhez tartozik; nem tekinthető a mostani JWT role tesztmódosítás CI-bizonyítékának.

### Még szükséges – nyitott kapuk

| Terület | Státusz | Mi hiányzik a lezáráshoz |
|---|---|---|
| Aktuális CI | **Fut** | A fenti push és PR futás mindkét jobja zöld legyen; rögzíteni kell az új tesztszámot és coverage-et. |
| Supabase CLI migration repair szemantika | **Nincs igazolva** | A CI workflow jelenleg nem telepít és nem futtat Supabase CLI-t; ezért a pontos migration repair viselkedés továbbra is unverified. Csak izolált, lokális környezetben vizsgálható; production parancs nem futtatható. |
| Két 20261117 ledger-eltérés | **Nyitott** | Az ismételt SQL replay és adatmegőrzés bizonyított a lokális fixture-ben, de ez nem javítja és nem bizonyítja a remote ledger biztonságos módosítását. Pontos, CLI-kompatibilis reconciliation eljárás és független review kell. |
| Migrációs katalógus-postconditionök | **Részben kész** | A CI-ben további explicit ellenőrzés szükséges a productionnel egyező owner/grant/policy/function ACL/trigger/index állapotra; az összes objektumra kiterjedő egyezés nincs teljes körűen bizonyítva. |
| Production backup + restore | **Részben igazolt** | A production age-titkosított dump S3-feltöltése, SSE-KMS ellenőrzése, letöltése, visszafejtése és manifest hash-ellenőrzése sikeres (`45611038142`); az izolált PostgreSQL 17 CI restore-round-trip sikeres (`45617334463`). A production archívum külön adatbázisba való restore-ja, a teljes post-restore jegyzőkönyv, AWS stack státusz és retention/riasztás továbbra is nyitott. |
| Valós Supabase Auth/JWT/RLS | **Harness kész, futtatás nyitott** | A már létező Jarvis projekten kívüli tesztprojekt/branch nem hozható létre; a meglévő Jarvis production projekt csak read-only. Ha nincs már engedélyezett izolált Supabase környezet, a valós live teszt blokkolt marad. A live workflowhoz szükséges secret/variable beállítás és futtatás nincs igazolva. |
| Üzleti mellékhatások és külső integrációk | **Nyitott** | Approval race/replay/failure tesztek, SMTP/IMAP/Gemini kontrollált integrációs tesztek és audit fail-closed bizonyíték. |
| Operáció | **Nyitott** | Production restore-gyakorlat, RPO/RTO, retention/riasztás, incidens- és kulcsrotációs runbook. |
| Release | **Blokkolt** | Független kód/SQL review, minden P0 kapu, pontos change terv és külön felhasználói jóváhagyás. PR #13 draft marad; automatikus merge nincs. |

### Környezeti és production korlátozások

- Kizárólag a meglévő Jarvis Supabase projekt használható; új account, project vagy branch létrehozása tilos. A projekt branch listája üres.
- A production Supabase projekt read-only marad. Nincs db push, migration repair, ledger edit, DDL/DML, policy-változtatás vagy Auth-user provisioning.
- Production Auth/RBAC feature flag OFF marad.
- A GitHub Actions PostgreSQL 17 fixture a migrációs replay/failure-recovery bizonyíték egyetlen engedélyezett helye ebben a fázisban.
- Bármely production adatbázis-módosításhoz külön, konkrét műveletre és SQL/migrációs készletre szóló jóváhagyás szükséges.

## 2026-11-25 – első három release-gate AI/CI munkája

A következő, kizárólag repository/CI scope-ú változtatások kerültek a PR #13 branch-re:

1. **Aktuális CI ellenőrzés:** a `118c27a15cd65aa0f8aea1cb3de5701f5e68c4fa` head PR CI futása
   sikeres volt (`45590107707`). Az új regression step-eket tartalmazó frissebb head
   CI eredményét külön kell megvárni; a régi zöld futás nem bizonyítja az új teszteket.
2. **Katalógus-postcondition review:** új
   `supabase/tests/catalog_postconditions.test.sql` teszt került be. Ellenőrzi a
   táblatulajdonosokat, RLS-t, 15 policy-t, a trusted `app_metadata` boundary-t, a
   táblajogosultságokat, sequence grantet, audit function owner/ACL/SECURITY DEFINER
   határt, három trigger állapotát, négy audit indexet és a `postgres` default ACL-eket.
   A CI a teljes audit/RBAC migrációs replay után futtatja.
3. **Supabase CLI repair szemantika:** a CI rögzített Supabase CLI `3.4.0` verziót
   telepít, és a valódi `migration repair` parancsot kizárólag az izolált PostgreSQL 17
   fixture URL-jére futtatja. Ellenőrzi az `applied` beszúrást, a `reverted` törlést,
   majd az újraalkalmazást, valamint azt, hogy a repair nem változtatja meg a sémát vagy
   a legacy rekordokat. A két 20261117 fájl azonos 8 jegyű verziót használ; a CI külön
   rögzíti a `migration list` kimenetét is, hogy a verzióütközés tényleges CLI-viselkedése
   ne feltételezésből legyen megítélve.

**CI státusz:** az új workflow-ellenőrzések implementálva, de csak a friss PR-headhez
futó teljes CI siker után jelölhetők bizonyítottnak. Addig a CLI-repair és katalóguskapu
`pending` marad. A production Supabase továbbra is kizárólag read-only; nem történt
`db push`, migration repair, ledger edit, DDL/DML, policy/Auth módosítás vagy flag
aktiválás. PR #13 draft marad, merge nem történt.


### CI failure analysis and correction — 2026-11-25

The first run containing the CLI/catalog steps (`45591909723`) exposed a test-harness
assertion issue, not a production or migration failure. Supabase CLI 3.4.0 successfully
executed `migration repair 20261117 --status applied` against the localhost-only PostgreSQL
fixture. The following `psql -t` boolean assertion was too strict: aligned tuple output
contains leading whitespace, so `grep -qx t` returned non-zero. The assertion now adds
`--no-align` to make the expected scalar output deterministic.

The separate Python/unit/AppTest/browser job completed its test step successfully in
`45591909723`; artifact upload was still running at the time of inspection. The database
job stopped before the structured audit pgTAP, catalog postconditions and backup/restore
steps, so those results remain unverified. A new CI run for the assertion fix is required
before closing any of the first three gates.
