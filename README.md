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
- A dashboard adatbázis-műveletei olvasásra korlátozódnak.
- A leadek személyes e-mail-címei és szabad szöveges megjegyzései, valamint az e-mail-piszkozatok címzettjei nem kerülnek az AI kontextusába.
- Az automatikus e-mail-küldés nincs engedélyezve; a küldő és utánkövető modulok alapértelmezetten leállnak. A napi háttér-workflow-k ütemezése ki van kapcsolva; a régi duplikált workflow hatástalanított.
- A Supabase és Gemini hitelesítő adatait kizárólag Codespaces Secrets / Streamlit secrets konfigurációban tárold. Soha ne commitold őket.

## Globális leadkutatás

- A JARVIS a chatben kifejezett leadkutatási kérésre Google Search groundinggal valós, nyilvános cégeket kereshet világszerte, iparági és cégméret-korlátozás nélkül.
- A GitHub Actions naponta 08:00 UTC-kor legfeljebb 15 új céget kutat; kézzel is indítható. A duplikátumokat cégnév és domain alapján szűri.
- A kutatás kizárólag vállalati adatokat ment (cégnév, hivatalos weboldal, ország, iparág, rövid üzleti profil és forrás). Személyes neveket, személyes e-mail-címeket és telefonszámokat nem gyűjt.
- A kutatásból létrejövő lead e-mail-címe üres, státusza `research`, `approved_to_contact=false`, `consent_basis=null`. A megtalált cég nem válik automatikusan megkereshetővé.
- **Az e-mail-küldés továbbra is tiltva van.** A napi kutatási workflow nem hívja az e-mail-küldő vagy utánkövető modult.
- A napi háttérkutatáshoz a GitHub repository **Settings → Secrets and variables → Actions** részében külön be kell állítani a `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (vagy `SUPABASE_KEY`) és `GEMINI_API_KEY` titkokat. A Codespaces Secrets nem öröklődik automatikusan a GitHub Actions környezetbe; hiányzó titkok esetén a napi feladat biztonságosan kihagyja a futást.
- A Supabase SQL Editorban egyszer futtasd a frissített `supabase/schema.sql` fájlt, hogy a `leads.email` mező üresen is tárolható legyen a cégszintű kutatási rekordoknál.

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

A tesztek nem igényelnek élő Supabase- vagy Gemini-kapcsolatot, és nem használnak valódi titkokat.

## Adatvédelem és biztonság

A service-role kulcs megkerüli a Supabase Row Level Security szabályait, ezért csak szerveroldali titokként használd, soha ne jelenítsd meg vagy küldd kliensnek. A dashboard kódja kizárólag lekérdezéseket használ, de a service-role kulcs jogosultságait ettől függetlenül védeni kell.

A projekt különálló import-, inbox- és e-mail-műveleti szkriptjei nem részei a chatfelületnek. A régi pipeline workflow-k teljesen hatástalanítottak: nincs ütemezés, és kézi indítás esetén sem futtatnak adatbázis- vagy e-mail-műveletet.

A technikai hozzájárulás-ellenőrzés nem helyettesíti a GDPR/ePrivacy és a célország szerinti marketingjogi ellenőrzést.
