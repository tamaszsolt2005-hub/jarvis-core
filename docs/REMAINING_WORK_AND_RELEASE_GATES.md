# JARVIS – fennmaradó feladatok és élesítési kapuk

**Frissítve:** 2026-11-24  
**Hatókör:** `feat/supabase-auth-rbac-foundation` / PR #13  
**Állapot:** fejlesztési és dokumentációs nyilvántartás; nem production change approval.

Ez a dokumentum a kódban már előkészített funkciókat, a CI-ben bizonyított
viselkedést és a productionben még nem igazolt képességeket külön kezeli.
A CI zöld állapota önmagában nem jelent production-ready Auth/RBAC-ot.

## 1. Legutóbbi igazolt fejlesztési állapot

- PR #13 továbbra is nyitott és draft.
- A legutóbbi teljesen zöld CI-t tartalmazó PR head: `4945816b9010d899c1737a90ff3785ec1898acdd`.
- A legutóbbi teljes CI run [45463032568](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45463032568) mindkét jobja sikeres: **718 passed, 3 skipped, 93.78% coverage** (3,500/3,732 sor); `dashboard.py` 82.27%, `jarvis_auth.py` 96.55%, `audit_admin.py` 96.19%.
- A PostgreSQL 17 audit/RBAC + pgTAP + titkosított age backup/restore integráció, CloudFormation-validáció, Playwright, compileall és a Python/AppTest/browser tesztek egyaránt sikeresek.
- Coverage és 27 reszponzív dashboard screenshot artifact feltöltve. Ez CI-bizonyíték, nem production backup vagy valós Supabase Auth-teszt.
- A dashboard Auth helper tesztcsomag a session frissítést, hiányzó/visszavont session fail-closed kezelését, régi kliens kizárását Auth módban és a sessionből történő takarítást ellenőrzi.
- A PostgreSQL CI job lokális, izolált PostgreSQL környezetet használ. Ez nem production backup, nem Supabase Auth szolgáltatás és nem AWS/S3 restore-próba.

## 2. Kritikus blokkolók – production bevezetés előtt

### P0 – migrációs előzmények és schema reconciliation

- [ ] Az öt remote migration ledgerben szereplő, Gitből hiányzó történeti SQL eredeti példányának visszakeresése.
- [ ] Ha nem állítható helyre: teljes, aktuális schema-only snapshot és külön forward-only reconciliation terv; a történeti verziókat nem szabad kitalált SQL-lel pótolni.
- [ ] A két `20261117` repo migráció ledgereltérésének bizonyítékalapú rendezése.
- [ ] A live `settings`, `posts`, `logs` legacy struktúrájának megőrzése és az audit/RBAC migrációk előfeltételeinek ellenőrzése.
- [ ] Tiszta bootstrap és production-shape PostgreSQL 17 teszt, negatív precondition tesztekkel.
- [ ] Pontos, felülvizsgált migrációs sorrend, rollback/forward-recovery terv és postcondition lekérdezések.

**Tiltás:** nincs `supabase db push`, `supabase migration repair`, production DDL/DML vagy kézi ledger-módosítás a bizonyítékok és pontos migrációs terv rendezése előtt.

### P0 – titkosított production backup

- [ ] AWS backup stack deploy és a CloudFormation outputok ellenőrzése.
- [ ] GitHub Actions secrets: `SUPABASE_DB_URL`, `AWS_BACKUP_ROLE_ARN`, `BACKUP_AGE_IDENTITY`.
- [ ] GitHub Actions variables: source project ref, age recipient, S3 bucket, KMS key ARN, AWS region.
- [ ] Production dump titkosított feltöltése S3-ba.
- [ ] Feltöltött objektum letöltése, visszafejtése, manifest/hash ellenőrzése.
- [ ] Restore-próba külön, izolált PostgreSQL adatbázisba, az eredmény dokumentálása.

A privát age identity kizárólag GitHub Secretben tárolható; chatbe és Gitbe nem kerülhet. A CI local-test round-trip nem helyettesíti ezt a munkát.

### P0 – valós Auth/RLS és felhasználói életciklus

- [ ] Már létező, külön engedélyezett izolált Supabase környezet biztosítása valós JWT/RLS próbákhoz; új tesztprojektet nem hozunk létre.
- [ ] Auth user provisioning, e-mail megerősítés, megbízható `app_metadata.role` kiosztás és admin visszaállítási folyamat.
- [ ] Admin/operator/reader pozitív és negatív teszt minden táblára, műveletre, RPC-re, view-ra és módosító UI útvonalra.
- [ ] Token refresh, revoke, lejárat, logout, szerepkör-demotion és több felhasználós session izoláció valós Supabase Authon.
- [ ] A `logs` audit append útvonal megoldása: a jelenlegi production legacy táblán nincs audit mező/policy; enforced user-JWT módban az auditírásnak biztonságosan és fail-closed módon kell működnie.
- [ ] Auth flag csak a migrációk, admin provisioning és end-to-end tesztek után kapcsolható be.

## 3. Fontos funkcionális és architekturális hiányok

- [ ] A dashboard teljes felhasználói belépési útvonalának, logoutjának, session lejáratának és admin bootstrap folyamatának end-to-end ellenőrzése.
- [ ] Minden üzleti modul felhasználói vs. háttérfolyamat DB-hozzáférésének végleges szétválasztása. A service-role kliens kizárólag szűk, szerveroldali jobokban maradhat.
- [ ] `get_supabase()` deprecated alias fokozatos kivezetése és minden hívó explicit besorolása.
- [ ] `task_actions` auditírás és felhasználói JWT/RLS együttműködésének valós tesztelése.
- [ ] Jóváhagyás művelethez kötése, egyszer használhatóság, lejárat és replay-védelem; az egyszerű `approved=True` önmagában nem biztonsági bizonyíték.
- [ ] E-mail-küldési mellékhatások role-, approval- és szerveroldali kapcsolóvédelmének végponttól végpontig tesztelése.
- [ ] Nincs tenant izoláció: a jelenlegi role modell egyetlen közös workspace-re vonatkozik. Több ügyfél kiszolgálása előtt tenant adatmodell és RLS kell.
- [ ] Audit hash-lánc nem WORM: DB-tulajdonossal szembeni megváltoztathatatlanság, külső hash-ankor, retention/jogi hold és független riasztás nincs kialakítva.
- [ ] Gemini, SMTP, IMAP és ütemezett proaktív workflow éles külső integrációinak bizonyítása kontrollált tesztekkel.
- [ ] Rendszeres restore-gyakorlat, backup retention és riasztási/üzemeltetési runbook.

## 4. Tesztelési hiányok és minőségi kapuk

- [x] A teljes Python/AppTest/browser eredmény és coverage riport rögzítése a `45463032568` futásból.
- [x] Új dashboard Auth/session helper tesztek CI-validálása; `dashboard.py` coverage 82.27% (további UI ágak még javíthatók).
- [ ] Valós Supabase Auth/JWT/RLS integrációs tesztek (mockolt teszt nem elegendő).
- [ ] Minden role és CRUD művelet negatív tesztje, beleértve az RPC-ket, view-kat és közvetlen API hozzáférést.
- [ ] E-mail és task jóváhagyási replay/race/failure tesztek.
- [ ] Backup workflow fail-closed konfigurációs, S3 round-trip és restore utáni integritási teszt.
- [ ] CI artifactok (coverage XML, screenshotok) megőrzési és hozzáférési szabályainak ellenőrzése.

## 5. Kötelező élesítési sorrend

1. PR #13 kódszintű review, teljes CI és dokumentációs konzisztencia.
2. Production schema/migration history reconciliation lezárása.
3. AWS production backup stack és friss, visszaellenőrzött titkosított mentés.
4. Pontos audit → hash-chain → shared-workspace RBAC migrációs sorrend izolált PostgreSQL 17 próbája.
5. Valós Auth/JWT/RLS teszt meglévő, engedélyezett izolált Supabase környezetben.
6. Külön production change terv: előfeltételek, karbantartási ablak, rollback/forward recovery, ellenőrző SQL.
7. A már megadott általános engedély mellett is a pontos éles SQL/migrációs csomag külön, közvetlen jóváhagyása és friss backup után szabad élesíteni.
8. Read-only post-deploy ellenőrzés, teszt, monitorozás, dokumentáció és csak ezután a feature flag bekapcsolása.

## 6. Kapcsolódó dokumentumok

- [Teljes műszaki dokumentáció](JARVIS_DOCUMENTATION.md)
- [Auth/RBAC production reconciliation](AUTH_RBAC_PRODUCTION_RECONCILIATION.md)
- [Supabase klienshozzáférési leltár](SUPABASE_CLIENT_ACCESS_INVENTORY.md)
- [Production migration recovery](production-migration-recovery.md)
- [Friss production read-only revalidation](PRODUCTION_REVALIDATION_2026-11-24_1851UTC.md)
- [PR #13 CI validation](PR13_CI_VALIDATION_2026-11-24.md)
- [PR #13](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/13)

**Production állapot:** a friss, 2026-11-24 18:51 UTC read-only revalidation ugyanazt igazolta: 8 public tábla, mindegyiken RLS engedélyezve, 0 policy; `auth.users` üres; `audit_chain_state` hiányzik; a 12 ellenőrzött strukturált audit oszlopból 0 található a `logs` táblában. Részletek: [PRODUCTION_REVALIDATION_2026-11-24_1851UTC.md](PRODUCTION_REVALIDATION_2026-11-24_1851UTC.md).


## CI státusz pontosítás (2026-11-24)

A `45462249173` futás végül nem lett teljesen zöld: a PostgreSQL 17
integrációs job sikeres, a Python `test` jobot a kombinált
unit/AppTest/browser tesztlépés közben megszakították (cancelled), amikor
újabb commitok kerültek a PR ágra. A feltöltött, de megszakított futáshoz
tartozó coverage XML 3,500/3,732 sort (93.78%) mutat, ebből
`dashboard.py` 82.27%. Ez csak részleges/provizórikus mérés, nem tekinthető
sikeres CI-nek és nem helyettesíti a teljes pytest futás coverage riportját.

Ez a CI-futás történeti állapot. A későbbi teljesen zöld futás a [45463032568](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45463032568), amely 718 passed / 3 skipped és 93.78% coverage eredményt adott. A legutóbbi audit-export és jóváhagyáslejárati módosítások újabbak ennél, ezért azok a legfrissebb branch headen külön CI-ellenőrzést igényelnek.


## Legfrissebb CI – teljesen zöld (2026-11-24)

A [45463032568](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45463032568)
futás mindkét jobja sikeres: 718 teszt passed, 3 skipped, 93.78% line
coverage (3,500/3,732). A PostgreSQL 17 audit/RBAC pgTAP és titkosított
lokális backup/restore integráció is zöld. A coverage és 27 UI screenshot
artifact elérhető a workflow-ban.

Ezzel a repo CI-validációs kapu teljesült az adott commitra. Továbbra is
nyitott blokkoló a production backup, a remote migrációs előzmények
helyreállítása/egyeztetése, valamint a valós Auth/JWT/RLS ellenőrzés.


## Új kódszintű biztonsági javítások – CI-re vár (2026-11-24)

- A chatben előkészített task, célpiac, leadkutatás és e-mail műveletek
  jóváhagyása most 5 perc után lejár, egyszer fogyasztható, és az aktuális
  Supabase Auth felhasználóhoz kötött. A legacy belépésnél a bejelentkezési
  időbélyeg a kötés alapja; azonosítható principal nélkül a jóváhagyás tiltott.
- A külön audit-admin session refresh most megköveteli, hogy a frissített
  Supabase Auth user ID egyezzen az eredetileg bejelentkezett user ID-val.
- Az audit CSV export pending/success/blocked/unknown eseményei a külön
  ellenőrzött admin user-JWT klienssel íródnak, nem a legacy service-role
  dashboard klienssel. A pending export 5 perc után lejár, és admin
  felhasználóhoz kötött.
- Új regressziós tesztek fedik le a jóváhagyás lejáratát, egyszeri
  felhasználását, user-váltást, audit-session identity substitutiont és az
  audit export JWT-kliens szerződését.
- Ezek a változások a korábbi zöld CI után kerültek be; végleges eredményüket
  a legfrissebb PR headen kell megvárni.

**Megmaradó korlát:** az alkalmazás UI approval továbbra sem kriptográfiai
aláírás és nem helyettesíti az adatbázis RLS-t vagy a szerveroldali RBAC-ot.
A production RLS policy-k még nincsenek alkalmazva.
