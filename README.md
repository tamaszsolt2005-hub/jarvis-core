# JARVIS – Business Intelligence & Sales Operations

A projekt Streamlit dashboardot, Supabase adatbázist és Google Gemini AI-t használ. Az automatikus e-mailküldés biztonsági okból alapértelmezetten ki van kapcsolva.

## Biztonságos telepítés
1. Készíts Supabase adatbázismentést.
2. Futtasd a `supabase/schema.sql` fájlt a Supabase SQL Editorban.
3. Állítsd be a GitHub Actions Secrets értékeit: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY`, `EMAIL_USER`, `EMAIL_PASSWORD`.
4. A Codespaces Streamlit titkokhoz használd a `.streamlit/secrets.toml.example` fájlt mintaként. A valódi titkokat soha ne commitold.
5. Hagyd az `AUTO_SEND_ENABLED=false` értéket, amíg a beállításokat, jogalapot és címzettlistát nem ellenőrizted.

## Lead import
A `lead_gen.py` csak a felülvizsgált `data/leads.csv` fájlt importálja. Kötelező oszlopok: `company_name,email,website,notes,source,consent_basis,approved_to_contact,consent_confirmed_at`. Küldésre csak timestampelt, dokumentált hozzájárulással megjelölt rekord jogosult. A CSV személyes adatokat tartalmazhat, ezért a `.gitignore` kizárja.

## Működés
- `python inbox_monitor.py`: bejövő válaszok ellenőrzése és osztályozása.
- `python lead_gen.py`: felülvizsgált CSV import.
- `python email_sender.py`: első levelek (csak explicit engedélyezéskor).
- `python follow_up.py`: esedékes utánkövetés (csak explicit engedélyezéskor).
- `streamlit run dashboard.py`: dashboard a 8501-es porton.

A technikai hozzájárulás-ellenőrzés nem helyettesíti a GDPR/ePrivacy és a célország szerinti marketingjogi ellenőrzést. Használj jogszerű adatforrást, átlátható azonosítást és egyértelmű leiratkozási lehetőséget.
