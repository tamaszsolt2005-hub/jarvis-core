# JARVIS – műszaki dokumentáció

**Utolsó dokumentációs felülvizsgálat:** 2026-11-20  
**Repository:** `tamaszsolt2005-hub/jarvis-core` · **Branch:** `main`

Ez a dokumentum a JARVIS belső felépítését, modulhatárait, adatfolyamait és biztonsági szabályait írja le. Nem helyettesíti az aktuális projektállapotot: az elkészült, tesztelt és élesben igazolt funkciók státuszát a [PROJECT_STATUS.md](PROJECT_STATUS.md) tartalmazza. A felhasználói bemutatást és az indítási útmutatót a [README.md](../README.md) tartalmazza.

> **Dokumentációs szabály:** a leírás a repository dokumentációjából és az ismert implementációs szerződésekből készült. A modulnevek és a működési elvek nem jelentenek automatikus bizonyítékot az éles szolgáltatáskapcsolatokra. Ahol külső integráció szükséges, azt külön jelezzük.

## 1. Rendszeráttekintés

A JARVIS egy magyar nyelvű, Streamlit-alapú, chat-first B2B üzleti intelligencia-alkalmazás. A felhasználói kérdés alapján a rendszer kiválasztja a szükséges üzleti adatokat, a Supabase-ből olvas, majd a központi Gemini-integrációval állít elő választ.

Fő építőelemek:

- **Felhasználói felület:** Streamlit chat és jóváhagyási folyamatok.
- **AI-réteg:** központi Gemini-kliens és modellkonfiguráció.
- **Üzleti logika:** leadkutatás, weboldal-audit, pontozás, memória, döntéstámogatás és feladatkezelés.
- **Adatréteg:** Supabase-adatbázis és szerveroldali hozzáférés.
- **Automatizálás:** külön GitHub Actions workflow-k a napi leadkutatáshoz, briefinghez és az e-mail-automatizmushoz.
- **Minőségbiztosítás:** Python szintaxisellenőrzés, pytest és GitHub Actions CI.

## 2. Fő adat- és vezérlési folyamatok

### 2.1 Chatkérés

1. A felhasználó természetes nyelvű kérdést küld a Streamlit felületen.
2. A dashboard és a kapcsolódó logika meghatározza a kérdéshez szükséges adatokat.
3. A szükséges üzleti adatok korlátozott lekérdezéssel érkeznek a Supabase-ből.
4. A központi Gemini-kliens a releváns kontextussal elkészíti a választ.
5. A kérés és a válasz eseménye naplózható; a nyers kérdés- és válaszszöveg nem kerül a rendszernaplóba.
6. A felület megjeleníti a választ és a kérés állapotát.

A válaszhossz helyi heurisztikával igazodik a kérdés összetettségéhez; ez nem igényel külön AI-hívást. A tokenkeret felső korlát, nem garantált kimeneti hossz.

### 2.2 Jóváhagyást igénylő műveletek

A módosítást vagy külső hatást végző műveletek előnézeti/jóváhagyási mintát használnak, ahol ezt a funkció megköveteli. A jóváhagyás a bemutatott művelethez kötött; másik felhasználói kérés vagy elutasítás érvénytelenítheti a függő jóváhagyást.

A feladatkezelésnél a létrehozás, módosítás és lezárás először előnézetet készít. Az adatbázis-módosítás csak a külön jóváhagyás után történik.

### 2.3 Leadkutatás

1. A felhasználó megadja a célpiacot és a keresési briefet.
2. A kutatási modul nyilvános forrásokra és keresési groundingra támaszkodó céges találatokat készít.
3. A rendszer strukturált céges kutatási adatokat és forrásokat kezel.
4. Külön értékeli a weboldal információgazdagságát, az üzleti illeszkedést és a kutatási prioritást.
5. A kutatás önmagában nem ad kapcsolatfelvételi engedélyt.

A kutatás nem gyűjthet automatikusan személyes elérhetőségeket; a leadkutatási rekord nem válik pusztán a megtalálásától megkereshetővé.

### 2.4 E-mail-folyamat

**Chatből indított e-mail:**
- A rendszer csak a felhasználó által pontosan megadott, érvényes formátumú címre készít tervezetet.
- A címzett, tárgy és teljes szöveg küldés előtt előnézetben látható.
- Küldéshez külön, egyértelmű felhasználói jóváhagyás szükséges.
- A chatküldéshez az `EMAIL_DELIVERY_ENABLED` és `CHAT_EMAIL_ENABLED` szerveroldali kapcsoló szükséges.

**Háttérben futó e-mail és utánkövetés:**
- Külön automatizmus; nem azonos a chatből indított, felhasználói jóváhagyásos küldéssel.
- Csak igazolt hozzájárulás, jóváhagyott kapcsolatfelvétel, érvényes e-mail-cím és leiratkozás hiánya esetén futhat.
- A háttérküldéshez az SMTP-küldés, az automatikus küldés és az inbox-figyelés külön engedélyezése szükséges.
- A bejövő válasz vagy leiratkozás megállítja a további utánkövetést.
- A pontos korlátokat és kapcsolókat az aktuális README, illetve a kód konfigurációja tartalmazza.

**Ellenőrzési határ:** a környezeti változók megléte nem bizonyít SMTP/IMAP-kapcsolatot vagy tényleges kézbesítést. Az éles végponttól végpontig teszt külön feladat.

## 3. Modulhatárok és felelősségek

A főbb, dokumentált komponensek felelősségi körei:

| Terület / komponens | Felelősség |
|---|---|
| `dashboard.py` | Streamlit felület, chatfolyamat és felhasználói jóváhagyási interakciók |
| `chat_email.py` | Chatből érkező e-mail-szándék értelmezése, címzett-ellenőrzés és tervezet |
| `email_utils.py` | E-mail-konfiguráció és biztonsági kapcsolók |
| `email_inbox.py` | Bejövő levelek IMAP-alapú figyelése, válasz/leiratkozás feldolgozása |
| `email_sender.py` | Háttérküldés és utánkövetési szabályok |
| `daily_briefing.py` | Napi vezetői összefoglaló |
| `intelligent_lead_scoring.py` | Kutatási prioritás meghatározása |
| `supabase/schema.sql` | Adatbázis-séma kiinduló definíciója |
| `.github/workflows/` | CI és ütemezett háttérfolyamatok |

A repository további moduljai külön üzleti logikát valósítanak meg. Új modul hozzáadásakor ezt a táblázatot és a kapcsolódó adatfolyam-leírást frissíteni kell, miután a tényleges forráskódot ellenőriztük.

## 4. Adatmodell és Supabase

A JARVIS a meglévő Supabase-projektet használja. A dokumentált táblák és szerepük:

- `leads`: céges leadek és kutatási adatok.
- `tasks`: felhasználói feladatok és határidők.
- `settings`: tartós alkalmazásbeállítások, célpiac és technikai checkpointok.
- `logs`: technikai események és naplóadatok.
- `jarvis_memory`: kifejezetten mentett preferenciák, döntések, tapasztalatok és tanulságok.
- `jarvis_proactive_state`: proaktív változásfigyelés technikai pillanatképe.

A pontos oszlopdefiníciók és indexek hiteles forrása a `supabase/schema.sql` és a `supabase/migrations/` könyvtár. Ez a dokumentum nem helyettesíti az SQL-sémát.

Az adatbázis módosítását a repositoryban lévő SQL-fájl önmagában nem hajtja végre: a migrációt a megfelelő Supabase-környezetben külön kell telepíteni és ellenőrizni.

## 5. Memória és üzleti tanulás

A hosszú távú memória kizárólag kifejezett felhasználói utasításra változik. Kategóriái:
- üzleti preferencia;
- döntés;
- tapasztalat/eredmény;
- tanulság.

A releváns emlékek visszakereshetők a későbbi kérdésekhez. A memória tartalma adat, nem rendszerutasítás, ezért nem írhatja felül a rendszer biztonsági szabályait.

A JARVIS az explicit módon rögzített kutatási eredményekből és döntésekből óvatos mintákat készíthet. Az együttjárást nem állíthatja be bizonyított ok-okozati kapcsolatként, és nem találhat ki üzleti eredményt, ROI-t vagy konverziós adatot.

Titkok, jelszavak, API-kulcsok, személyes elérhetőségek és érzékeny személyes adatok nem kerülhetnek a memóriába.

## 6. Biztonsági alapelvek

- Titkok kizárólag szerveroldali környezeti változókban, Codespaces Secrets vagy GitHub Actions Secrets konfigurációban tárolhatók.
- API-kulcsot, jelszót vagy service-role kulcsot nem szabad Gitbe commitolni, kliensoldalra továbbítani vagy naplózni.
- A Supabase service-role kulcs megkerüli az RLS-t; kizárólag megbízható szerveroldali környezetben használható.
- A nyilvános weboldalak és a memóriából visszakeresett szövegek nem megbízható bemenetek; nem írhatják felül a rendszerutasításokat.
- A leadkutatás nem jelent marketing-hozzájárulást.
- E-mail-küldés és háttér-automatizmus csak külön konfigurációval és a megfelelő jóváhagyási/hozzájárulási feltételekkel működhet.
- A technikai hozzájárulás-ellenőrzés nem helyettesíti a GDPR/ePrivacy és a célország szerinti jogi ellenőrzést.

## 7. Automatizálás és CI

A GitHub Actions workflow-k külön feladatokat látnak el:
- CI: Python szintaxisellenőrzés és automatizált tesztek push/pull request esetén.
- Napi leadkutatás: a mentett célpiac alapján új cégek kutatása.
- Napi briefing/proaktív figyelés: napi jelentés és változások összefoglalása.
- E-mail-automatizmus: inbox-ellenőrzés és – csak a szükséges kapcsolók és hozzájárulási feltételek mellett – háttérküldés.

A workflow-fájl jelenléte nem bizonyítja, hogy a szükséges GitHub Actions titkok konfigurálva vannak, vagy hogy a külső szolgáltatások elérhetők.

## 8. Tesztelési stratégia és bizonyítási szintek

A tesztelés értelmezésekor külön kell választani:

1. **Statikus ellenőrzés:** például `python -m compileall -q .`.
2. **Automatizált teszt:** például `python -m pytest -q`; mockolt külső szolgáltatásokkal is futhat.
3. **Integrációs teszt:** tényleges, kontrollált Supabase/Gemini/IMAP/SMTP környezetben végzett próba.
4. **Üzemi ellenőrzés:** a felület, workflow-k és külső szolgáltatások valós működésének ellenőrzése.

Egy sikeres egységteszt vagy CI-futás nem bizonyít éles kézbesítést, folyamatos rendelkezésre állást vagy külső szolgáltatás-hozzáférést. A dátumozott teszteredményeket és nyitott ellenőrzéseket a [PROJECT_STATUS.md](PROJECT_STATUS.md) dokumentumban kell vezetni.

## 9. Dokumentáció karbantartása

| Változás | Frissítendő dokumentum |
|---|---|
| Új felhasználói képesség vagy telepítési lépés | [README.md](../README.md) |
| Tesztfutás, elkészült feladat, hiba vagy ellenőrzött környezeti állapot | [PROJECT_STATUS.md](PROJECT_STATUS.md) |
| Modulhatár, adatfolyam, adatmodell vagy biztonsági architektúra változása | Ez a dokumentum |
| SQL-tábla/oszlop/index változása | Először a `supabase/schema.sql` és migráció; utána ez a dokumentum, ha az architektúra-leírás is változik |

**Alapelv:** a README a felhasználónak szól, a PROJECT_STATUS a fejlesztés aktuális állapotát rögzíti, a TECHNICAL_DOCUMENTATION pedig a rendszer belső működését magyarázza. Ugyanazt a változó állapotot ne tartsuk karban több helyen.
