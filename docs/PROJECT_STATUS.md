# JARVIS – aktuális projektállapot

**Utolsó ellenőrzött dokumentációs állapot:** 2026-11-20  
**Repository:** `tamaszsolt2005-hub/jarvis-core` · **Branch:** `main`  
**Supabase-projekt:** Jarvis · `kiutreccucbegskxowek` · EU West

## Hogyan olvasd ezt a dokumentumot?

Ez a fájl a változó projektállapot egyetlen irányadó helye. Különböztesd meg:
- **Implementálva:** a funkció megtalálható a repository kódjában.
- **Automatikusan tesztelt:** a hozzá tartozó teszt sikeresen lefutott.
- **Integrációsan igazolt:** valós külső szolgáltatással is ellenőrizték.
- **Üzemszerűen igazolt:** a tényleges alkalmazás vagy ütemezett folyamat működését is ellenőrizték.

Egy korábbi teszt vagy környezeti változó megléte nem bizonyítja a jelenlegi éles működést.

## Implementált fő funkciók

- Magyar nyelvű Streamlit chat, Gemini-integráció, beszélgetési előzmény és adaptív kimeneti tokenkeret.
- Kérdésfüggő Supabase-adatlekérés és naplózás; a chatkérés/válasz tartalma nem kerül a technikai eseménynaplóba.
- Forrásalapú globális céges leadkutatás, célpiacváltás és kutatás előnézettel/jóváhagyással.
- Weboldal-audit biztonságos HTTP-lekéréssel, leadprioritás és üzleti/stratégiai összesítés.
- Explicit utasításra működő hosszú távú memória és üzleti tanulómemória.
- Jóváhagyásos feladat-létrehozás, -módosítás és -lezárás.
- Chat-analitika, determinisztikus vezetői analitikai jelentés és napi briefing.
- Chatből e-mail-tervezet, előnézet és külön jóváhagyás utáni SMTP-küldési kísérlet.
- Külön, hozzájárulás-ellenőrzéses háttér-e-mail-küldő és IMAP-alapú inbox-monitor kód.

A funkciók részletes belső felépítését a [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md) írja le.

## Ellenőrzött tények – 2026-11-20

### Helyi tesztek

A felhasználó korábban az alábbi parancsokat futtatta sikeresen:

```bash
python -m compileall -q .
python -m pytest -q
```

Ellenőrzött eredmény: **154 passed, 0 failed**. Ez az eredmény az e-mail-fejlesztés előtti kódállapotra vonatkozott. Az e-mail-funkciók később bekerült tesztjeinek teljes futtatása ezen a dátumon még nem volt igazolva. Ne állítsd, hogy ez a jelenlegi teljes tesztállapot.

### Codespaces e-mail-környezeti változók

A Codespaces konténer újraépítése után a következő változók jelenlétét ellenőrizték; mind a négy beállítottnak látszott:

- `EMAIL_USER`
- `EMAIL_PASSWORD`
- `EMAIL_DELIVERY_ENABLED`
- `CHAT_EMAIL_ENABLED`

A változók értékei nem kerültek a dokumentációba. A jelenlétük nem igazolja, hogy az SMTP/IMAP-kapcsolat működik, hogy a küldési kapcsolók értéke `true`, vagy hogy levél ténylegesen kézbesült.

### Közvetlen Supabase-ellenőrzés

2026-11-20-án a megfelelő Jarvis Supabase-projekten csak olvasó SQL-lekérdezéseket futtattak.

- Projektállapot az ellenőrzéskor: `ACTIVE_HEALTHY`.
- Projekt létrehozása: 2026-11-13 16:02:24 UTC.
- A `public.logs` táblában 23 rekord volt.
- Megfigyelt első naplóesemény: 2026-11-13 18:33:44 UTC.
- Megfigyelt utolsó naplóesemény: 2026-11-20 17:54:37 UTC.
- A chat modulban 2 `chat_request` és 2 `chat_response` esemény volt.
- A vizsgált mintában nem volt `error` vagy `warning` szintű rekord.

Ez egy adott időpontban végzett ellenőrzés, nem folyamatos rendelkezésreállási garancia. A projekt 2026-11-13-i létrehozása előtti naplóhiány nem bizonyít naplóvesztést.

### Supabase jogosultságok – korábbi ellenőrzés

A 2026-11-20-i dokumentációban rögzített biztonsági ellenőrzés szerint RLS aktív volt az alkalmazástáblákon, és az `anon` / `authenticated` közvetlen táblajogosultságai vissza voltak vonva. A `service_role` szerveroldali hozzáférése megmaradt. A `supabase_admin` default ACL módosítási kísérlete permission errorral meghiúsult; ezt nem szabad megoldottként feltüntetni.

## Hibakezelési fejlesztés – 2026-11-20\n\n**Kódban implementálva:**\n- Új `jarvis_errors.py`: központi hibajelentés UTC időbélyeggel, modullal, művelettel, kivételtípussal és warning/error/critical szintekkel.\n- A naplóüzenetek szűrik a gyakori jelszó-, API-kulcs-, token-, Bearer- és URL-hitelesítő adat formákat, továbbá a környezeti változók ismert titokértékeit.\n- A `jarvis_common.log_event()` már szűri a meglévő alkalmazásnapló üzeneteit; a `get_setting()` hibája a központi jelentőn keresztül warningként jelenthető.\n- Ha a Supabase naplózás maga hibázik, helyi Python logger a tartalék; nincs rekurzív adatbázis-naplózási próbálkozás.\n- Új tesztek készültek a titokszűrésre, súlyossági szintre, metaadatokra és naplózási backend hibájára.\n\n**Még nem igazolt:** a módosítások utáni tesztfuttatás és GitHub Actions CI-eredmény. A teljes repository minden kivételágának központi hibajelentőre átvezetése nem része ennek a részleges bekötésnek; további modulonkénti audit szükséges. Az alkalmazás minden hibája így még nem garantáltan központilag naplózott.\n\n## E-mail állapot

**Implementálva a kódban:**
- Chatből e-mail-tervezet készítése, pontos címzett, tárgy és teljes szöveg előnézete.
- Küldés csak a külön `Jóváhagyom` üzenet után, ha `EMAIL_DELIVERY_ENABLED=true` és `CHAT_EMAIL_ENABLED=true`.
- Háttérküldés és utánkövetés külön kapcsolókkal, hozzájárulás- és leiratkozás-ellenőrzéssel.
- IMAP inbox-ellenőrzés válasz és leiratkozás felismerésére.

**Még nem igazolt:**
- Valós SMTP-kapcsolat és tényleges kézbesítés.
- Valós IMAP-kapcsolat és bejövő válasz feldolgozása.
- E-mail-funkciók teljes, friss tesztcsomagjának felhasználói futtatása.
- A tényleges címzettkorlátozás és kontrollált próbaküldés biztonságos ellenőrzése.

A háttérküldés alapértelmezetten nem tekinthető aktívnak. Ehhez mindhárom `EMAIL_DELIVERY_ENABLED`, `AUTO_SEND_ENABLED` és `EMAIL_INBOX_MONITOR_ENABLED` kapcsolónak külön engedélyezettnek kell lennie; a chatküldéshez a `CHAT_EMAIL_ENABLED` is szükséges.

## Automatizálások a repositoryban

A workflow-fájlokban definiált UTC ütemezések:

| Workflow | Ütemezés | Feladat |
|---|---:|---|
| `.github/workflows/global-lead-research.yml` | naponta 08:00 UTC | globális céges leadkutatás |
| `.github/workflows/daily-briefing.yml` | naponta 08:30 UTC | vezetői briefing és artifact |
| `.github/workflows/email-automation.yml` | naponta 09:15 UTC | inbox-ellenőrzés, majd feltételes háttérküldés |
| `.github/workflows/ci.yml` | push, pull request, kézi indítás | compileall és pytest |

A `jarvis.yml` és `jarvis-cron.yml` régi, letiltott no-op workflow-k; nem szabad őket aktív automatizálásként leírni. A workflow-fájl létezése nem bizonyítja, hogy egy futás sikeres volt vagy minden GitHub Actions secret konfigurálva van.

## Nyitott ellenőrzések és ismert eltérések

1. Futtasd le a jelenlegi teljes tesztcsomagot Codespaces-ben, és rögzítsd az új, dátumozott eredményt.\n2. Ellenőrizd a `jarvis_errors.py`-hoz hozzáadott tesztek és a teljes CI futás eredményét.
2. Ellenőrizd a Gemini- és dashboard-folyamatot valós, kontrollált környezetben.
3. Ellenőrizd a legutóbbi GitHub Actions futásokat és artifactokat.
4. Végezz kontrollált SMTP/IMAP végponttól végpontig tesztet, valódi címzettnek küldés előtt címzettkorlátozással.
5. **Supabase `posts` tábla – ellenőrizve 2026-11-20:** a megfelelő Jarvis-projekt `public` sémájában nyolc tábla van. A `posts` tábla létezik, 0 rekorddal, RLS bekapcsolva; oszlopai: `id`, `content`, `scheduled_for`, `status`, `created_at`. A repository `supabase/schema.sql` és a kódkeresés nem tartalmaz `posts` definíciót vagy használatot. Ez jelenleg árva/legacy táblának látszik. Nem töröltük és nem módosítottuk; külön döntés és mentés nélkül maradjon érintetlen.
6. **Proaktív monitor – ellenőrizve:** a `proactive_monitor.py` `run_proactive_monitor()` függvénye implementált: legfeljebb 2000 leadet és 1000 feladatot vizsgál, előző pillanatképpel hasonlítja össze őket, jelzi az új/módosult rekordokat, lejárt/mai/sürgős feladatokat, majd a `jarvis_proactive_state` táblába ment pillanatképet. A leadeket és feladatokat nem módosítja. Repository-keresésben és aktív workflow-kban nincs hívása, ezért nincs bekötve és nincs ütemezve. A dashboard `_proactive_signals()` függvénye külön, pillanatnyi állapotjelzés; nem ez a változásfigyelő. Állapot: implementált, de automatikus futás nem igazolt.
7. **Elavult dashboard-megjegyzés – javítva:** a `dashboard.py` fejlécének docstringje korábban azt állította, hogy az alkalmazás soha nem küld e-mailt. A kód valójában támogat chatből e-mail-tervezetet, majd külön jóváhagyás és `EMAIL_DELIVERY_ENABLED` + `CHAT_EMAIL_ENABLED` kapcsolók mellett SMTP-küldési kísérletet. A docstringet ehhez igazítottuk. Ez nem bizonyítja a tényleges kézbesítést; az SMTP-integráció továbbra is külön ellenőrzendő.

## Dokumentációs szabály

- README: felhasználói áttekintés és telepítés.
- Ez a fájl: dátumozott állapot, tesztek, külső ellenőrzések és nyitott feladatok.
- TECHNICAL_DOCUMENTATION: tartós architektúra, modulok, adatfolyamok és biztonsági szabályok.

Ne másold át a dátumozott teszt- vagy szolgáltatásállapotot a műszaki dokumentációba. Minden új állapotállításhoz dátum és ellenőrzési forrás szükséges.


## Hibakezelés és tesztelési bővítés – 2026-11-20

**Kódban implementálva:**
- A meglévő `jarvis_errors.py` központi jelentőjét megtartottuk; nem készült párhuzamos hibakezelő.
- Az `email_sender.py` egyedi küldési hibái már a központi `report_error()` függvényt használják. Ha a küldés utáni státuszfrissítés is hibázik, az kritikus hibaként kerül jelentésre; a küldő továbbra sem próbál automatikusan vakon újraküldeni.
- Az `email_sender.run()` váratlan pipeline-hibát központilag jelent, majd újra dobja, hogy a GitHub Actions futás hibásként látszódjon.
- Az `email_inbox.run()` ugyanígy központilag jelent és újradobja a váratlan hibát. A hiba nem lesz elrejtve sikeres futásként.
- Javítva az e-mailküldés letiltásakor naplózott figyelmeztetés szintje: a korábban használt `warn` helyett a támogatott `warning` érték szerepel.

**Új tesztfájl:** `tests/test_error_resilience.py` – mockolt tesztek a naplóüzenetek titokszűrésére, a Supabase-naplózási hiba helyi fallbackjére, a kikapcsolt SMTP fail-closed működésére, az inbox- és sender-folyamat hibajelentésére, a hibák továbbdobására, hibás UID-re és hiányzó Supabase-konfigurációra.

**Meglévő tesztek, amelyeket megtartottunk:** központi hibajelentés, közös Gemini/config segédek, task parser/végrehajtás, email workflow/consent/opt-out, SSRF-védett HTTP és lead scoring. A meglévő teszteket nem töröltük.

**Tesztfuttatás:** ebben a munkamenetben nem sikerült helyi futtatást végezni: a futtatókörnyezet nem tudta elérni a GitHubot, így a Codespaces munkakönyvtár és a projekt függőségei nem voltak elérhetők. A CI futás eredményét sem sikerült lekérdezni. Ezért nincs igazolt új passed/failed tesztszám; a commitok megléte nem bizonyít tesztsikert.

**Nyitott tesztelési területek:** a Streamlit dashboard teljes jóváhagyási/jogosultsági útvonala, valós vagy elkülönített Supabase tranzakciós viselkedés, párhuzamos e-mailküldés/atomikus deduplikáció, valamint SMTP/IMAP végponttól végpontig integráció. Az új tesztek mockoltak; nem végeznek valódi küldést vagy éles adatbázis-módosítást.

## Központi műveleti napló és audit – 2026-11-20

**Meglévő alap ellenőrizve:**
- A repository már használja a public.logs táblát; a korábbi technikai naplórekordok megmaradnak.
- A jarvis_common.audit_event() és a supabase/schema.sql strukturált auditmezői már a mostani munka előtt is léteztek: operation_id, action, status, result, error, approved, recipient, subject, delivery_id.
- Az SQL-séma ezeket ADD COLUMN IF NOT EXISTS formában, indexekkel definiálja. A mostani módosításhoz nem készült új tábla, és nem kellett adatbázis-migrációt futtatni. Ez a repository-sémára vonatkozó állítás; élő Supabase-migráció végrehajtása ebben a munkában nem történt.

**Most bekötött működés:**
- task_actions.py: feladat create/update/close művelet előtt audit pending rekord; sikernél success, blokkolt/ütköző állapotnál blocked. Ha a kezdő auditrekord nem menthető, a feladatművelet nem fut le.
- dashboard.py: jóváhagyott chat e-mail előtt pending audit; az e-mail küldési kísérlet eredménye success vagy failed eseményt kap. A kezdő audit nem írható -> SMTP nem indul. Címzett, tárgy, jóváhagyási állapot és SMTP Message-ID tárolható; a levéltörzs nem kerül az auditba.
- email_sender.py: háttér e-mailküldés előtt pending, SMTP-átvétel után success; SMTP előtt fellépő hibánál failed, SMTP-átvétel utáni auditbizonytalanságnál unknown esemény. Az audit kezdőrekordjának sikertelensége megakadályozza az SMTP-küldést.
- email_inbox.py: a bejövő válasz és leiratkozás auditálása; auditírási hiba esetén az IMAP UID checkpoint nem lép tovább, így a feldolgozás nem tűnik sikeresnek.
- global_lead_research.py: a kutatási futás eredménye darabszámokkal és piaci hatókörrel kerül naplózásra; leadek személyes adatai nem kerülnek az audit eredménymezőjébe.
- jarvis_common.get_audit_events(): szűrhető, időrendben (legújabb elöl) visszaadott strukturált auditrekordok; limit 1–1000. A régi, strukturálatlan logbejegyzések továbbra is a meglévő log/analitika útvonalon érhetők el.
- A strukturált eredmény natív JSON értékként kerül a jsonb mezőbe. Ha az SMTP átvette a levelet, de a záró auditbejegyzés nem menthető, a chat ezt külön jelzi, és nem javasol vak újraküldést. A szabad szöveges eredményértékek is titokszűrést kapnak. A dashboard logkontextusa audit-metaadatokat kér le, de nem kéri le a címzettet és a tárgyat a Gemini kontextusába.

**Új tesztek:** tests/test_audit_logging.py – auditmezők, UUID, titokszűrés, JSON eredmény, sikertelen auditmentés, időrendi lekérdezés és szűrők. A tests/test_task_actions.py új esete ellenőrzi, hogy audit-adatbázishiba esetén a feladat létrehozása nem történik meg.

**Tesztállapot:** a felhasználó által közölt 161 passed in 6.00s eredmény a korábbi hibakezelési/tesztelési módosítások utáni állapotot igazolja, de a jelen auditfejlesztés commitjai előtti futás volt. A most hozzáadott audit teszteket és az összesített csomagot ebben a munkamenetben még nem futtattuk; ezért friss passed/failed szám nincs igazolva.

**Nyitott pontok:**
- A supabase/schema.sql migráció tényleges futtatása az élő Supabase-projekten nincs igazolva. A repository-séma tartalmazza a szükséges oszlopokat, de az élő adatbázis állapotát külön kell ellenőrizni.
- Az audit append-only alkalmazásszintű minta; adatbázis-szintű immutabilitás, adminisztrátori módosítások elleni védelem és retention policy nincs kialakítva.
- A get_audit_events() lekérdezési segéd elkészült; külön, lapozható admin audit UI még nincs.
- A leadkutatási és bejövő levél audit utólagos állapotot rögzít. A külső szolgáltatás és adatbázis közötti tranzakciós atomikusság nem garantált.

 
## Adatbázis-mentés és visszaállítás – 2026-11-20

**Éles Supabase-projekt olvasási ellenőrzése (Jarvis: `kiutreccucbegskxowek`):**
- Projektállapot: `ACTIVE_HEALTHY`; PostgreSQL 17.11.0.019; EU West.
- A `public` sémában 8 tábla: `leads` (11 sor), `posts` (0), `logs` (28), `settings` (1), `tasks` (0), `email_drafts` (0), `jarvis_memory` (0), `jarvis_proactive_state` (1). Mindegyiken RLS aktív.
- A `posts` legacy táblát is tartalmazza a teljes public dump, a repository-sémától függetlenül.
- A `storage.buckets` lekérdezés üres volt. A projekt bővítménykatalógusa több PostgreSQL-kiterjesztést tartalmaz; célprojektben a szükségeseket külön ellenőrizni kell.
- Kizárólag olvasási lekérdezések futottak; éles adat nem módosult.

**Előkészített repository-elemek:**
- `scripts/supabase_backup.py`: Supabase CLI public schema + data dump, UTC időbélyeg és UUID, SHA-256 manifest, age titkosítás.
- `.github/workflows/database-backup.yml`: napi 02:15 UTC és kézi indítás; hiányzó külső konfiguráció esetén skip; sikeres konfigurációval titkosított fájl feltöltése S3 prefixbe.
- Visszaállítás: az éles projektazonosító kódszinten tiltott; csak külön allowlistelt, DB URL-lel egyező, üres sandbox célba engedélyezett; archívum- és hash-ellenőrzés; egyetlen SQL tranzakció.
- `tests/test_supabase_backup.py`: mockolt biztonsági és archívumellenőrzési egységtesztek.
- `.gitignore`: privát mentési könyvtárak és titkosított archívumok kizárva.

**Külső konfiguráció még szükséges:**
- GitHub Actions Secrets: `SUPABASE_DB_URL`, `BACKUP_AWS_ACCESS_KEY_ID`, `BACKUP_AWS_SECRET_ACCESS_KEY`.
- GitHub Actions Variables: `JARVIS_BACKUP_SOURCE_PROJECT_REF`, `BACKUP_AGE_RECIPIENT`, `BACKUP_AWS_REGION`, `BACKUP_S3_BUCKET`.
- Privát S3 bucket, korlátozott IAM, versioning és 30 napos lifecycle szabály.
- Age privát kulcs elkülönített, offline tárolása.
- Külön sandbox Supabase-projekt és integrációs visszaállítási próba; projektet költség/jóváhagyás nélkül nem hoztunk létre.

**Lefedettségi korlát:** a logikai mentés a teljes `public` sémát és adatait fedi. Nem tartalmazza a Supabase kezelt `auth`, `storage`, `realtime` sémákat, Storage bináris fájlokat, projektbeállításokat, API-kulcsokat, Vault root kulcsot vagy custom role jelszavakat. A platform napi backup/PITR hozzáférhetősége csomagfüggő, a csomagot és beállítást nem ellenőriztük.

**Állapot:** kód és workflow előkészítve; tényleges mentés, S3 feltöltés és sandbox visszaállítás még nem történt. Az éles DB változatlan maradt. A hozzá tartozó egységtesztek friss futása még nincs igazolva.


## Biztonságos adatbázis-mentés és visszaállítás – 2026-11-20

**Kódban előkészítve:**
- `scripts/supabase_backup.py`: a rögzített JARVIS Supabase projektből a teljes `public` séma és adat logikai exportja, UUID-alapú azonosító, UTC időbélyeg, SHA-256 manifest, age titkosítás.
- A DB-jelszó nem kerül parancssori URL-be; a script privát, 0600 jogosultságú PGPASSFILE/folyamatkörnyezet használatára készült.
- `.github/workflows/database-backup.yml`: napi 02:15 UTC és kézi indítás; hiányos konfiguráció esetén kihagyja a futást. Az AWS-feltöltés GitHub OIDC rövid életű role-hitelesítéssel történik.
- A visszaállítás explicit `--confirm-restore` kapcsolót, külön allowlistelt nem éles projektazonosítót, URL/ref egyezést, age kulcsot és üres `public` sémát követel. Az éles JARVIS projektazonosító kódszinten tiltott.
- A helyi backup könyvtár és titkosított archívumok Git-ignore alatt vannak.

**Élő adatbázis-ellenőrzés 2026-11-20:** a megfelelő Jarvis projekten csak olvasási ellenőrzés történt. A `public` sémában nyolc tábla volt: `leads` (11), `posts` (0), `logs` (28), `settings` (1), `tasks` (0), `email_drafts` (0), `jarvis_memory` (0), `jarvis_proactive_state` (1). A teljes public dump a legacy `posts` táblát is tartalmazza. Az élő séma eltér a repository `supabase/schema.sql` fájljától, ezért a mentés nem abból épül újra.

**Még nem konfigurált / nem igazolt:**
- GitHub Actions `SUPABASE_DB_URL` és `AWS_BACKUP_ROLE_ARN` secret, valamint a projektref, age recipient, AWS régió és privát bucket változók.
- AWS IAM OIDC trust policy, privát S3 bucket, SSE-KMS, versioning és lifecycle retention.
- Az age privát visszafejtő kulcs biztonságos, offline megőrzése.
- Sikeres éles mentési futás, S3 feltöltés és izolált Supabase sandbox restore próba.

A Supabase Auth és Storage platform-sémák, Storage fájlbinárisok, platformtitkok és külső szolgáltatások nem részei a public sémás logikai mentésnek; ezekhez külön platform backup/PITR és Storage export kell. A feladat során az éles Supabase-adatbázist nem módosítottuk, visszaállítást nem futtattunk.

**Tesztállapot:** a korábban jelentett `161 passed in 3.05s` futás a mentési fejlesztés előtti állapotot igazolja. Az új backup tesztek után friss teljes tesztfuttatás még nem áll rendelkezésre; nem állítunk friss sikeres teszteredményt.
