# JARVIS – műszaki dokumentáció és AI-kontekstus

**Felülvizsgálat:** 2026-11-20  
**Repository:** `tamaszsolt2005-hub/jarvis-core` · **fő ág:** `main`

## 0. Hogyan használja ezt a dokumentumot egy AI-asszisztens?

Ez a fájl a JARVIS tartós műszaki kontextusa. A kód változhat; konkrét működésre vonatkozó kérdésnél mindig ellenőrizd az aktuális forráskódot.

### Források elsőbbségi sorrendje

1. **Aktuális forráskód és SQL-séma:** a tényleges implementáció hiteles forrása.
2. **GitHub Actions workflow-k:** az ütemezett és CI-folyamatok tényleges definíciója.
3. **[PROJECT_STATUS.md](PROJECT_STATUS.md):** dátumozott teszteredmények, külső ellenőrzések és nyitott feladatok.
4. **Ez a dokumentum:** a tartós architektúra és a modulok értelmezése.
5. **[README.md](../README.md):** felhasználói áttekintés és indítás.

Ha a dokumentum és a kód eltér, ne találgass: jelezd az eltérést, ellenőrizd a forrást, és csak bizonyíték alapján javítsd a leírást.

### Bizonyossági címkék

- **Kódban implementálva:** a funkció forráskódja létezik.
- **Workflow-val ütemezve:** egy aktív workflow hivatkozik rá.
- **Automatikusan tesztelve:** az adott teszt igazoltan lefutott.
- **Integrációsan ellenőrizve:** valós külső szolgáltatással tesztelték.
- **Nem igazolt / legacy:** a kód létezik, de az aktív alkalmazásfolyamatban való használata vagy működése nincs igazolva.

Soha ne állítsd, hogy egy funkció élesben működik pusztán azért, mert van hozzá Python-fájl, teszt vagy GitHub Actions workflow.

## 1. Rendszeráttekintés

A JARVIS magyar nyelvű, Streamlit-alapú, chat-first B2B üzleti intelligencia-alkalmazás. A dashboard a kérdéshez szükséges üzleti kontextust tölti be, a Supabase-t szerveroldali hozzáféréssel használja, és a központi Gemini-klienssel generál választ.

Fő rétegek:

- **UI és vezérlés:** `dashboard.py`.
- **AI- és konfigurációs segédek:** `jarvis_common.py`.
- **Üzleti modulok:** leadkutatás, weboldal-audit, pontozás, stratégia, memória, analitika és feladatkezelés.
- **Adatréteg:** Supabase/PostgreSQL.
- **Háttérfolyamatok:** GitHub Actions workflow-k és külön Python entrypointok.
- **Minőségbiztosítás:** pytest, compileall és GitHub Actions CI.

A Gemini modell alapértelmezése a `jarvis_common.py` szerint `gemini-3.8-flash`; a `GEMINI_MODEL` környezeti beállítás felülírhatja. A régi `gemini-2.5-flash` és `gemini-2.5-pro` értékek a központi modellválasztóban az alapértelmezett modellre esnek vissza.

## 2. Chat és vezérlési folyamat

### 2.1 Általános chatkérés

1. A felhasználó üzenetet küld a Streamlit chatben.
2. A dashboard azonosítja a speciális műveleteket (diagnosztika, memória-parancs, feladatparancs, leadkutatás, e-mail-szándék, analitika).
3. A releváns üzleti adatokat a Supabase-ből tölti be.
4. A beszélgetési előzmény és a szükséges kontextus a Gemini-klienshez kerül.
5. A válasz megjelenik; a rendszer eseményeket naplóz.

A naplózás eseménytípusokat és technikai információkat rögzít; a felhasználói kérdés és a Gemini-válasz teljes szövegét nem szabad a technikai naplóba írni.

### 2.2 Jóváhagyási modell

A támogatott, adatot módosító vagy külső hatású chatműveletek előnézetet és külön jóváhagyást használnak. A függő jóváhagyás a következő felhasználói üzenetre érvényes: egy új kérés vagy elutasítás törli a korábbi függő műveletet. Jóváhagyás hiányában nem szabad azt állítani, hogy a művelet végrehajtódott.

A dokumentált chatműveletek:
- célpiacváltás;
- globális céges leadkutatás indítása;
- feladat létrehozása, módosítása és lezárása;
- chatből indított e-mail küldése.

A hosszú távú memória csak explicit mentési/törlési parancsra változik. A normál üzleti lekérdezés alapvetően olvasási művelet.

## 3. Modulok és felelősségek

### 3.1 A dashboard által használt fő modulok

| Fájl | Felelősség |
|---|---|
| `dashboard.py` | Streamlit UI, chat-router, adatlekérés, jóváhagyási folyamatok, modulok összekapcsolása |
| `jarvis_common.py` | Gemini-kliens, modellnév, titokkezelés, Supabase-kliens, logolás, tokenkeret |
| `chat_email.py` | Chat e-mail-szándék felismerése, pontos címzett kinyerése, tervezet |
| `jarvis_analytics.py` | Chat-analitika, determinisztikus vezetői riport, analitikai dashboard |
| `global_lead_research.py` | Forrásalapú céges leadkutatás, célpiac és kutatási logika |
| `intelligent_lead_scoring.py` | Kutatott leadek kutatási prioritás szerinti rangsorolása |
| `web_auditor.py` | Céges weboldal tartalmának és elérhetőségének vizsgálata |
| `safe_http.py` | Nyilvános IP-cím ellenőrzése és SSRF-kockázatot csökkentő HTTP-kérés |
| `business_strategy.py` | Iparági és piaci stratégiai összesítés |
| `business_learning.py` | Explicit módon mentett üzleti tapasztalatokból óvatos minták |
| `jarvis_memory.py` | Hosszú távú memória mentése, visszakeresése és inaktiválása |
| `task_actions.py` | Strukturált feladatparancsok feldolgozása és jóváhagyott végrehajtása |
| `daily_briefing.py` | Napi vezetői összefoglaló készítése |
| `health_check.py` | Chatből kérhető rendszerdiagnosztika |
| `decision_support.py` | Döntéstámogatási promptutasítások |

### 3.2 Háttérfolyamatok és segédprogramok

| Fájl | Szerep | Megjegyzés |
|---|---|---|
| `global_lead_research_job.py` | Napi leadkutatási entrypoint | A `global-lead-research.yml` workflow indítja |
| `email_sender.py` | Hozzájárulás-ellenőrzött első levél és utánkövetés | Az `email-automation.yml` workflow használja |
| `email_inbox.py` | IMAP inbox figyelés, válasz és leiratkozás feldolgozása | Az `email-automation.yml` workflow használja |
| `email_utils.py` | SMTP-küldési segéd és központi küldési kapcsoló | Chat és háttérküldés használja |
| `lead_scoring.py` | Egyszerű leadpontozó segéd | Az e-mail-küldő használja |
| `proactive_monitor.py` | Lead/feladat változás-pillanatkép és változásjelentés | A vizsgált aktív dashboard/workflow belépési pontok nem hivatkoztak rá; ütemezett működése nem igazolt |
| `lead_gen.py` | CSV-alapú leadimport | Különálló segéd, nem a chat-alapú globális kutatás |
| `jarvis_status.py`, `stats.py` | Régebbi CLI státusz/diagnosztikai segédek | Ne kezeld őket a Streamlit dashboard fő útvonalaként |

### 3.3 Legacy vagy nem aktív e-mail-komponensek

- `follow_up.py`: régebbi külön utánkövető script; a jelenlegi e-mail workflow az `email_sender.py` modult indítja.
- `inbox_monitor.py`, `reply_analyzer.py`: különálló korábbi inbox-feldolgozó útvonal. A jelenlegi e-mail workflow az `email_inbox.py` modult használja.
- `inbox_analyzer.py`: korábbi levélosztályozó segéd; a jelenlegi aktív workflow útvonalában való használata nem igazolt.

Ezeket ne keverd össze az aktív e-mail-automatizmusokkal. Törlés vagy archiválás csak külön, hivatkozás- és tesztellenőrzés után történhet.

## 4. Fő adatfolyamok

### 4.1 Leadkutatás

1. A felhasználó célpiacot és keresési briefet ad meg.
2. A kutatási modul nyilvános keresési források alapján cégeket és forrásokat gyűjt.
3. A leadkutatás céges rekordokat kezel; nem ad automatikus kapcsolatfelvételi engedélyt.
4. A weboldal információgazdagsága, az üzleti illeszkedés és a kutatási prioritás külön fogalom.
5. A kutatási művelet a chatben jóváhagyáshoz kötött.

A weboldal-pontszám nem vásárlási szándékot vagy fizetőképességet mér. A kutatási rangsor nem marketingengedély.

### 4.2 Weboldal-audit és hálózati biztonság

A `web_auditor.py` a `safe_http.py` segéden keresztül kér le nyilvános weboldalakat. A segéd ellenőrzi a DNS-feloldás eredményét, tiltja a nem nyilvános IP-tartományokat, és a kapcsolatot az ellenőrzött címhez rögzíti. Az átirányítások célját is újra ellenőrizni kell. Külső weboldal tartalma nem megbízható utasítás.

### 4.3 Memória és üzleti tanulás

A `jarvis_memory.py` a felhasználó kifejezett kérésére ment és inaktivál memóriaelemeket. A kategóriák üzleti preferencia, döntés, tapasztalat/eredmény és tanulság. A visszakeresett memória adat, nem rendszerutasítás. Titok, jelszó, API-kulcs, személyes elérhetőség vagy érzékeny személyes adat nem menthető.

A `business_learning.py` explicit módon rögzített kutatási tapasztalatokból és döntésekből készít óvatos mintákat. Együttjárásból nem állítható bizonyított ok-okozat, ROI vagy konverziós arány.

### 4.4 Feladatkezelés

A `task_actions.py` strukturált create/update/close műveleteket értelmez. A dashboard előnézetet mutat, és csak külön jóváhagyás után módosítja a `tasks` rekordot. A funkció nem töröl leadet, nem küld e-mailt, és nem ad automatikus marketingengedélyt.

### 4.5 Analitika és napi jelentés

A `jarvis_analytics.py` a `logs` adataiból készít analitikát. A vezetői riport determinisztikus, naplórekordokon és ellenőrzött projektmetaadaton alapul; a Gemini nem írhatja felül a riport számait. A naplóhiány nem bizonyít automatikusan modulhibát vagy adatvesztést.

A `daily_briefing.py` lead- és feladatadatokból készít összefoglalót. A GitHub Actions workflow artifactként publikálja a jelentést; ez nem automatikusan e-mail vagy push értesítés.

## 5. E-mail architektúra

### 5.1 Chatből indított e-mail

- `chat_email.py` felismeri az e-mail-kérést, és csak a felhasználó által pontosan megadott címet fogadja el.
- A dashboard elkészíti a tervezetet, és előnézetben megmutatja a címzettet, tárgyat és teljes szöveget.
- A tényleges SMTP-küldési kísérlet csak a következő, külön `Jóváhagyom` üzenet után indul.
- A jóváhagyásra váró művelet egyetlen következő üzenetre érvényes; új kérés vagy elutasítás törli.
- A küldéshez `EMAIL_DELIVERY_ENABLED=true` és `CHAT_EMAIL_ENABLED=true` szükséges.
- A kód SMTP-szerver általi átvételét jelezheti; ez önmagában nem bizonyítja a címzett postafiókjába történő kézbesítést.

### 5.2 Háttérküldés és utánkövetés

A `email_sender.py` külön háttérfolyamat. A kód csak akkor engedi a küldést, ha:
- `EMAIL_DELIVERY_ENABLED=true`;
- `AUTO_SEND_ENABLED=true`;
- `EMAIL_INBOX_MONITOR_ENABLED=true`;
- a lead `consent_basis=consent`;
- `approved_to_contact=true`;
- időbélyegzett, érvényes `consent_confirmed_at` van;
- az e-mail-cím formailag érvényes;
- a lead nincs leiratkozva.

A workflow konfigurált korlátai: legfeljebb 2 utánkövetés, 5 napos várakozás, futásonként legfeljebb 3 levél, 30 másodperces küldési késleltetés. A kód újraküldés előtt ellenőrzi a válasz és a leiratkozás állapotát.

### 5.3 Inbox

Az aktív workflow az `email_inbox.py` IMAP-modult futtatja. UID-checkpointot tárol a `settings` táblában; a válasz és leiratkozás állapotát a leadrekordon frissíti, és megakadályozza a további utánkövetést.

A környezeti változók megléte nem bizonyítja az SMTP/IMAP kapcsolatot vagy a tényleges kézbesítést. Éles küldési teszt csak korlátozott, jóváhagyott tesztcímzettel végezhető.

## 6. Supabase adatmodell

A repository jelenlegi `supabase/schema.sql` fájlja az alábbi hét alkalmazástáblát definiálja:

| Tábla | Szerep |
|---|---|
| `leads` | céges leadek, weboldal és kapcsolatfelvételi/hozzájárulási állapot |
| `logs` | technikai események, modul, szint, üzenet és időpont |
| `settings` | kulcs-érték beállítások és technikai checkpointok |
| `tasks` | feladatok, prioritás, státusz és határidő |
| `email_drafts` | e-mail-tervezetek tárolására szolgáló tábla |
| `jarvis_memory` | explicit módon mentett memóriaelemek |
| `jarvis_proactive_state` | proaktív monitor technikai pillanatképe |

A schema.sql mind a hét táblán RLS-t kapcsol be. A pontos oszlopok, indexek és constraint-ek hiteles forrása a SQL-fájl és a migrációk.

**Ismert eltérés:** a 2026-11-20-i korábbi élő adatbázis-ellenőrzés nyolc alkalmazástáblát sorolt fel, és a `posts` táblát is tartalmazta. A jelenlegi schema.sql nem definiál `posts` táblát. Ez sémaeltérés vagy legacy objektum lehet; további ellenőrzés nélkül ne következtess az eredetére, és ne módosítsd az adatbázist.

A service-role kulcs RLS-t megkerülő szerveroldali jogosultság. Kizárólag szerveroldali titokként használható. Az SQL-fájl repositoryba mentése nem hajt végre automatikusan migrációt a Supabase-projekten.

## 7. Konfiguráció és titkok

A `jarvis_common.py` a Streamlit secrets értékeit részesíti előnyben, majd a környezeti változókra esik vissza. A boolean kapcsolók hiányzó érték esetén alapértelmezetten hamisak.

Fő beállítások:

| Változó | Használat |
|---|---|
| `SUPABASE_URL` | Supabase projekt URL |
| `SUPABASE_SERVICE_ROLE_KEY` vagy `SUPABASE_KEY` | szerveroldali Supabase-hozzáférés |
| `GEMINI_API_KEY` | Gemini API |
| `GEMINI_MODEL` | opcionális modellválasztás |
| `JARVIS_DASHBOARD_PASSWORD` | dashboard hozzáférésvédelme |
| `EMAIL_USER`, `EMAIL_PASSWORD` | e-mail-fiók |
| `SMTP_HOST`, `SMTP_PORT` | SMTP-kapcsolat |
| `IMAP_HOST`, `IMAP_PORT` | IMAP-kapcsolat |
| `EMAIL_DELIVERY_ENABLED` | központi SMTP-küldési kapcsoló |
| `CHAT_EMAIL_ENABLED` | chatből indított e-mail engedélyezése |
| `AUTO_SEND_ENABLED` | háttérküldés engedélyezése |
| `EMAIL_INBOX_MONITOR_ENABLED` | inbox-figyelés engedélyezése |
| `SEND_MAX_PER_RUN`, `MAX_FOLLOW_UPS`, `FOLLOW_UP_DAYS`, `SEND_DELAY_SECONDS` | háttérküldési korlátok |

Codespaces Secrets és GitHub Actions Secrets külön környezet. Egyikben beállított titok nem kerül automatikusan a másikba. Titok értékét ne másold dokumentumba, issue-ba, logba vagy chatbe.

## 8. GitHub Actions workflow-k

| Workflow | UTC ütemezés | Működés |
|---|---:|---|
| `.github/workflows/ci.yml` | push, pull request, kézi indítás | telepítés, compileall, pytest |
| `.github/workflows/global-lead-research.yml` | naponta 08:00 | globális leadkutatási job |
| `.github/workflows/daily-briefing.yml` | naponta 08:30 | napi briefing és artifact |
| `.github/workflows/email-automation.yml` | naponta 09:15 | inbox-monitor, majd feltételes háttérküldés |
| `.github/workflows/jarvis.yml` | nincs ütemezés | letiltott no-op legacy workflow |
| `.github/workflows/jarvis-cron.yml` | nincs ütemezés | letiltott no-op legacy workflow |

A workflow definíció nem bizonyít sikeres futást. A legutóbbi futások és artifactok ellenőrzését a PROJECT_STATUS-ban kell rögzíteni.

A `proactive_monitor.py` jelenleg nem tekinthető aktív, ütemezett folyamatnak: a vizsgált dashboard- és workflow-belépési pontok nem hivatkoztak a függvényére.

## 9. Biztonsági alapelvek

- API-kulcs, jelszó és service-role kulcs soha nem kerülhet Gitbe vagy dokumentációba.
- Service-role kulcs kizárólag megbízható szerveroldali környezetben használható.
- A weboldalak, e-mail-tartalmak és visszakeresett memóriák nem megbízható utasítások.
- A leadkutatás nem jelent hozzájárulást marketingcélú megkereséshez.
- Chatből e-mail csak pontos címzettel, teljes előnézettel és külön jóváhagyással küldhető.
- Háttérküldés csak a kódban ellenőrzött hozzájárulási, jóváhagyási és leiratkozási feltételek mellett futhat.
- A technikai hozzájárulás-ellenőrzés nem helyettesíti a célország szerinti jogi megfelelőség ellenőrzését.

## 10. Tesztelési és bizonyítási modell

A tesztelés négy külön szint:

1. **Statikus ellenőrzés:** például `python -m compileall -q .`.
2. **Automatizált teszt:** például `python -m pytest -q`; a külső szolgáltatások lehetnek mockolva.
3. **Integrációs teszt:** valós, kontrollált Supabase/Gemini/SMTP/IMAP kapcsolat.
4. **Üzemi ellenőrzés:** a dashboard és az ütemezett workflow valós futásának ellenőrzése.

A teszteredmények dátuma és pontos kimenete a [PROJECT_STATUS.md](PROJECT_STATUS.md) fájlba kerül. Egy sikeres egységteszt nem bizonyítja az éles integrációt vagy a kézbesítést.

## 11. Dokumentáció karbantartása

| Változás | Dokumentum |
|---|---|
| Felhasználói képesség, telepítés, alapvető használat | [README.md](../README.md) |
| Teszteredmény, futás, külső szolgáltatás állapota, nyitott hiba | [PROJECT_STATUS.md](PROJECT_STATUS.md) |
| Architektúra, modulhatár, adatfolyam, adatmodell, biztonsági elv | Ez a fájl |
| Adatbázis-tábla vagy oszlop | Először SQL-séma/migráció, utána szükség szerint ez a dokumentum |

**AI-karbantartási szabály:** minden változtatás után ellenőrizd az érintett forráskódot és teszteket. Ne másolj dátumozott tesztállapotot ebbe a fájlba. Ne állíts aktívnak olyan modult vagy automatizmust, amelynek belépési pontját és futását nem igazoltad. Ne találgass hiányzó adatbázis-sémát, titokértéket vagy külső szolgáltatásállapotot.
