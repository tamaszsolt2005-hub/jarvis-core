# JARVIS – Chat-first B2B Business Intelligence

A JARVIS egy magyar nyelvű, Streamlit-alapú B2B üzleti intelligencia-asszisztens. A felhasználó természetes nyelven kérdezhet; az alkalmazás a kérdéshez szükséges üzleti adatokat a Supabase-ből olvassa, és a Gemini modell segítségével készít választ.

## Fő képességek

- **Chat és üzleti elemzés:** magyar nyelvű kérdések, kérdésfüggő adatlekérés és adaptív válaszhossz.
- **Globális céges leadkutatás:** forrásokkal alátámasztott céges kutatás, célpiac és keresési brief kezelése. A kutatás önmagában nem jelent kapcsolatfelvételi engedélyt.
- **Weboldal-audit és prioritás:** nyilvános céges weboldalak biztonságos vizsgálata, információgazdagsági pontszám és kutatási prioritás.
- **Üzleti stratégia és tanulás:** iparági összesítések, kifejezetten elmentett döntések és tapasztalatok felhasználása.
- **Hosszú távú memória:** csak kifejezett felhasználói utasításra ment és módosít emlékeket.
- **Feladatkezelés:** feladat létrehozása, módosítása és lezárása előnézet és külön jóváhagyás után.
- **Analitika és vezetői jelentés:** naplóadatokon alapuló dashboard-analitika és determinisztikus jelentés.
- **E-mail:** chatből e-mail-tervezet készítése; a címzett, tárgy és teljes szöveg előnézete után külön jóváhagyással küldési kísérlet indítható. Külön háttér-automatizmus is létezik hozzájárulás-ellenőrzéssel és utánkövetési korlátokkal.

## Fontos működési és biztonsági szabályok

- A normál üzleti adatlekérdezések olvasásközpontúak. A módosítást végző, támogatott chatműveletek külön jóváhagyást igényelnek.
- A leadkutatás nem ad automatikus marketing-hozzájárulást.
- Chatből e-mail csak pontosan megadott címzettel, látható előnézettel, külön felhasználói jóváhagyással és aktív szerveroldali kapcsolókkal küldhető.
- A háttérküldés külön folyamat; csak érvényes, időbélyegzett hozzájárulás, jóváhagyott kapcsolatfelvétel és leiratkozás hiánya mellett futhat.
- A titkok kizárólag szerveroldali környezeti változókban vagy titokkezelőben tárolhatók. Ne commitolj jelszót, API-kulcsot vagy service-role kulcsot.
- A teszt vagy a környezeti változó megléte önmagában nem bizonyít éles külső szolgáltatáskapcsolatot vagy sikeres e-mail-kézbesítést.

## Technológia

- Python 3.11
- Streamlit
- Google Gemini API
- Supabase (PostgreSQL)
- GitHub Actions automatizmusok és CI

A tényleges modell alapértelmezése a `jarvis_common.py` fájlban `gemini-3.8-flash`; a `GEMINI_MODEL` beállítással felülírható.

## Telepítés és indítás

Telepítsd a függőségeket:

```bash
python -m pip install -r requirements.txt
```

A Streamlit alkalmazás indítása:

```bash
streamlit run dashboard.py --server.port 8501
```

## Konfiguráció

A fő alkalmazáshoz szükséges szerveroldali beállítások:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` vagy megfelelő jogosultságú `SUPABASE_KEY`
- `GEMINI_API_KEY`
- `JARVIS_DASHBOARD_PASSWORD`

E-mailhez további konfiguráció szükséges, többek között `EMAIL_USER`, `EMAIL_PASSWORD`, SMTP/IMAP-kiszolgáló-beállítások és a megfelelő biztonsági kapcsolók.

A chatből indított küldés kapcsolói:
- `EMAIL_DELIVERY_ENABLED=true`
- `CHAT_EMAIL_ENABLED=true`

A háttérküldés további kapcsolói:
- `AUTO_SEND_ENABLED=true`
- `EMAIL_INBOX_MONITOR_ENABLED=true`

A kapcsolók alapértelmezése biztonsági okból kikapcsolt. A Codespaces Secrets és a GitHub Actions Secrets külön környezetek; egyik nem helyettesíti automatikusan a másikat. A titkok értékét soha ne tedd dokumentációba vagy Gitbe.

## Adatbázis-mentés és visszaállítás

A titkosított Supabase-mentési és kizárólag elkülönített, üres tesztprojektbe engedélyezett visszaállítási eljárást a [DATABASE_BACKUP_RESTORE.md](docs/DATABASE_BACKUP_RESTORE.md) dokumentálja. A napi workflow külső adatbázis-kapcsolat, age kulcs, privát S3 tárhely és AWS OIDC konfiguráció nélkül kihagyja a mentést. A GitHub-repozitórium nem tárol adatbázis-mentést.

## Tesztelés

```bash
python -m compileall -q .
python -m pytest -q
```

A mockolt egységtesztek nem helyettesítik a Gemini-, Supabase-, SMTP- és IMAP-integrációk kontrollált, éles tesztjét.

## Dokumentáció

- [Projektállapot](docs/PROJECT_STATUS.md) – aktuálisan elkészült, tesztelt, ellenőrzött és még nyitott feladatok.
- [Műszaki dokumentáció](docs/TECHNICAL_DOCUMENTATION.md) – architektúra, modulok, adatfolyamok, adatmodell és biztonsági szabályok.
- [Adatbázis-mentés és visszaállítás](docs/DATABASE_BACKUP_RESTORE.md) – titkosított mentés, tárolás és izolált visszaállítás.

**Dokumentációs irányelv:** a README a felhasználói áttekintés és indítási útmutató. A változó teszt- és üzemállapotot ne másold ide; azt a PROJECT_STATUS dokumentumban tartsd naprakészen.
