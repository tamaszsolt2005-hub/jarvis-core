# JARVIS – teljes projekt- és műszaki dokumentáció

> **Felülvizsgálat:** 2026-11-25  
> **Vizsgált fejlesztési branch:** `feat/supabase-auth-rbac-foundation`  
> **Igazolt branch commit:** `e6736101405180c220d6b96b5a7a3c1d890813e0`  
> **Repository:** `tamaszsolt2005-hub/jarvis-core`

Ez az egyetlen részletes, ember által olvasható projekt-dokumentáció. A forráskód, a Supabase-migrációk és a GitHub Actions workflow-k az elsődleges technikai bizonyítékok. A dokumentum külön választja a kódban létező funkciót, a tesztelt működést és az éles környezetben ténylegesen igazolt állapotot.

## Tartalom

1. [Projektáttekintés](#1-projektáttekintés)
2. [Funkciók és állapotuk](#2-funkciók-és-állapotuk)
3. [Architektúra és modulok](#3-architektúra-és-modulok)
4. [Adatmodell és production Supabase](#4-adatmodell-és-production-supabase)
5. [Automatizmusok](#5-automatizmusok)
6. [Biztonság és jogosultságok](#6-biztonság-és-jogosultságok)
7. [Audit és hibakezelés](#7-audit-és-hibakezelés)
8. [Mentés és visszaállítás](#8-mentés-és-visszaállítás)
9. [Telepítés és konfiguráció](#9-telepítés-és-konfiguráció)
10. [Tesztelés és bizonyítékok](#10-tesztelés-és-bizonyítékok)
11. [Ismert hibák és blokkolók](#11-ismert-hibák-és-blokkolók)
12. [Fejlesztési sorrend](#12-fejlesztési-sorrend)



## Aktuális állapot és bizonyítékok – 2026-11-25

A fejlesztési branch aktuális commitja `e6736101405180c220d6b96b5a7a3c1d890813e0`. A [45571463053 CI-futás](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45571463053) teljesen sikeres: **762 passed, 3 skipped, 96.47% Python line coverage**. A PostgreSQL 17 + pgTAP integráció, az izolált age backup/restore round-trip, CloudFormation-validáció, Playwright telepítés és compileall is sikeres.

Ez a repository és izolált CI környezet bizonyítéka. Nem igazolja a production AWS/S3 mentést, production restore-t, valós Supabase Auth/JWT/RLS viselkedést vagy éles e-mail kézbesítést. A production állapot ismert read-only vizsgálata szerint RLS policy és Auth user még nincs telepítve; a production Auth flag ezért OFF marad. A PR #13 nyitott és draft.

A végrehajtandó feladatok, felelősségi területek és elfogadási kritériumok a [fennmaradó feladatok és release gate dokumentumban](REMAINING_WORK_AND_RELEASE_GATES.md) vannak. A dokumentum a CI-ben igazolt állapotot elkülöníti a productionben még nem bizonyított képességektől.

## 1. Projektáttekintés

A **JARVIS** magyar nyelvű, Streamlit-alapú, chat-központú B2B üzleti intelligencia-asszisztens. Természetes nyelvű kérdésekből üzleti szándékot azonosít, szükséges adatokat tölt be a Supabase-ből, majd Google Gemini modellel készít választ vagy irányít egy dedikált üzleti műveletet.

Célja a céges leadek kutatásának és értékelésének, az üzleti minták elemzésének, a feladatkezelésnek, a memóriának, a vezetői összefoglalóknak és a kontrollált e-mail-folyamatoknak az egy felületen történő támogatása.

| Terület | Technológia |
|---|---|
| Nyelv, runtime | Python 3.11 |
| UI | Streamlit |
| LLM | Google Gemini API |
| Adatbázis | Supabase / PostgreSQL |
| Automatizmusok, CI | GitHub Actions |
| Tesztek | pytest, pytest-cov, Streamlit AppTest, Playwright |

A `jarvis_common.py` alapértelmezett modellje `gemini-3.8-flash`; a `GEMINI_MODEL` felülírhatja. A régi `gemini-2.5-flash` és `gemini-2.5-pro` konfigurációk az alapértelmezett modellre esnek vissza.

### Állapotok értelmezése

- **Implementált:** kód vagy workflow megtalálható a vizsgált commitban.
- **Automatikusan tesztelt:** azonosítható CI-futtatás tesztelte.
- **Integrációsan igazolt:** valós szolgáltatással, kontrollált környezetben ellenőrizték.
- **Élesben igazolt:** valós éles folyamat sikeres futása megfigyelhető.
- **Részleges / blokkolt:** van implementáció, de az egész funkció vagy valamely függősége még nem aktív.
- **Tervezett:** nincs kész implementáció.

A kód jelenléte önmagában nem bizonyít külső integrációt vagy production működést.

## 2. Funkciók és állapotuk

| Funkció | Jelenlegi állapot | Korlát / megjegyzés |
|---|---|---|
| Magyar nyelvű chat, Gemini-válasz | Implementált | API-működés a titkoktól és külső szolgáltatástól függ. |
| Kontextusfüggő Supabase-adatlekérés | Implementált | Fő üzleti kliens service-role jogosultságú, nem user-RBAC. |
| Globális céges leadkutatás | Implementált, ütemezett | 2026-11-23-án auditmező-hiány miatt fail-closed módon leállt. |
| Weboldal-audit | Implementált | Nyilvános URL-ek, SSRF-védett HTTP; nem igazol vásárlási szándékot. |
| Lead scoring / prioritás | Implementált | Kutatási priorizálás, nem hozzájárulás vagy konverziós garancia. |
| Üzleti stratégiai összesítés | Implementált | A tárolt kutatási adatok minőségétől függ. |
| Explicit memória mentése/keresése/törlése | Implementált | Csak kifejezett felhasználói utasításra. |
| Üzleti tanulás | Implementált | Rögzített tapasztalatokból készít óvatos mintákat; nem állít ok-okozatot. |
| Jóváhagyásos feladatkezelés | Implementált | Előnézet és külön jóváhagyás szükséges. |
| Chat-analitika, vezetői riport | Implementált | A hiányzó napló nem automatikusan modulhiba. |
| Napi vezetői briefing | Ütemezett | Workflow-artifactot készít; e-mailes értesítés nem következik belőle. |
| Chatből e-mail-tervezet/küldési kísérlet | Implementált, kapuzott | SMTP-átvétel nem egyenlő a címzett postaládájába érkezéssel. |
| Háttér e-mail és utánkövetés | Kódban implementált, élesben nem igazolt | Hozzájárulás, válasz, leiratkozás és jóváhagyás kötelező. |
| IMAP válasz-/leiratkozás-figyelés | Kódban implementált | Valós IMAP-folyamat végponttól végpontig nem igazolt. |
| Proaktív lead-/feladatfigyelés | Napi workflow-val bekötve | Snapshotot ír; éles sikeres futása nem igazolt. |
| Rendszerdiagnosztika | Implementált | Táblákat, konfigurációt és auditmezőket ellenőriz. |
| Központi hibajelentés | Implementált és regressziós teszttel ellenőrzött | Hiányzó `logs.error` oszlopnál a hibaesemény a legacy `module/level/message/created_at` oszlopokkal is menthető. A production írási útvonal teljes működését külön éles ellenőrzés igazolja. |
| Strukturált audit + admin auditoldal | Kódban és migrációban előkészített | A production `logs` táblából hiányzik minden strukturált auditmező, az auditlánc-tábla, a trigger és a policy; az éles audit továbbra is blokkolt a migráció jóváhagyott alkalmazásáig. |
| Teljes admin/operator/reader RBAC | Nem aktív | Részleges Auth-alapok PR #13-ban, de nem merge-elt / nem aktivált. |
| Titkosított DB backup | Kód és automatikus round-trip CI-teszt | A CI valós PostgreSQL 17 + age mentés/visszaállítási kört tesztel. Az éles S3 mentés a GitHub/AWS konfiguráció hiányában még nem igazolt. |
| Lokális restore-próba | CI-ben automatizált | Elkülönített, ideiglenes PostgreSQL 17 adatbázisba valódi visszaállítás történik; Supabase tesztprojektet továbbra sem hozunk létre. |

### Működési alapelvek

1. A leadkutatás nem jelent kapcsolatfelvételi vagy marketing-hozzájárulást.
2. A leadpontszám nem bizonyít fizetőképességet, vásárlási szándékot vagy várható ROI-t.
3. Módosító chatművelet csak előnézet és külön jóváhagyás után hajtható végre.
4. Memória csak explicit mentési vagy törlési utasításra módosul.
5. E-mail háttérküldéshez időbélyeges hozzájárulás és jóváhagyott kapcsolatfelvétel kell.
6. Bizonytalan SMTP-átvétel után nincs vak automatikus újraküldés.
7. Ha a kötelező `pending` audit nem menthető, az érzékeny művelet leáll.

## 3. Architektúra és modulok

### Adatfolyam

1. A felhasználó természetes nyelvű üzenetet küld a Streamlit chatben.
2. A dashboard felismeri a kutatási, memória-, feladat-, e-mail-, diagnosztikai vagy analitikai szándékot.
3. A megfelelő modul a Supabase-ből betölti a szükséges üzleti kontextust.
4. A Gemini megkapja a releváns kontextust és előállítja a választ.
5. A válasz megjelenik; a technikai események naplózhatók.
6. Módosító vagy külső hatású művelet csak a jóváhagyási kapun keresztül futhat.

A weboldalak, e-mailek és visszakeresett memóriák tartalma nem megbízható utasítás, hanem adat. A teljes felhasználói kérdést és Gemini-választ nem szabad automatikusan technikai naplóba írni.

### Fő rétegek

- **UI/vezérlés:** Streamlit dashboard és chat-router.
- **Közös szolgáltatás:** konfiguráció, Gemini- és Supabase-kliensek, naplózás, audit.
- **Üzleti modulok:** kutatás, web-audit, scoring, stratégia, memória, feladatok, analitika, e-mail.
- **Adatréteg:** Supabase/PostgreSQL.
- **Háttér:** GitHub Actions workflow-k.
- **Minőség:** pytest, AppTest, Playwright, SQL-tesztek.

### Fő fájlok

| Fájl | Felelősség |
|---|---|
| `dashboard.py` | Streamlit UI, chat-router, session, jóváhagyások, audit- és analitikafelület |
| `jarvis_common.py` | Közös config, Gemini/Supabase kliens, naplózás, audit |
| `jarvis_errors.py` | Központi hibajelentés, titokszűrés, logger fallback |
| `global_lead_research.py`, `global_lead_research_job.py` | Céges kutatás, piacválasztás, ütemezett job |
| `web_auditor.py`, `safe_http.py` | Biztonságos weboldal-lekérés és elemzés |
| `lead_scoring.py`, `intelligent_lead_scoring.py` | Leadprioritás |
| `business_strategy.py`, `business_learning.py` | Üzleti összesítés és explicit tapasztalatokból minták |
| `jarvis_memory.py` | Memória mentése, keresése, inaktiválása |
| `task_actions.py` | Feladatparancsok validálása és végrehajtása |
| `jarvis_analytics.py`, `daily_briefing.py` | Analitika, vezetői riport, napi briefing |
| `proactive_monitor.py`, `proactive_monitor_job.py` | Napi változás-pillanatkép |
| `health_check.py` | Konfiguráció, táblák, auditmezők diagnosztikája |
| `email_sender.py`, `email_inbox.py`, `chat_email.py`, `email_utils.py` | Küldés, inbox, chat e-mail-folyamat |
| `audit_admin.py` | Auth-alapú admin auditnézet, lapozás, export, integritás-ellenőrzés |
| `lead_gen.py`, `decision_support.py` | CSV leadimport, döntéstámogatási prompt |
| `scripts/supabase_backup.py` | Titkosított public-séma backup és sandbox restore |
| `infra/aws-backup-stack.yaml` | Előkészített AWS S3/KMS/OIDC infrastruktúra |

További régebbi vagy külön célú fájlok: `follow_up.py`, `inbox_monitor.py`, `reply_analyzer.py`, `inbox_analyzer.py`, `jarvis_status.py`, `stats.py`. Ezek pontos használatát kód- és teszthivatkozások alapján kell eldönteni. A dokumentációs összevonás Python-fájlokat nem töröl.

## 4. Adatmodell és production Supabase

### Repository-séma

A `supabase/schema.sql` hét alkalmazástáblát definiál: `leads`, `tasks`, `email_drafts`, `logs`, `settings`, `jarvis_memory`, `jarvis_proactive_state`.

### Production audit – 2026-11-23

A meglévő Jarvis Supabase-projekt ellenőrzéskor `ACTIVE_HEALTHY` állapotú volt, `eu-west-1` régióban, PostgreSQL `17.11.0.019` verzióval. A `public` sémában nyolc tábla volt: `leads`, `tasks`, `email_drafts`, `logs`, `settings`, `jarvis_memory`, `jarvis_proactive_state`, `posts`.

A `posts` élő legacy tábla, nem szerepel a repo snapshotban, és a vizsgált kód nem hivatkozott rá. Ettől még nem szabad automatikusan átvenni vagy törölni; előbb függőségi ellenőrzés kell.

Lényeges eltérések:

- Mind a nyolc production public táblán RLS engedélyezett, de az auditkor egyiken sem volt RLS policy.
- Közvetlen táblajogosultság a `postgres` és `service_role` szerepköröknél volt.
- A production `logs` legacy oszlopai: `id`, `module`, `message`, `created_at`, `level`. Hiányoznak a kódban elvárt strukturált mezők, köztük `action`, `error`, `operation_id`.
- A production `settings` integer `id` primary key-t és unique `key` mezőt használ; a repo snapshot ettől eltér.
- A production `tasks` és `email_drafts` táblákban lead-ID indexek voltak, amelyek a repo snapshotban nincsenek.

**A `supabase/schema.sql` nem pontos production-séma-export, és nem helyettesíti az eredeti migrációs előzményeket.** A production audit csak olvasási műveleteket végzett; adatot vagy sémát nem módosított.

### Öt hiányzó remote migrációforrás

A remote migration ledger az alábbi verziókat rögzítette, de az eredeti SQL nem található meg a repositoryban/Git-előzményekben:

| Verzió | Remote név |
|---|---|
| `20261119191911` | `create_jarvis_memory_and_fk_indexes` |
| `20261119192040` | `complete_jarvis_runtime_schema` |
| `20261119192145` | `enable_rls_on_legacy_posts` |
| `20261119192412` | `revoke_anon_authenticated_public_table_and_sequence_privileges` |
| `20261119192559` | `secure_postgres_default_privileges_public_schema` |

A migrációnevek nem igazolják az SQL tényleges tartalmát; nem szabad kitalálni vagy névből visszaépíteni az eredeti SQL-t.

**Biztonsági kapu:** a drift rendezéséig tilos a `supabase db push`, migration repair, a ledger átírása, találgatott DDL, SQL Editor-módosítás, production GRANT/REVOKE vagy RLS policy-telepítés. Előbb hiteles schema-only dump, eltérésmátrix, bizonyítékon alapuló új migráció, külön jóváhagyott nem éles teszt és restore terv kell. Production bevezetéshez külön jóváhagyás szükséges.

## 5. Automatizmusok

A workflow-k UTC-idő szerint:

| Idő | Workflow | Funkció | Ellenőrzési állapot |
|---:|---|---|---|
| 02:15 | `database-backup.yml` | Titkosított Supabase public DB backup, S3 upload | AWS/S3 konfiguráció és sikeres backup nem igazolt |
| 08:00 | `global-lead-research.yml` | Legfeljebb 15 új globális cég kutatása | 2026-11-23-án logs auditmező-hiány miatt sikertelen |
| 08:20 | `proactive-monitor.yml` | Lead- és feladatváltozások pillanatképe | Kód és workflow megvan; éles siker nem igazolt |
| 08:30 | `daily-briefing.yml` | Napi vezetői összefoglaló | 14 napos artifact; valós adatkapcsolat külön igazolandó |
| 09:15 | `email-automation.yml` | Inbox-válasz/leiratkozás és feltételes küldés | Éles SMTP/IMAP és kézbesítés nem igazolt |
| Push/PR/kézi | `ci.yml` | Statikus, unit, AppTest, Playwright tesztek | Csak az adott commit CI-eredményét igazolja |

A `jarvis.yml` és `jarvis-cron.yml` letiltott no-op legacy workflow; nem aktív automatizmus.

### Proaktív monitor

A `proactive_monitor.py` legfeljebb 2000 leadet és 1000 feladatot vizsgál, az előző sikeres snapshothoz viszonyítja az új/módosult rekordokat és státusz-, prioritás-, határidőváltozásokat. Az első futás alapállapotot ment; a következő futások a `jarvis_proactive_state` tábla `daily_proactive_snapshot` kulcsú rekordját upsertelik. Nem módosít leadet/feladatot/e-mailt, és nem küld levelet. Mintavételi korlátja miatt nem teljes adatbázis-audit. A workflow artifact 14 napig marad meg.

A dashboard `_proactive_signals()` állapotjelzése ettől különálló, pillanatnyi jelzés.

### Production leadkutatási hiba – 2026-11-23

A [45252422431 workflow-futás](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45252422431) sikertelen volt. A kötelező secret-ellenőrzés sikerült, de a kutatás előtt a `pending` strukturált auditot nem lehetett elmenteni, mert a Supabase séma-cache nem találta a `logs.action` oszlopot. A központi hibajelentés most már felismeri a hiányzó `logs.error` oszlopot, és a régi `module/level/message/created_at` mezőkkel próbál biztonságos fallback mentést; ez nem oldja fel a `pending` audit hiányát, ezért a leadkutatás továbbra is fail-closed módon leáll, amíg a sémadriftet jóváhagyott módon nem rendezzük.

A job fail-closed módon, a `research_global_companies()` előtt leállt; a leadkutatás nem indult el. Ez production sémadrift, nem hiányzó GitHub secret. Migrációs egyeztetés nélkül nem javítható biztonságosan.

## 6. Biztonság és jogosultságok

### Dashboard és adatbázis-kliens

A Streamlit dashboard közös `JARVIS_DASHBOARD_PASSWORD` jelszóval védett; a tesztek szerint a session maximum 8 órás. Ez nem egyedi identitás és nem teljes RBAC.

A `jarvis_common.get_supabase()` szerveroldali kliens `SUPABASE_SERVICE_ROLE_KEY`-t, ennek hiányában legacy `SUPABASE_KEY`-t használ. A service-role megkerüli az RLS-t, ezért titkos szerveroldali környezetben kell tartani; nem kerülhet browserbe, kliensoldali kódba vagy naplóba.

### Cél RBAC-modell – jelenleg nem aktív

| Művelet | admin | operator | reader |
|---|---:|---:|---:|
| Lead/feladat/tervezet olvasás | Igen | Igen | Igen |
| Lead/feladat módosítás | Igen | Igen | Nem |
| Jóváhagyott e-mail | Igen | Külön megerősítéssel | Nem |
| Analitika olvasás | Igen | Igen | Igen |
| Rendszerbeállítás/felhasználókezelés | Igen | Nem | Nem |
| Admin audit olvasása | Igen | Nem | Nem |
| Memória módosítása | Igen | Explicit utasítással | Nem |

A bevezetéshez egyedi Supabase Auth-identitás, trusted `app_metadata.role`, user-JWT alapú adatbázis-kliens, táblánkénti RLS policy és anon/reader/operator/admin negatív teszt szükséges. A user által módosítható `user_metadata` nem lehet jogosultság alapja; hiányzó vagy hibás szerepkörnél fail-closed hozzáférés kell.

A PR #13 (`feat/supabase-auth-rbac-foundation`) a vizsgált állapotban draft és nem merge-elt. Tartalmaz Auth-segédet és szerepkör-ellenőrzést, de a fő dashboard login nincs átállítva, az üzleti modulok service-role klienst használnak, production Auth/RLS/migráció nem történt. A [45251071690 PR CI](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45251071690) sikeres volt, de ez nem bizonyít production RBAC-aktiválást. [PR #13](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/13).

### Audit-admin és tartalmi/network biztonság

Az `audit_admin.py` külön Supabase Auth admin útvonalat használ; csak `SUPABASE_PUBLISHABLE_KEY` vagy legacy `SUPABASE_ANON_KEY` publikus kulcsot fogad el. Auth user ellenőrzés és trusted `app_metadata.role = "admin"` szükséges. Ez nem a teljes üzleti RBAC, production logs-séma és policy hiányában az audit UI éles használata blokkolt.

A `safe_http.py` és `web_auditor.py` DNS/IP-validálással és redirect-ellenőrzéssel csökkenti az SSRF-kockázatot. Külső weboldal, e-mail vagy memória tartalma nem megbízható utasítás. Soha ne kerüljön logba nyers jelszó, token, API-kulcs, hitelesített URL, e-mail-törzs vagy teljes lead-payload. A technikai hozzájárulás-ellenőrzés nem helyettesíti a célország és kommunikációs cél jogi vizsgálatát.

Nincs tenant-szintű adatszegregáció; a jelenlegi adatmodell egy üzleti munkaterületet feltételez. Az `approved=True` belső alkalmazáskorlát, nem hitelesítési token.

## 7. Audit és hibakezelés

A repository auditmegoldása a `public.logs` táblát bővíti. A kódban definiált mezők közé tartozik: `operation_id`, `action`, `status`, `result`, `error`, `approved`, `recipient`, `subject`, `delivery_id`, `actor_user_id`, `previous_hash`, `entry_hash`. Audit státuszok: `pending`, `success`, `failed`, `blocked`, `unknown`.

Auditált útvonalak: jóváhagyott feladatműveletek, chat- és háttér e-mail, inbox válasz/leiratkozás, CSV-import, globális kutatási job. Érzékeny művelet előtt a `pending` audit mentése kötelező; hiba esetén a művelet álljon le. SMTP-átvétel utáni bizonytalan auditállapotban ne történjen vak újraküldés.

A repository SQL-kód admin-only olvasást, kliensoldali módosítás tiltását, append-only triggerelést, SHA-256 hash-láncot, ellenőrző függvényt, kurzoros lapozást és CSV-exportot tartalmaz. Ez nem WORM: privilegizált DB-tulajdonos módosíthatja a védelmeket. Külső immutable archívum, külső hash-ankor, jóváhagyott megőrzési idő, jogi hold és ütemezett független integritásellenőrzés nincs igazolva.

**Production:** a 2026-11-23-i auditkor a production `logs` csak a legacy oszlopokat tartalmazta, az audit SQL-migrációk nem voltak alkalmazva. A kódban meglévő audit nem tekinthető élesben aktív, teljes védelemnek.

### Központi hibakezelés

A `jarvis_errors.report_error()` három szintet kezel:

| Szint | Jelentés |
|---|---|
| `warning` | Helyreállítható/opcionális probléma; a kihagyott funkciót jelezni kell. |
| `error` | Az aktuális művelet sikertelen; azt meg kell szakítani. |
| `critical` | Nem garantálható a biztonságos folytatás; job hibás zárása vagy kivétel továbbdobása szükséges. |

A modul maszkolja a gyakori jelszó-, kulcs-, token-, Bearer- és URL-hitelesítő adat mintákat, valamint ismert secret értékeket. Supabase log hiba esetén Python logger a fallback; tilos rekurzív DB logolás. A redakció védelmi réteg, nem garancia minden érzékeny adatra. Új hibakezeléshez redakciós, metaadat-, kivétel- és fail-closed tesztek kellenek.

## 8. Mentés és visszaállítás

A `scripts/supabase_backup.py` a teljes `public` sémáról és adatairól PostgreSQL logical dumpot készít, UTC timestampet, UUID-t és SHA-256 manifestet használ, majd `age` recipient kulccsal titkosítható. A DB-jelszó nem kerülhet parancssori URL-be. A tényleges production dump a repo snapshoton kívüli `posts` táblát is megőrzi.

A napi 02:15 UTC workflow rövid életű GitHub OIDC AWS role-t, privát S3 bucketet és SSE-KMS feltöltést használ. A szükséges konfiguráció hiányában a workflow most hibával leáll, nem jelzi sikeresnek a kihagyott mentést. Feltöltés után ellenőrzi a KMS-metaadatokat, visszatölti az objektumot, majd az age dekódolást és a manifest SHA-256 hash-eit is ellenőrzi. Az `infra/aws-backup-stack.yaml` előkészített, de a stack telepítése nem igazolt.

**Szükséges Actions secret-ek:** `SUPABASE_DB_URL`, `AWS_BACKUP_ROLE_ARN`, `BACKUP_AGE_IDENTITY` (az age privát kulcs teljes tartalma, kizárólag GitHub Secretként).

**Szükséges Actions változók:** `JARVIS_BACKUP_SOURCE_PROJECT_REF`, `BACKUP_AGE_RECIPIENT`, `BACKUP_AWS_REGION`, `BACKUP_S3_BUCKET`, `BACKUP_S3_KMS_KEY_ARN`.

Az éles mentés és S3-feltöltés csak a GitHub Actions secret-ek/változók és az AWS stack telepítése után igazolható. A `verify` parancs a letöltött objektumot dekódolja, ellenőrzi az archívum fájlkészletét és SHA-256 hash-eit. A CI külön, ideiglenes PostgreSQL 17 adatbázisban valódi titkosított backup/restore round-tripet futtat. A nem éles Supabase restore továbbra is csak külön, üres, allowlistelt projektbe engedhető; új Supabase tesztprojektet nem hozunk létre.

A public dump nem tartalmazza a Supabase által kezelt `auth`, `storage`, `realtime` sémák teljes tartalmát, Storage bináris objektumokat, projektbeállításokat, API-kulcsokat, Vault root kulcsot vagy custom role jelszavakat. Auth/Storage használat előtt külön platform- és objektummentési terv és restore-próba szükséges.

## 9. Telepítés és konfiguráció

Helyi indítás:

```bash
python -m pip install -r requirements.txt
streamlit run dashboard.py --server.port 8501
```

Tesztfüggőségek és tesztfuttatás:

```bash
python -m pip install -r requirements-test.txt
python -m playwright install chromium firefox webkit
python -m compileall -q .
python -m pytest -q
```

A CI coverage riportot is generál (`pytest --cov`); a küszöb 80%.

Fő konfigurációs kulcsok – csak neveket dokumentálunk, értékeket soha:

| Kulcs | Cél |
|---|---|
| `SUPABASE_URL` | Supabase URL |
| `SUPABASE_SERVICE_ROLE_KEY` / legacy `SUPABASE_KEY` | Szerveroldali adatbáziskliens |
| `SUPABASE_PUBLISHABLE_KEY` / legacy `SUPABASE_ANON_KEY` | Külön publikus/Auth kliens |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | Gemini |
| `JARVIS_DASHBOARD_PASSWORD` | Dashboard |
| `EMAIL_USER`, `EMAIL_PASSWORD`, `SMTP_HOST`, `SMTP_PORT`, `IMAP_HOST`, `IMAP_PORT` | E-mail és inbox |
| `EMAIL_DELIVERY_ENABLED`, `CHAT_EMAIL_ENABLED`, `AUTO_SEND_ENABLED`, `EMAIL_INBOX_MONITOR_ENABLED` | E-mail biztonsági kapcsolók |
| `SEND_MAX_PER_RUN`, `MAX_FOLLOW_UPS`, `FOLLOW_UP_DAYS`, `SEND_DELAY_SECONDS` | E-mail korlátok |
| `SUPABASE_DB_URL`, `AWS_BACKUP_ROLE_ARN`, `BACKUP_AGE_IDENTITY` | Backup workflow secret |
| `JARVIS_BACKUP_SOURCE_PROJECT_REF`, `BACKUP_AGE_RECIPIENT`, `BACKUP_AWS_REGION`, `BACKUP_S3_BUCKET`, `BACKUP_S3_KMS_KEY_ARN` | Backup workflow változók |

Az e-mail-kapcsolók alapértelmezésben kikapcsoltak. Chat-küldéshez `EMAIL_DELIVERY_ENABLED=true` és `CHAT_EMAIL_ENABLED=true`; háttérküldéshez ezen felül `AUTO_SEND_ENABLED=true`, `EMAIL_INBOX_MONITOR_ENABLED=true` és érvényes lead-hozzájárulás kell. A Codespaces és a GitHub Actions secret-tára külön van.

## 10. Tesztelés és bizonyítékok

A minőségbiztosítási rétegek: `compileall`; mockolt pytest/AppTest/Playwright; külön PostgreSQL 17 + age integrációs backup/restore round-trip CI-job; külön kontrollált live integráció; valós dashboard- és Actions-futások megfigyelése. A lokális PostgreSQL integráció bizonyítja a backup/restore kód tényleges működését, de nem bizonyítja az éles Supabase-hozzáférést vagy az S3-feltöltést.

Dátumhoz kötött bizonyítékok:

- **2026-11-23 – történeti coverage baseline:** a [45132352299 CI-futás](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45132352299) PR #9 headjén 594 sikeres, 2 kihagyott, 0 hibás tesztet és 97,70% statement coverage-et mutatott. Ez nem a jelenlegi main tesztszáma.
- **2026-11-23 – PR #13 CI:** a [45251071690 futás](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45251071690) sikeres volt compileall, CloudFormation, Playwright telepítés, unit/AppTest/browser tesztek és artifact-lépések tekintetében. Ez draft PR head; nem igazolja az Auth/RLS production integrációt.
- **2026-11-23 – production leadkutatás:** a [45252422431 workflow](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45252422431) a hiányzó `logs.action` mező miatt sikertelen volt; a `pending` audit hibája megállította a kutatás indítását. A központi hibajelentés külön fallbacket kapott a legacy logs-sémához, de ez nem helyettesíti a strukturált auditmigrációt.

Tesztbiztonsági határok:

- A normál pytest a Python-folyamaton belül tilt DNS- és kimenő socket-hívásokat; ez nem OS-szintű sandbox, nem korlátoz minden subprocess hálózatot.
- Read-only live integrációhoz `tests/test_live_integrations.py`, `live_integration` marker és `JARVIS_LIVE_INTEGRATION_TESTS=1` szükséges.
- SMTP/IMAP unit tesztek mockoltak; valós levelet nem küldenek.
- Supabase unit tesztek fake klienst használnak; production DB-t nem módosítanak.
- A `supabase/tests/audit_access_and_integrity.test.sql` pgTAP tesztet a CI külön PostgreSQL 17 adatbázisban futtatja, a két verziókezelt auditmigráció alkalmazása után; az Auth JWT-függvény lokális tesztstub, nem éles Auth-integráció.

## 11. Ismert hibák és blokkolók

### Production adatbázis

- Öt remote migráció eredeti SQL-forrása hiányzik a Gitből.
- A repo schema snapshot nem pontos production snapshot.
- A production `logs` tábla hiányzó mezői már leállították a globális leadkutatási workflow-t.
- A production táblákon RLS engedélyezett, de policy nincs; a backend service-role-ra támaszkodik.
- Nincs jóváhagyott, külön tesztadatbázis a valódi policy-k és pgTAP tesztek ellenőrzéséhez.

### RBAC és audit

- A közös dashboard-jelszó nem egyedi felhasználói identitás.
- A teljes admin/operator/reader modell nincs bekötve az üzleti adatútvonalakba.
- Nincs tenant-adatszegregáció.
- Az audit UI/hash-lánc SQL repositoryban létezik, de production migráció nem alkalmazott.
- Nincs WORM-archívum, külső hash-ankor, retention/jogi hold vagy igazolt független riasztás.
- A hash-lánc DB-tulajdonossal szemben nem megváltoztathatatlan.

### Üzemeltetés / külső kapcsolatok

- Az AWS backup stack telepítése, a GitHub backup secret-ek/változók megléte, az éles Supabase dump és az S3-feltöltés még nem igazolt; hiányzó konfigurációval a workflow most hibás állapotot jelez. A lokális backup/restore round-tripet a CI külön jobban ellenőrzi.
- A Gemini/SMTP/IMAP külső integrációk és az e-mail-kézbesítés sikeres üzemi működése nincs bizonyítva mockolt tesztekkel.
- A proaktív monitor napi workflow kódban létezik, de a sikeres éles futás külön igazolandó.

A production `posts` tábla legacy/árva objektumnak tűnik, de a repo-hivatkozás hiánya nem elegendő törléshez. Ugyanez minden ismeretlen DB-objektumra igaz.

## 12. Fejlesztési sorrend

1. Production schema-only snapshot és tételes eltérésmátrix beszerzése, adatbázis-módosítás nélkül.
2. Az öt hiányzó migráció eredeti SQL-jének beszerzése vagy a hiány bizonyítékalapú dokumentálása; találgatás tilos.
3. Titkosított backup és külön, jóváhagyott sandbox restore-próba.
4. Audit SQL, RLS és hash-lánc ellenőrzése nem éles adatbázisban.
5. Valós Auth/RBAC pozitív és negatív teszt anon/reader/operator/admin/service-role szerepekkel.
6. Dashboard és üzleti modulok JWT/RLS alapú átállítása csak a modell bizonyítása után.
7. Kontrollált Gemini-, SMTP-, IMAP- és ütemezett workflow-integrációs próbák.
8. Production bevezetés csak külön engedéllyel, ellenőrzött backup/restore és pontos migrációs diff alapján.

**Ez a dokumentum nem engedélyez** production DDL-t, adatfrissítést, GRANT/REVOKE-ot, policy-változtatást, migration ledger javítást, `supabase db push`-t, új Supabase projekt/branch létrehozását vagy AWS erőforrás telepítését.

### Dokumentáció-karbantartás

- Ez a fájl a részletes dokumentáció egyetlen forrása.
- A `README.md` csak rövid projektbemutató és belépési pont.
- Forráskód/SQL/workflow változása után az érintett fejezetet frissíteni kell.
- Teszteredmény dátummal, commit/PR SHA-val és CI-linkkel szerepelhet.
- Külső integráció csak tényleges futás és visszakereshető eredmény után jelölhető igazoltnak.
- Eltérés esetén a kód, migráció és workflow az elsődleges forrás; a dokumentumot javítani kell.
- Titok, jelszó, token, DB URL vagy személyes adat nem kerülhet bele.

---

**Állapot:** a dokumentum a 2026-11-23-i repository- és csak olvasási production-audit bizonyítékokra épül. Nem jelent production migrációs, backup-, Auth/RBAC- vagy külső integrációs jóváhagyást.


## Dokumentációs kiegészítés – 2026-11-24

A PR #13 dashboard Auth helper tesztjeinek új állapota, valamint a CI
bizonyítékok és korlátok a
[`PR13_CI_VALIDATION_2026-11-24.md`](PR13_CI_VALIDATION_2026-11-24.md)
fájlban szerepelnek. A teljes, prioritásos hiánylista és production release
gate a [`REMAINING_WORK_AND_RELEASE_GATES.md`](REMAINING_WORK_AND_RELEASE_GATES.md)
dokumentumban található.

A legutóbbi CI run `45462249173` PostgreSQL 17 integrációs jobja sikeres;
a Python/AppTest/browser tesztlépés a dokumentáció frissítésekor még futott,
ezért az új Auth helper tesztek végleges tesztszáma és coverage értéke nincs
igazolva. A korábbi `45460581824` 93.57%-os coverage értéke nem vetíthető
automatikusan az új kódra.

A jelenlegi tesztdupla a dashboard Auth helper útvonalát vizsgálja; nem
helyettesíti a valós Supabase Auth/JWT/RLS integrációt. A CI-ben futó
PostgreSQL/age backup-restore izolált lokális teszt, nem production mentés.


## 2026-11-24 friss állapot – CI és biztonsági javítások

A korábbi, még futó/megszakított CI állapotot a későbbi teljes zöld futás
felülírja: [45463032568](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45463032568)
718 passed, 3 skipped, 93.78% line coverage eredményt adott. A PostgreSQL 17
audit/RBAC pgTAP és titkosított local age backup/restore integráció sikeres.
Ez CI-bizonyíték, nem production backup vagy valós Supabase Auth-teszt.

A legutóbbi, külön read-only production ellenőrzés 2026-11-24 18:51 UTC-kor
megerősítette, hogy productionben 8 public tábla van RLS-sel, de 0 RLS policy;
az `auth.users` üres; az audit hash-chain tábla és a strukturált audit
mezők hiányoznak; a remote migration ledger öt Gitből hiányzó történeti
migrációt tartalmaz. Részletes pillanatkép:
[`PRODUCTION_REVALIDATION_2026-11-24_1851UTC.md`](PRODUCTION_REVALIDATION_2026-11-24_1851UTC.md).

A chatműveletek pending jóváhagyása most öt perc után lejár, egyszer
használható és az aktuális felhasználóhoz kötött. Az audit-admin session
refresh ellenőrzi a user ID folytonosságát. Az audit CSV export eseményei
ellenőrzött admin user-JWT kliensen keresztül íródnak, és az export-jóváhagyás
is lejáró, adminhoz kötött. Az új regressziós tesztek a korábbi zöld CI után
kerültek be; ezek végleges CI-eredménye még ellenőrzendő.

A teljes, prioritásos blokkolólista:
[`REMAINING_WORK_AND_RELEASE_GATES.md`](REMAINING_WORK_AND_RELEASE_GATES.md).

## 2026-11-24 – aktuális teljes CI és kódszintű javítások

A 2026-11-24-i teljesen zöld PR #13 baseline CI-futás:
[45467211381](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45467211381)
— 734 passed, 3 skipped, 93.67% line coverage egy korábbi commiton. Ez nem a jelenlegi PR head validációja. A PostgreSQL 17 integrációs
job a két repo-only 20261117 migrációt, az öt visszanyert történeti SQL-t,
majd az audit/hash-chain/RBAC migrációkat is sikeresen futtatta a lokális
production-shape fixture-en. Az encrypted age backup/restore körút is sikeres.

A repository további biztonsági javításai:
- audit-admin session user-ID folytonosság ellenőrzése;
- ötperces, egyszer fogyasztható, felhasználóhoz kötött chat-jóváhagyás;
- user-JWT alapú, lejáró és adminhoz kötött audit CSV export;
- admin-only rendszerdiagnosztika user-JWT-vel, service-role fallback nélkül;
- production-compatible settings identity és posts tábla a schema bootstrapban;
- coverage és UI screenshot artifact retention 14/7 napra korlátozva.

A remote ledgerből visszanyert öt migrációs forrás repositoryban van.
A teljes production migration drift azonban még nem zárt: a két 20261117
repo-verzió hiányzik a remote ledgerből, az audit/RBAC migrációk pedig még
nincsenek productionben alkalmazva.

Friss production read-only leltár:
[PRODUCTION_REVALIDATION_2026-11-24_1851UTC.md](PRODUCTION_REVALIDATION_2026-11-24_1851UTC.md).
Prioritásos hátralévő feladatok:
[REMAINING_WORK_AND_RELEASE_GATES.md](REMAINING_WORK_AND_RELEASE_GATES.md).


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
