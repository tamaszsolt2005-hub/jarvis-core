# Auth/RBAC és production migrációs rendezés

**Állapot:** kódszintű előkészítés a `feat/supabase-auth-rbac-foundation` ágon. Production adatbázis, Auth-felhasználók és jogosultságok nem változtak.

## 1. Dashboard Auth

A fő Streamlit belépés egyéni Supabase Auth módot kapott. Bekapcsolásához a szerveroldali `JARVIS_SUPABASE_AUTH_LOGIN_ENABLED=true` kapcsoló szükséges. Alapértelmezésben kikapcsolt; kikapcsolt módban a régi közös jelszavas útvonal marad.

Auth módban:
- e-mail+jelszó Supabase Auth belépés történik;
- a felhasználó azonosítóját és szerepét az Auth `get_user()` ellenőrzi;
- kizárólag a megerősített e-mail és a szerver által kezelt `app_metadata.role` fogadható el;
- minden Streamlit rerun frissíti/ellenőrzi a sessiont;
- a dashboard üzleti adatbázis-kliens publikus kulcsot és user JWT-t használ, service-role fallback nélkül;
- kijelentkezéskor a Supabase Auth session visszavonása megkísérlődik;
- az Auth mód automatikusan bekapcsolja a szerveroldali RBAC enforcementet is.

A kapcsolót addig nem szabad élesben bekapcsolni, amíg nincs legalább egy megerősített admin Auth-fiók, ellenőrzött szerepkör-kiosztás, és a lent részletezett migrációk biztonságos alkalmazása. A jelenlegi read-only ellenőrzéskor a production `auth.users` tábla üres volt.

## 2. RLS/GRANT modell

Az új `20261124130000_shared_workspace_role_access.sql` migráció a jelenlegi **egyetlen közös JARVIS-munkaterület** szerepkörmodelljét valósítja meg. Nem tenant-izoláció: több ügyfél adatainak elkülönítésére nem alkalmas.

| Tábla | Admin | Operator | Reader | Háttérfolyamat |
|---|---|---|---|---|
| `leads`, `tasks`, `email_drafts`, `jarvis_memory`, `posts` | CRUD | CRUD | SELECT | service_role |
| `settings` | CRUD | csak `lead_research_market` SELECT | nincs hozzáférés | service_role |
| `logs` | SELECT + saját audit append | saját audit append | nincs hozzáférés | service_role append |
| `audit_chain_state` | SELECT | nincs hozzáférés | nincs hozzáférés | service_role |
| `jarvis_proactive_state` | nincs hozzáférés | nincs hozzáférés | nincs hozzáférés | service_role |

- Az engedélyezési döntések kizárólag `app_metadata.role` claimből származnak.
- Az auditbejegyzés INSERT csak admin/operator számára engedélyezett; a hash trigger az `actor_user_id` értékét a hitelesített `auth.uid()` alapján állítja be.
- A hash-lánc trigger szűken korlátozott `SECURITY DEFINER` függvény, fix `search_path`-tal; közvetlen EXECUTE joga az API-szerepektől vissza van vonva. A kliens továbbra sem módosíthat vagy törölhet audit sort.
- A proactive monitor állapota kizárólag szerveroldali háttérfolyamatnak érhető el.
- A CI pgTAP teszteli az anon tiltást, a reader írási tiltást, operator/admin különbségeket és az audit actor kötését.

## 3. Production migrációs előzmények – kötelező blokkoló

A production projekt korábbi read-only felmérése szerint a remote migration ledger az alábbi öt, a repositoryból hiányzó migrációt tartalmazza:

- `20261119191911_create_jarvis_memory_and_fk_indexes`
- `20261119192040_complete_jarvis_runtime_schema`
- `20261119192145_enable_rls_on_legacy_posts`
- `20261119192412_revoke_anon_authenticated_public_table_and_sequence_privileges`
- `20261119192559_secure_postgres_default_privileges_public_schema`

További eltérés:
- a repo `20261117_add_leads_website.sql` és `20261117_add_logs_level.sql` fájljai nem szerepelnek a remote ledgerben, miközben hatásuk a live sémában látszik;
- a repo auditmigrációi (`20261120090000`, `20261123093000`) a remote ledgerben nem szerepelnek;
- a live `settings` tábla integer ID/sequence sémát használ, és a legacy `posts` tábla nincs a repo aktuális sémaképében;
- a production `logs` kezdeti sémája legacy oszlopokat tartalmazott, ezért az auditmigrációk előfeltétele a naplóséma bővítése.

**Következmény:** a `supabase db push` nem biztonságos, amíg a hiányzó történeti SQL-források nem kerülnek elő és a repo/remote migrációs állapot nincs összeegyeztetve. A történeti SQL-t nem szabad a jelenlegi sémából találgatva rekonstruálni, és a remote migration history-t sem szabad vakon átírni.

### Biztonságos további sorrend

1. Az öt hiányzó migráció eredeti SQL-forrásának visszakeresése a korábbi fejlesztési környezetből, artefaktumokból vagy backupból.
2. A visszakeresett fájlok hash/hatás összevetése a live sémával és a repository migrációkkal.
3. Dokumentált baseline/reconciliation terv és tiszta, izolált PostgreSQL 17 próbafuttatás.
4. A hiányzó történeti állapot rendezése után az audit- és RBAC-migrációk sorrendhelyes próbafuttatása.
5. Csak külön, konkrét production jóváhagyás után éles alkalmazás és utólagos read-only ellenőrzés.

## Aktiválási kapuk

- Nincs production Auth user; admin-fiókot és szerepkört még nem hoztunk létre.
- A fő Auth belépés kapcsolója alapértelmezésben OFF.
- Az új RLS migráció verziókezelt fájlként elkészült, de productionben nem futott le.
- A migration history drift miatt production migráció nem indítható.
- Nincs új Supabase tesztprojekt vagy branch létrehozva.


## 4. Dashboard Auth tesztelési állapot (2026-11-24)

A PR #13 ágon új `tests/test_dashboard_auth_helpers.py` tesztcsomag készült.
A teszt a dashboard Auth helper függvényeit külön, izolált Streamlit
tesztduplával futtatja. Lefedett esetek:

- Auth feature flag kikapcsolt és bekapcsolt állapota;
- a bejelentkezett session átadása a user-JWT kliensnek;
- engedélyezett szerepkörök explicit halmaza;
- frissített token és role visszaírása a Streamlit sessionbe;
- hiányzó vagy visszavont session esetén fail-closed viselkedés;
- a régi DB-kliens, szerepkör, Auth session és függő művelet eltávolítása
  sikertelen session-ellenőrzés után;
- legacy shared-password kliens használata kizárólag Auth OFF módban.

Az első CI futásban (45461593492) 717 teszt sikerült, 1 teszt a hiányos
Streamlit tesztdupla miatt bukott el, 3 teszt skipelődött. Az alkalmazáskód
helyesen törölte a lejárt session állapotát; a tesztduplából hiányoztak a
visszairányított login űrlap metódusai. A tesztdupla javítása:
`c1d50154451c35f10d9f16094dbef7680b7e9fed`.

A javított CI futás (45462249173) PostgreSQL 17 integrációs jobja sikeres,
beleértve az audit/RBAC migrációkat, pgTAP ellenőrzéseket és a titkosított,
izolált local backup/restore körutat. A Python jobban a CloudFormation
validáció, Playwright telepítés és compileall is sikeres; az utolsó ellenőrzés
idején a Python/AppTest/browser tesztlépés még futott. Emiatt a végleges
tesztszám és coverage még nincs igazolva.

**Fontos korlát:** ezek mockolt dashboard-helper tesztek. Nem bizonyítják a
Supabase Auth szolgáltatás valódi JWT refresh, token-visszavonás vagy RLS
policy integrációját. Ehhez már létező, külön engedélyezett izolált Supabase
környezet szükséges; új projektet nem hozunk létre, production nem használható
tesztkörnyezetként.


## 2026-11-24 – legfrissebb production read-only állapot

A 18:51 UTC-kor végzett új read-only ellenőrzés megerősítette:
- 8 public tábla, mindegyiken RLS enabled;
- 0 public RLS policy és 8 Supabase Security Advisor `rls_enabled_no_policy` finding;
- `auth.users` száma 0;
- `public.audit_chain_state` nem létezik;
- a `logs` táblán a 12 vizsgált strukturált audit/hash oszlopból egy sem található;
- a remote ledgerben továbbra is öt, repositoryból hiányzó történeti migráció van.

A pontos tábla-/oszlopleltár és a migrációverziók:
[`PRODUCTION_REVALIDATION_2026-11-24_1851UTC.md`](PRODUCTION_REVALIDATION_2026-11-24_1851UTC.md).
A vizsgálat kizárólag read-only SQL/catalog lekérdezéseket használt; production
adat, séma, policy, Auth-fiók és migration history nem változott.

## 2026-11-24 – audit session és export hardening

- Az audit-admin session refresh már összeveti a frissített Auth user ID-t a
  bejelentkezéskor rögzített user ID-val; hiányzó vagy eltérő identitás tiltást
  eredményez.
- A CSV export auditbejegyzései a verified admin user-JWT klienssel készülnek,
  nem a service-role legacy dashboard klienssel.
- A pending export admin userhez kötött és öt perc után lejár; lejárt vagy
  eltérő adminhoz tartozó pending export nem tölthető le.
- A task/leadkutatás/célpiac/chat-email pending jóváhagyások öt perc után
  lejárnak, egyszer fogyaszthatók, és Auth módban a felhasználóhoz kötöttek.
- A hozzájuk tartozó regressziós tesztek bekerültek, de a korábbi teljesen zöld
  CI run után; a legfrissebb branch head teljes CI-je szükséges.

A production Auth flag továbbra is OFF marad. A policyk és migrációk
productionre alkalmazása a backup- és migration-history gate lezárásáig tilos.
