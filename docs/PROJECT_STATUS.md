# JARVIS projektállapot

**Utolsó dokumentációs frissítés:** 2026-11-20  
**Repository:** `tamaszsolt2005-hub/jarvis-core` · **Branch:** `main`  
**Supabase-projekt:** `Jarvis` (`kiutreccucbegskxowek`, EU West)

Ez a dokumentum a repositoryban található kód, a felhasználó által futtatott tesztek és a 2026-11-20-i közvetlen Supabase-ellenőrzések alapján különíti el a kész, tesztelt és még élesben ellenőrizendő részeket. A „kész” kódfunkciót jelent, nem automatikusan teljes üzemi validációt.

## Elkészült funkciók a kódbázisban

### Chat és AI
- Streamlit-alapú, magyar nyelvű, chat-first B2B üzleti intelligencia felület; prémium sötét téma és állapotjelzések.
- Központi Gemini-kliens és modellkonfiguráció; alapértelmezett modell a repository leírása szerint `gemini-3.8-flash`; a modell környezeti beállítással felülírható.
- Átmeneti Gemini túlterhelés kezelése korlátozott újrapróbálkozással/fallback logikával.
- A chatkérések és a sikeresen elkészült AI-válaszok eseménytípusa naplózódik (`chat_request`, `chat_response`); a kérdés- és válaszszöveg nem kerül a rendszernaplóba.
- Hosszabb vezetői jelentésekhez teljes, lezárt válaszra és az adathiányok jelzésére vonatkozó promptszabályok.
- Adaptív válaszhossz-szabályozás: az `estimate_response_tokens()` a kérdés megfogalmazása, hossza és összetettségi jelzései alapján helyben választ kimeneti tokenkeretet. A rövid kérdések jellemzően 512, az átlagosak 768–1024, a több szempontú kérdések 2048, az explicit részletes elemzések 3072–4096, a kifejezetten rövid választ kérők 384 tokent kapnak. A heurisztika nem indít külön AI-hívást; a `generate_text()` a megadott keretet alkalmazza (technikai plafon: 8192). A keret felső korlát, nem célérték vagy garantált tokenfelhasználás.
- Adaptív válaszhossz: helyi heurisztika becsüli a kérdés összetettségét extra AI-hívás nélkül, majd 384–4096 közötti kimeneti tokenkeretet állít be; a központi Gemini-kliens 8192 tokenes technikai plafont tart fenn.

### Leadkutatás és üzleti elemzés
- Google Search grounding alapú, globális, forrásokkal alátámasztott céges leadkutatás.
- Célpiac és keresési brief chatből megadható; a célpiacváltás és a leadkutatás jóváhagyáshoz kötött.
- A leadkutatási rekordok céges adatokat tárolnak; a kutatás önmagában nem ad kapcsolatfelvételi engedélyt.
- Külön weboldal-információs pontszám és AI/automatizálási üzleti illeszkedési becslés.
- Kutatási prioritás és iparági/ország szerinti stratégiai összesítés; a pontszámok nem vásárlási szándékot vagy fizetőképességet mérnek.
- Weboldal-auditor legfeljebb 30 nyilvános weboldal vizsgálatára, biztonságos HTTP-lekérési segéddel.
- Üzleti tanulómemória: a kifejezetten rögzített döntések, tapasztalatok és tanulságok későbbi elemzésekben felhasználhatók.

### CRM, memória és proaktív működés
- Leadek, feladatok, e-mail-tervezetek és naplók kérdésfüggő, olvasásközpontú lekérdezése.
- JARVIS hosszú távú memóriája kizárólag explicit felhasználói utasításra ment/módosít; titkok és érzékeny személyes adatok tiltottak.
- Strukturált feladat létrehozása, módosítása és lezárása előnézet + külön jóváhagyás után.
- Proaktív változásfigyelés a lead- és feladatállapotokhoz, technikai pillanatkép-táblával.
- Napi vezetői jelentés és napi globális leadkutatás GitHub Actions workflow-kban; a jelentés artifactként érhető el.

### Analitika és naplózás
- A `public.logs` rekordjaiból 7/30/90/365 napos aktivitási összesítés készül, modulbontással, chatkérés/válaszesemény-számmal, hibákkal és figyelmeztetésekkel.
- A dashboard analitikai felülete valódi naplóadatokból készíti a KPI-kat és grafikonokat.
- A chat-analitika nem teszi az AI kontextusába a nyers naplóüzeneteket.
- A chatfolyamat naplózása külön eseménytípusokat használ a kérésekhez, válaszokhoz és hibákhoz; az analitika a sikeres, hibás és befejezetlen kéréseket külön kezeli. A régebbi, korrelációs azonosító nélküli naplóbejegyzések nem kezelhetők bizonyítottan összetartozó kérés-válasz párként.
- **Új pontosítás:** a jelentés külön megjeleníti a Supabase-projekt létrehozási dátumát és a naplóban ténylegesen megfigyelt első/utolsó esemény időpontját. A projekt létrehozása előtti időszak naplóhiányát nem minősíti automatikusan adatvesztésnek.
- A Jarvis Supabase-projekt létrehozási ideje a projekt metaadata alapján: **2026-11-13 16:02:24 UTC**. Ez projektmetaadat, nem a naplózás indulási ideje.
- **Vezetői analitikai jelentés:** a kifejezetten kért analitikai jelentéseket a rendszer most már determinisztikusan, közvetlenül a naplórekordokból állítja elő; ezeknél a Gemini nem írhatja felül a számokat vagy a projektmetaadatot. A riport 30 napos naptári ablakot, 7 napos összehasonlítást, modulmegoszlást, hibákat/figyelmeztetéseket, külön projekt-létrehozási és tényleges naplózási időszakot, valamint adatlefedettségi korlátot mutat. A naplóhiányt nem nevezi bizonyított modulleállásnak.
- A projekt létrehozási dátuma ismert, ezért annak `system_info` táblába történő utólagos rögzítése nem szükséges; a dátum jelenleg ellenőrzött projektmetaadatból származik.

### E-mailküldés és utánkövetés
- Chatből indított levél: a JARVIS megköveteli a felhasználó által pontosan megadott e-mail-címet, előnézetben megmutatja a címzettet, tárgyat és teljes szöveget, majd csak a külön „Jóváhagyom” üzenet után próbál küldeni.
- Chatküldéshez a szerveroldali `EMAIL_DELIVERY_ENABLED=true` és `CHAT_EMAIL_ENABLED=true` kapcsoló is szükséges. Mindkettő alapértelmezetten hamis.
- Háttérküldés: első kapcsolatfelvétel és legfeljebb két utánkövető levél kezelhető külön üzenetenkénti jóváhagyás nélkül, de csak `consent_basis=consent`, `approved_to_contact=true`, időbélyeggel igazolt `consent_confirmed_at`, érvényes e-mail-cím és `opted_out=false` esetén.
- Alapértelmezett utánkövetési várakozás 5 nap; maximum 2 utánkövető levél; futásonként legfeljebb 3 levél; küldések között 30 másodperc.
- Az `email_inbox.py` IMAP-on ellenőrzi a legutóbbi 200 bejövő üzenetet. Válasz esetén `status=replied`, leiratkozás esetén `opted_out=true` és `status=opted_out`; mindkettő törli a következő utánkövetés időpontját.
- A háttérküldő csak akkor fut, ha az SMTP, az automatikus küldés és az IMAP-figyelés kapcsolója is aktív. A GitHub Actions workflow előbb az inboxot ellenőrzi, majd az első leveleket és esedékes utánkövetéseket küldi.
- Új Supabase-tábla vagy jogosultságmódosítás nem szükséges; a meglévő `leads` mezőket használja.
- A kód és az egységtesztek bekerültek a repositoryba, de a friss e-mailteszt-csomag felhasználói futtatása, az SMTP/IMAP éles konfigurációja és a teljes végponttól végpontig ellenőrzés még hátravan.
- A tényleges küldés nincs bekapcsolva automatikusan. A `EMAIL_DELIVERY_ENABLED`, `AUTO_SEND_ENABLED`, `EMAIL_INBOX_MONITOR_ENABLED` és (chatküldéshez) `CHAT_EMAIL_ENABLED` kapcsolók szerveroldali konfigurációt igényelnek.

## Ellenőrzött állapot – 2026-11-20

### Automatizált helyi tesztek

A felhasználó Codespaces környezetében a legutóbbi adaptív válaszhossz-módosítások letöltése után az alábbi parancsok futottak le:

```bash
python -m compileall -q .
python -m pytest -q
```

Legutóbbi felhasználó által visszaigazolt eredmény: **154 passed, 0 failed** (2026-11-20). Ez a teljes helyi tesztcsomag eredménye az adaptív válaszhossz-szabályozást is tartalmazó kódállapoton. A tesztek a kód szerződéses és egységszintű működését ellenőrzik; nem helyettesítik a külső szolgáltatásokkal végzett éles végponttól végpontig tesztet.

### Közvetlen Supabase-ellenőrzés
2026-11-20-án a megfelelő Jarvis projektben kizárólag olvasó SQL-lekérdezések futottak. Az adatbázis nem módosult.

- Projekt: `kiutreccucbegskxowek`, állapot: `ACTIVE_HEALTHY`, régió: `eu-west-1`.
- Projekt létrehozása: `2026-11-13T16:02:24.276230Z`.
- A `public.logs` oszlopai: `id`, `module`, `message`, `created_at`, `level`.
- Ellenőrzéskor 23 naplórekord volt.
- Első naplóesemény: `2026-11-13 18:33:44.635249 UTC`.
- Legutolsó naplóesemény: `2026-11-20 17:54:37.793367 UTC`.
- 2026-11-13 előtti naplórekord nem volt.
- A chat modulban 2 `chat_request` és 2 `chat_response` esemény volt; a korábban hiányzónak tűnő második válasz 17:54:37 UTC-kor rögzült.
- A 23 vizsgált rekord mind `info` szintű volt; a mintában nem volt `error` vagy `warning`.

**Értelmezési korlát:** a projekt csak 2026-11-13-án jött létre, ezért az azt megelőző 30 napos részre nem lehetett ebből a projektből naplóadat. Ez nem bizonyít automatikus törlést vagy naplóretenciós hibát. A naplóban rögzített hiba hiánya nem bizonyítja önmagában minden üzleti művelet sikerességét.

### Supabase jogosultsági és adatvédelmi állapot
A korábbi, külön ellenőrzött Jarvis adatbázis-biztonsági beállítások:
- RLS aktív a nyolc alkalmazástáblán: `email_drafts`, `jarvis_memory`, `jarvis_proactive_state`, `leads`, `logs`, `posts`, `settings`, `tasks`.
- Nincs RLS policy; az `anon` és `authenticated` táblajogosultságai vissza vannak vonva.
- A `service_role` hozzáférése megmaradt, és csak szerveroldali titokként használható.
- A `postgres` default ACL új public táblák/szekvenciák esetén nem ad automatikus hozzáférést az `anon`/`authenticated` szerepköröknek.
- A `supabase_admin` default ACL módosítási kísérlete permission errorral meghiúsult; ezt nem tekintjük megoldottnak, és nem történt jogosultsággyengítés.

## Konfiguráció és telepítés

A Codespaces/Streamlit futtatási környezetben szükséges titkok:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` (kizárólag szerveroldali secret)
- `GEMINI_API_KEY`
- `JARVIS_DASHBOARD_PASSWORD`

A napi GitHub Actions workflow-k külön GitHub Actions Secrets konfigurációt igényelnek; a Codespaces Secrets nem öröklődik automatikusan az Actions környezetébe. A titkokat soha ne commitold vagy küldd el chatben.

Indítás Codespaces-ben:
```bash
python -m pip install -r requirements.txt
streamlit run dashboard.py --server.port 8501
```

## Még ellenőrizendő / nyitott feladatok

1. A determinisztikus 30 napos vezetői analitikai jelentés új tesztjeinek helyi futtatása (`python -m pytest -q tests/test_jarvis_analytics.py`), majd a teljes tesztcsomagé.
2. Új analitikai riport megnyitása a Streamlit felületen, és ellenőrzése, hogy a projekt létrehozási dátuma, valamint az első/utolsó naplóesemény külön látszik.
3. A GitHub Actions workflow-k legutóbbi futásának ellenőrzése és az artifactok áttekintése.
4. A Gemini- és teljes dashboard-folyamat valós, titkokkal végzett végponttól végpontig tesztje.
5. A Supabase `supabase_admin` default ACL kérdésének külön vizsgálata, ha a jövőben szükségessé válik; jelenleg nem blokkolja a meglévő szerveroldali működést.

## Tudatosan nem bekapcsolt funkciók

- Automatikus e-mail-küldés.
- Leadek automatikus kapcsolatfelvételi engedélyezése.
- Nyers chatkérések és AI-válaszok tartalmának naplózása.
- Anonim vagy bejelentkezett böngészői szerepkörök közvetlen hozzáférése az alkalmazástáblákhoz.
