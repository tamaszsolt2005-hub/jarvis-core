# JARVIS – Chat-first B2B Business Intelligence

A JARVIS jelenlegi felülete egyetlen Streamlit chat. A felhasználó természetes nyelven kérdezhet, a rendszer pedig a kérdéshez illő üzleti adatokat olvassa ki a Supabase adatbázisból, majd magyar nyelvű elemzést készít a Gemini segítségével.

## Fő működési elvek

- Egyetlen chatfelület; nincs külön CRM-adatbeviteli vagy navigációs felület.
- Az üzleti adatok lekérése kérdésenként, igény szerint történik.
- A dashboard adatbázis-műveletei olvasásra korlátozódnak.
- A leadek személyes e-mail-címei és szabad szöveges megjegyzései nem kerülnek az AI kontextusába.
- Az automatikus e-mail-küldés nincs engedélyezve; a küldő és utánkövető modulok alapértelmezetten leállnak.
- A Supabase és Gemini hitelesítő adatait kizárólag Codespaces Secrets / Streamlit secrets konfigurációban tárold. Soha ne commitold őket.

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

A projekt korábbi különálló import-, inbox- és e-mail-műveleti szkriptjei nem részei a chatfelületnek. Ne futtasd őket automatikusan. Az e-mailküldés külön, explicit `AUTO_SEND_ENABLED=true` beállítást igényel; maradjon kikapcsolva.

A technikai hozzájárulás-ellenőrzés nem helyettesíti a GDPR/ePrivacy és a célország szerinti marketingjogi ellenőrzést.
