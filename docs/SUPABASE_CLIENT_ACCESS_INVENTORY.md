# Supabase klienshozzáférési leltár

**Vizsgált ref:** `feat/supabase-auth-rbac-foundation` – `7a7edd2d4ccbd7725ca15a157123f4bce490e278`  
**Állapot:** csak kód- és híváshely-leltár; sem production DB, sem Auth-felhasználó, sem migráció nem módosult.

## Összefoglaló

A kiinduló refen 17 közvetlen `get_supabase()` hívás volt 12 hívómodulban. A leltárban a `dashboard.py` tényleges száma 6 (309, 417, 456, 474, 1043, 1120), a többi 11 modulban egy-egy hívás. A jelenlegi kód ezeket explicit kliensgyárakra választotta szét; a régi `get_supabase()` csak deprecated kompatibilitási alias.

## Híváshelyek és besorolás

| Modul | Közvetlen hívás | Folyamat / hozzáférési osztály | Megjegyzés |
|---|---:|---|---|
| `dashboard.py` | 6 | Interaktív dashboard – átmeneti legacy | Audit események, analitika és chat műveletek; explicit `get_legacy_dashboard_supabase()` service-role klienssel. |
| `health_check.py` | 1 | Operációs diagnosztika – service-role | Read-only diagnosztika, explicit `get_service_supabase()` klienssel; a dashboardról is elérhető. |
| `daily_briefing.py` | 1 | CLI/háttérfeladat | A `main()` belépési pontban épít napi jelentést. |
| `email_inbox.py` | 1 | Háttérfolyamat | IMAP inbox feldolgozás és adatbázis-műveletek. |
| `email_sender.py` | 1 | Háttérfolyamat | Ütemezett, engedélyezési kapcsolókkal védett e-mail feldolgozás/küldés. |
| `follow_up.py` | 1 | Háttérfolyamat | Automatikus utánkövetés. |
| `global_lead_research_job.py` | 1 | Háttérfolyamat | Ütemezett globális leadkutatás és audit. |
| `inbox_monitor.py` | 1 | Háttérfolyamat | Bejövő válaszok figyelése és feldolgozása. |
| `lead_gen.py` | 1 | CLI/háttérfeladat | Átnézett lead CSV importálása és auditja. |
| `proactive_monitor_job.py` | 1 | Háttérfolyamat | Ütemezett proaktív monitor. |
| `jarvis_status.py` | 1 | CLI/operációs diagnosztika | Lead státuszok lekérdezése. |
| `stats.py` | 1 | CLI/operációs diagnosztika | Összesített státusz- és naplólekérdezés. |

## Célzott klienshatárok

1. **Felhasználói kliens (`get_user_supabase(session, allowed_roles=...)`):** kizárólag a bejelentkezett személy Supabase Auth JWT-jével, publikus/publishable kulccsal; a DB-oldali RLS-policy-k érvényesülnek. Ezt a dashboard jelenleg még nem használhatja üzleti műveletekre, mert nincs teljes Auth-bevezetés és táblánkénti RLS.
2. **Háttérfolyamat-kliens (`get_service_supabase()`):** explicit nevű service-role kliens, csak nem felhasználói, szerveroldali jobok számára. A service-role kulcs nem kerülhet Streamlit sessionbe, UI callbackbe vagy böngészőbe.
3. **Átmeneti dashboard kliens (`get_legacy_dashboard_supabase()`):** a régi közös jelszavas dashboard jelenleg privilegizált klienssel működik. Ezt külön, átmeneti és kifejezetten nem-RBAC klienshatárként kell megnevezni; a név szerinti elkülönítés önmagában nem teszi biztonságossá. Csak akkor váltható user JWT-re, ha a felhasználók, a szerepkörök, a szükséges GRANT-ok és az RLS-policy-k készen állnak.
4. **Diagnosztika:** a `health_check.py` egyszerre dashboardról hívható és CLI/üzemeltetési ellenőrzés; a felhasználói UI útvonalat és a háttér/üzemeltetési útvonalat később szét kell választani.

## Biztonságos átállási sorrend

- A jelenlegi hívásleltár és a CI baseline rögzítése.
- Kliensgyárak név szerinti szétválasztása, majd az összes hívó explicit besorolása; a régi `get_supabase()` név fokozatos kivezetése.
- A dashboard legacy kliensének elkülönítése úgy, hogy a régi belépés és az üzleti funkciók ne sérüljenek.
- A háttérjobok service-role kliensének explicit megtartása, a szükséges minimális felület dokumentálásával.
- Auth felhasználók és admin által kezelt szerepkörök előkészítése.
- Production migration history és tényleges séma drift rendezése az eredeti SQL-források helyreállítása után.
- Táblánkénti RLS és GRANT tervezés, majd csak engedélyezett, verziókezelt migrációval történő alkalmazás.
- Valós Auth/JWT/RLS integrációs teszt csak létező, engedélyezett izolált környezetben. Új Supabase tesztprojekt vagy branch nem készül.

## Kódoldali szétválasztás

- `get_service_supabase()` explicit service-role kliens a háttér- és operációs modulokhoz.
- `get_legacy_dashboard_supabase()` explicit átmeneti service-role kliens a régi dashboard számára.
- `get_user_supabase(session, allowed_roles=...)` a `jarvis_auth.verified_user_client()`-en keresztül publikus kulcsot és ellenőrzött/megújított JWT-t használ; a frissített sessiont is visszaadja.
- `get_supabase()` deprecated kompatibilitási alias; új kódban nem használandó.
- A `health_check.py` read-only operációs diagnosztika, explicit service-role klienssel.

## Korlátok

- Ez a leltár nem állítja, hogy a felhasználói kliens vagy RLS már aktív.
- A service-role hozzáférés átnevezése nem helyettesíti a jogosultsági modellt.
- Nem történt production DB-írás, Auth-user létrehozás, RLS-policy alkalmazás vagy kézi SQL.
- A #11, #12 és #13 PR nincs merge-elve.


## 2026-11-24 implementation update

The main dashboard now supports an opt-in `JARVIS_SUPABASE_AUTH_LOGIN_ENABLED` path. When enabled, its chat and analytics business-data clients use the verified user JWT; the flag also enables server-side permission enforcement. The legacy shared-password/service-role path remains the default until production migration history is reconciled and an admin Auth user is provisioned. Audit admin tooling retains its separate verified admin session and server-side audit append boundary.

The versioned `20261124130000_shared_workspace_role_access.sql` migration defines the current single-workspace table policy matrix. It has not been applied to production. See `docs/AUTH_RBAC_PRODUCTION_RECONCILIATION.md` for the exact history mismatch and activation gates.


## 2026-11-24 security follow-up

The separate audit-admin UI now uses the verified admin user-JWT client for
all export audit writes (pending, success, blocked and unknown); it no longer
uses `get_legacy_dashboard_supabase()` for this operation. The pending CSV
export is bound to the verified admin user ID and expires after five minutes.
An expired or mismatched pending export is discarded and recorded as blocked
when the admin-JWT audit append path is available.

The audit session refresh now also requires the refreshed Auth user ID to
match the user ID captured at sign-in. A missing identity or changed identity
fails closed. Unit tests cover the identity-substitution case.

The only remaining `get_legacy_dashboard_supabase()` use in `dashboard.py`
is the explicit fallback of `_get_dashboard_supabase()` while individual
Auth login is disabled. When `JARVIS_SUPABASE_AUTH_LOGIN_ENABLED=true`, the
dashboard obtains its data client via the verified user JWT; it never falls
back to the service-role client.

These are code-level boundaries only. Production currently has no Auth users
and no public RLS policies, as confirmed by the
[2026-11-24 18:51 UTC read-only revalidation](PRODUCTION_REVALIDATION_2026-11-24_1851UTC.md).
The feature flag must remain OFF until migration reconciliation, encrypted
production backup and real Auth/RLS validation are complete.

## 2026-11-24 – legfrissebb hozzáférési határok

- A dashboard audit-admin exportja verified admin user-JWT kliensen írja a
  pending/success/blocked/unknown audit eseményeket; nincs legacy service-role
  kliens az audit export UI útvonalán.
- Az audit-admin session refresh összeveti a frissített user ID-t az eredeti
  bejelentkezési user ID-val.
- A dashboardból indított rendszerdiagnosztika Auth módban kizárólag admin
  számára érhető el, user-JWT-t használ, és nem esik vissza service-role-ra.
  A belső audit-chain és proactive-state táblákat Auth módban nem próbálja
  megkerülni.
- A chatben függőben lévő műveletek és az audit CSV export öt perc után
  lejárnak, egyszer fogyaszthatók és az aktuális felhasználóhoz kötöttek.
- A dashboardban a get_legacy_dashboard_supabase() egyetlen fennmaradó
  használata a _get_dashboard_supabase() explicit legacy fallback ága,
  kizárólag Auth OFF módban. Auth ON esetén a dashboard user-JWT klienst használ.
- A teljes CI [45467211381](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45467211381)
  zöld: 734 passed, 3 skipped, 93.67% coverage.

Productionben továbbra sincs Auth user és nincs RLS policy; a feature flag
maradjon OFF a backup-, migration-history- és valós Auth/RLS kapuk lezárásáig.


## Ellenőrzési pontosítás – 2026-11-25

A korábbi zöld CI eredmény történeti baseline, nem a jelenlegi PR head validációja.
A legutóbbi branch head `a14fca757e2dd6cb73e4e00243ff9fde34635e6b`.
A korábbi audit UI tesztfutás 751 passed, 11 failed, 3 skipped eredményt
adott; a 11 hiba a `tests/test_dashboard_audit_ui.py` fájlban jelentkezett.
Az ezt követő kódjavítások után a jelenlegi head CI-je újraindult.

A jelenlegi push futás [45509971875](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45509971875)
ellenőrzésekor a PostgreSQL 17 audit/RBAC pgTAP és titkosított lokális
age backup/restore job sikeres volt. A Python jobban a függőségtelepítés és
a CloudFormation-validáció sikeres, a Playwright telepítés még futott;
a compileall és a teljes unit/AppTest/browser tesztlépés még nem kezdődött el.
Végleges tesztszám és coverage nincs. A PR esemény futása is külön ellenőrzendő.

Ezért a jelenlegi kódállapot még nem minősíthető teljesen CI-validáltnak.
A PostgreSQL/age eredmény izolált CI-környezetből származik, nem production
backup vagy valós Supabase Auth/JWT/RLS bizonyíték. A production Auth flag
maradjon OFF; nincs production migrációs vagy adatbázis-módosítási engedély.
