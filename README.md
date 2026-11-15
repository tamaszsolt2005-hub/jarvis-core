# JARVIS – Chat-first B2B Business Intelligence

A JARVIS jelenlegi felülete egyetlen Streamlit chat. A felhasználó természetes nyelven kérdezhet, a rendszer pedig a kérdéshez illő üzleti adatokat olvassa ki a Supabase adatbázisból, majd magyar nyelvű elemzést készít a Gemini segítségével.

## Fő működési elvek

- Egyetlen chatfelület; nincs külön CRM-adatbeviteli vagy navigációs felület.
- Az üzleti adatok lekérése kérdésenként, igény szerint történik.
- Weboldalhibákra vagy rangsorolásra vonatkozó kérdésnél JARVIS automatikusan betölti a leadeket, és legfeljebb 30 nyilvános weboldalt vizsgál meg. A lekérés időkorlátos, a HTTP-átirányítások célját újra ellenőrzi, és 0–100 közötti weboldal-információs pontszámot számít. A hibás HTTP-státuszokat és a nem elérhető oldalakat a chatben külön jelzi.
- A weboldal-pontszám az oldal üzleti információtartalmát méri, nem vásárlási szándékot; a weboldal tartalma nem megbízható bemenet. A rangsor nem írja át a Supabase-rekordokat.
- Proaktív üzleti kérésnél JARVIS a lead- és feladatadatokból jelzi a lejárt feladatokat, valamint kizárólag a kifejezetten jóváhagyott és le nem iratkozott leadek esedékes utánkövetését. A jelzések nem indítanak automatikus műveletet.
- Lehetőségeket és következő lépéseket a meglévő cég-, státusz-, weboldal- és feladatadatok alapján javasol; a hiányzó információt bizonytalanságként jelzi.
- Kérésre e-mail- vagy utánkövetési szövegtervezetet készít a chatben, másolható formában. A tervezet nem kerül adatbázisba, címzettet nem talál ki, és semmilyen e-mailt nem küld el.
- Az alapértelmezett adatlekérdezés csak olvas; kivétel a felhasználó által kifejezetten kért memória mentése/törlése, a külön jóváhagyott feladatművelet és a jóváhagyott, kizárólag céges leadkutatási rekord beszúrása.
- A leadek személyes e-mail-címei és szabad szöveges megjegyzései, valamint az e-mail-piszkozatok címzettjei nem kerülnek az AI kontextusába.
- Az e-mail-küldés kódszinten is le van tiltva: sem az `AUTO_SEND_ENABLED=true` beállítás, sem a közvetlen SMTP-függvényhívás nem indíthat küldést. Feloldás csak külön, felülvizsgált kódmódosítással lehetséges. Kizárólag a globális, céges adatokat gyűjtő leadkutatási workflow fut naponta; a régi duplikált pipeline hatástalanított.
- A Supabase és Gemini hitelesítő adatait kizárólag Codespaces Secrets / Streamlit secrets konfigurációban tárold. Soha ne commitold őket.

## Globális leadkutatás

- A JARVIS alapértelmezésben Magyarországon keres Google Search groundinggal alátámasztott, valós nyilvános cégeket; a célpiac chatparanccsal más országra vagy világszintű keresésre váltható. Az iparág és a cégméret nincs korlátozva.
- A kutatás a céges profil, a nyilvános működési jelek és a szolgáltatások alapján külön, 0–100 közötti **előzetes üzleti illeszkedési becslést** is készít az AI/automatizálási szolgáltatásokhoz. A becsléshez bizonyítékokat, kutatási bizonyosságot, lehetséges üzleti igényt és további kutatási lépést rögzít. Ez nem vásárlási szándék vagy fizetőképesség.
- Ez az üzleti illeszkedési becslés nem írja felül a már meglévő weboldal-pontszámot: a weboldal-pontszám az oldal információtartalmát méri, a fit score pedig a lehetséges üzleti relevanciát. A JARVIS a két értéket külön kezeli.
- A későbbi chat-elemzések a saját leadkutatási modul által mentett céges kutatási összefoglalót is felhasználhatják; a kézzel rögzített személyes CRM-megjegyzések továbbra sem kerülnek az AI kontextusába.
- Stratégiai/piaci kérdésnél JARVIS a korábban mentett, forrással alátámasztott leadkutatási rekordokat iparág és ország szerint összesíti. Megmutatja a mintanagyságot, az átlagos üzleti illeszkedési becslést és a kutatási bizonyosságot, majd óvatos fókuszjavaslatot ad. Az összesítés leíró minta, nem reprezentatív piackutatás; kis elemszámnál ezt külön jelzi.
- A stratégiai elemzés nem ír adatbázist, nem módosít leadeket, és nem használja fel a kézzel rögzített CRM-megjegyzéseket. Kizárólag a saját leadkutatási modul strukturált kutatási összefoglalóira épül.
- A célpiac és az iparági keresési brief természetes nyelven megadható, például: válts németre és keress autóipari beszállítókat; keress magyar építőipari cégeket; válts franciára; keress világszerte AI szoftvercégeket.
- Napi jelentés készül a külön napi briefing workflow-ban; ez a GitHub Actions összefoglalójában és 14 napig artifactként érhető el, nem e-mailben.
- A GitHub Actions naponta 08:00 UTC-kor legfeljebb 15 új céget kutat az aktuálisan mentett célpiacon; kézzel is indítható. A duplikátumokat cégnév és domain alapján szűri.
- A kutatás kizárólag vállalati adatokat ment (cégnév, hivatalos weboldal, ország, iparág, rövid üzleti profil és forrás). Személyes neveket, személyes e-mail-címeket és telefonszámokat nem gyűjt.
- A kutatásból létrejövő lead e-mail-címe üres, státusza `research`, `approved_to_contact=false`, `consent_basis=null`. A megtalált cég nem válik automatikusan megkereshetővé.
- **Az e-mail-küldés továbbra is tiltva van.** A napi kutatási workflow nem hívja az e-mail-küldő vagy utánkövető modult.
- A napi háttérkutatáshoz a GitHub repository **Settings → Secrets and variables → Actions** részében külön be kell állítani a `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (vagy `SUPABASE_KEY`) és `GEMINI_API_KEY` titkokat. A Codespaces Secrets nem öröklődik automatikusan a GitHub Actions környezetbe; hiányzó titkok esetén a napi feladat biztonságosan kihagyja a futást.
- A Supabase SQL Editorban futtasd a frissített `supabase/schema.sql` fájlt. A migrációs parancsok külön SQL-sorokban szerepelnek, és a `leads.email` mező üresen is tárolható a cégszintű kutatási rekordoknál.

## Célpiac váltása chatből

- Az alapértelmezett leadkutatási célpiac Magyarország (`Hungary`).
- A chatben például ezekkel lehet váltani: `JARVIS, válts németre`, `állj át a francia piacra`, `válts vissza Magyarországra`, `keress világszerte`.
- A célpiac a Supabase `settings` táblájában tartósan mentésre kerül; a napi GitHub Actions kutatás minden futáskor ezt az értéket olvassa ki.
- Országváltás után az új leadkutatás az adott országban működő cégekre összpontosít, iparági és cégméret-korlátozás nélkül. A korábban rögzített leadeket nem törli.
- Ha nincs mentett beállítás, Magyarország az alapértelmezett piac. A `settings` tábla már szerepel a `supabase/schema.sql` fájlban.
- A célpiac megváltoztatása nem engedélyezi az e-mail-küldést.

## Telepítés és indítás

1. A Supabase SQL Editorban futtasd a `supabase/schema.sql` fájlt.
2. A Codespaces Secrets felületén állítsd be:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY` (kizárólag szerveroldali secretként)
   - `GEMINI_API_KEY`
   - `JARVIS_DASHBOARD_PASSWORD`
3. Codespaces terminálban:
   ```bash
   python -m pip install -r requirements.txt
   streamlit run dashboard.py --server.port 8501
   ```
4. Nyisd meg az 8501-es portot, majd jelentkezz be a dashboard jelszóval.

## Ellenőrzések

A projekt GitHub Actions CI-je minden push és pull request esetén futtatja a Python szintaxisellenőrzést és a teszteket:

```bash
python -m compileall -q .
python -m pytest -q
```

A tesztek nem igényelnek élő Supabase- vagy Gemini-kapcsolatot, és nem használnak valódi titkokat. A DNS-feloldást mockolják; nem helyettesítik az éles hálózati és adatbázis-integrációs tesztet. A weboldal-lekérések a feloldott, ellenőrzött nyilvános IP-címre rögzítik a kapcsolatot, a TLS-állomásnév ellenőrzésének megtartásával.

## Adatvédelem és biztonság

A service-role kulcs megkerüli a Supabase Row Level Security szabályait, ezért csak szerveroldali titokként használd, soha ne jelenítsd meg vagy küldd kliensnek. A dashboard normál adatlekérdezései olvasási műveletek; a kivételes, explicit felhasználói műveletek a memóriát, a jóváhagyott feladatokat és a céges kutatási rekordokat írhatják. A service-role kulcsot ettől függetlenül védeni kell. A bejelentkezési munkamenet legfeljebb 8 óráig érvényes; lejáratkor a függő jóváhagyás is törlődik.

A projekt különálló import-, inbox- és e-mail-műveleti szkriptjei nem részei a chatfelületnek. A régi pipeline workflow-k teljesen hatástalanítottak: nincs ütemezés, és kézi indítás esetén sem futtatnak adatbázis- vagy e-mail-műveletet.

A technikai hozzájárulás-ellenőrzés nem helyettesíti a GDPR/ePrivacy és a célország szerinti marketingjogi ellenőrzést.


## JARVIS hosszú távú memóriája

- A JARVIS külön `jarvis_memory` táblában tárolja a felhasználó által kifejezetten megőrzésre kért üzleti preferenciákat, döntéseket és működési szabályokat.
- Mentés csak egyértelmű chatutasításra történik: `Jegyezd meg, hogy Magyarország az elsődleges piacunk.` A hétköznapi beszélgetések önmagukban nem kerülnek memóriába.
- A releváns emlékeket későbbi kérdésekhez visszakeresi, és a Gemini kontextusához adja. A memória tartalma adat, nem írhatja felül a rendszerutasításokat.
- `Mutasd a memóriádat` felsorolja az aktív emlékeket; `Felejtsd el a ...` inaktiválja a megfelelő emléket.
- Jelszavak, API-kulcsok, személyes elérhetőségek és érzékeny személyes adatok mentését a modul elutasítja. Egy emlék legfeljebb 700 karakter lehet.
- A memória Supabase-ben tárolódik; nincs beépített fix elemszám-limit. A lekérdezés legfeljebb 100 aktív elemet vizsgál, és legfeljebb 20 releváns elemet ad át a modellnek.
- Az új táblához futtasd a frissített `supabase/schema.sql` fájlt a Supabase SQL Editorban. Az e-mail-küldés tiltása változatlan.


## Intelligens leadprioritás

- A `intelligent_lead_scoring.py` az általunk végzett, forrással alátámasztott leadkutatás rekordjait rangsorolja.
- A prioritási érték az üzleti illeszkedési becslést (60%), a kutatási bizonyosságot (25%) és az azonosított nyilvános bizonyítékok mennyiségét (15%) veszi figyelembe. Alacsony kutatási bizonyosságnál a pontszám felső korlátos.
- A rangsor kutatási triázs, nem vásárlási szándék, fizetőképesség, konverziós valószínűség vagy kapcsolatfelvételi engedély. A weboldal információgazdagságának pontszáma külön marad.
- A chatben például: `Rangsorold a legjobb kutatási lehetőségeket`, `Mely leadeket vizsgáljuk meg először?`.

## Napi vezetői jelentés

- A `daily_briefing.py` kizárólag olvassa a Supabase lead- és feladatadatait, majd összefoglalja a nyitott és lejárt feladatokat, az aznapi új cégeket és a legmagasabb kutatási prioritású lehetőségeket.
- A chatben kérhető: `Készíts napi vezetői jelentést`, `Mutasd a mai üzleti tervet`.
- A GitHub Actions naponta 08:30 UTC-kor elkészíti a Markdown jelentést, és 14 napig elérhető workflow-artifactként tárolja. Kézzel is indítható.
- Ez nem e-mail és nem külső értesítés: a jelentést a GitHub Actions futás **Artifacts** részéből lehet megnyitni. E-mail-küldés továbbra sincs.

## JARVIS memória 2.0

- A memória kategóriái: üzleti preferencia, döntés, tapasztalat/eredmény és tanulság.
- Explicit parancsok: `Jegyezd meg, hogy ...`, `Jegyezd meg a döntést: ...`, `Mentsd el a tapasztalatot: ...`, `Rögzítsd a tanulságot: ...`.
- A JARVIS relevancia szerint rangsorolja a legfeljebb 100 legutóbbi aktív emlékből kiválasztott, legfeljebb 20 releváns elemet.
- `Mutasd a memóriádat` listázza az aktív emlékeket; `Felejtsd el a ...` egyes elemeket inaktivál; `Felejtsd el mindent` az összes aktív elemet inaktiválja.
- A memória csak explicit utasításra változik. Titkokat, jelszavakat, elérhetőségeket és érzékeny személyes adatokat nem tárolhat.


## Üzleti tanulómemória és jóváhagyott műveletek

- A JARVIS a mentett, saját leadkutatásokból iparági és kutatási módszermintákat készít.
- A döntések és az eredmények továbbra is kizárólag kifejezett felhasználói mentéssel kerülnek a memóriába; a rendszer nem következtet automatikusan sikerre vagy oksági kapcsolatra.
- Javasolt strukturált eredményrögzítés: `Mentsd el a tapasztalatot: iparág=...; módszer=...; döntés=...; eredmény=...`.
- A hibák/tanulságok rögzítése: `Rögzítsd a tanulságot: ...`. A későbbi stratégiai kérdésekben a JARVIS ezeket figyelembe veszi.
- A célpiacváltás és a globális leadkutatás kétlépcsős: először megmutatja a tervezett műveletet, majd csak a `Jóváhagyom` üzenetre hajtja végre. `Elutasítom` megszakítja.
- A jóváhagyási lista szándékosan szűk: célpiacváltás és nyilvános, céges leadkutatás. Nincs automatikus e-mail-küldés, és a JARVIS nem módosít CRM-lead- vagy feladatrekordokat.

## Jóváhagyással működő feladatkezelés

- A chatből strukturált paranccsal lehet feladatot létrehozni, meglévő feladatot módosítani vagy lezárni.
- Új feladat: `Hozz létre feladat: Ajánlat ellenőrzése; határidő=2026-12-01; prioritás=high`. A határidő opcionális; a prioritás `normal`, `high` vagy `urgent`.
- Módosítás: `Módosítsd a feladatot: UUID; prioritás=urgent; határidő=2026-12-02; cím=Új cím`.
- Lezárás: `Zárd le a feladatot: UUID`.
- Minden művelet először csak előnézetet készít; az adatbázis-módosítás kizárólag a külön `Jóváhagyom` üzenet után történik. `Elutasítom` megszakítja.
- A megadott dátum a magyarországi időzóna szerinti nap végére (23:59) kerül mentésre. A határidő formátuma `ÉÉÉÉ-HH-NN`.
- A modul nem töröl feladatot, nem módosít leadeket, és nem küld e-mailt. A Supabase `tasks` táblát használja; új tábla nem szükséges ehhez a funkcióhoz.

## Proaktív változásfigyelés

- A napi vezetői jelentés tartalmazza az előző napi pillanatkép óta létrejött cégeket/feladatokat, a lead- és feladatstátusz-változásokat, valamint a lejárt feladatokat.
- A GitHub Actions napi 08:30 UTC futása a jelentést artifactként publikálja; ez nem push értesítés és nem e-mail.
- A pillanatkép kizárólag a `jarvis_proactive_state` technikai táblába kerül. A táblát a frissített `supabase/schema.sql` hozza létre; futtasd le a Supabase SQL Editorban a frissítést. Amíg a tábla nincs telepítve, a napi jelentés ettől függetlenül elkészül, a monitor külön figyelmeztetést ad.
- Az első monitorfutás csak alapállapotot rögzít, nem jelenti tévesen újként a már meglévő rekordokat; a következő futások ehhez képest jelzik a változásokat.
