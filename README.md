# JARVIS – Chat-first B2B Business Intelligence

A JARVIS egy magyar nyelvű, Streamlit-alapú B2B üzleti intelligencia-asszisztens. Természetes nyelvű chatfelületen keresztül támogatja a céges leadkutatást, üzleti elemzést, feladatkezelést, memóriát, vezetői jelentéseket és a jóváhagyáshoz kötött e-mail-folyamatokat.

## Fő képességek

- Magyar nyelvű chat és Gemini-alapú válaszgenerálás.
- Forrásalapú globális céges leadkutatás és weboldal-audit.
- Leadpriorizálás, üzleti stratégiai összesítések és explicit üzleti memória.
- Jóváhagyásos feladatkezelés, analitika és napi vezetői briefing.
- Jóváhagyott chat e-mail-küldési kísérlet, valamint hozzájárulás-ellenőrzött háttér e-mail- és inbox-folyamatok.
- Proaktív lead- és feladatváltozás-figyelés, rendszerdiagnosztika és auditfunkciók.

**Fontos:** a repositoryban implementált funkció nem feltétlenül jelent aktív, éles integrációt. A Supabase production séma jelenleg eltér a repository migrációs állapotától; az auditmigráció és a teljes üzleti RBAC production bevezetése blokkolt. Az éles, age-titkosított adatbázis-logikai mentés és S3-feltöltés 2026-11-25-én sikeresen ellenőrizve lett; a CI izolált PostgreSQL restore-tesztje is sikeres. A teljes CI-ben egy napi briefing dátumkezelési regresszió javítása után újrafuttatás szükséges.

## Technológia

- Python 3.11, Streamlit
- Google Gemini API
- Supabase / PostgreSQL
- GitHub Actions, pytest, Streamlit AppTest és Playwright

## Telepítés és indítás

Függőségek telepítése:

```bash
python -m pip install -r requirements.txt
```

Alkalmazás indítása:

```bash
streamlit run dashboard.py --server.port 8501
```

A fő működéshez szükséges konfigurációs kulcsok: `SUPABASE_URL`, szerveroldali `SUPABASE_SERVICE_ROLE_KEY` (vagy a régi `SUPABASE_KEY`), `GEMINI_API_KEY` és `JARVIS_DASHBOARD_PASSWORD`. E-mailhez és háttérfolyamatokhoz további titkok és biztonsági kapcsolók szükségesek. **Titokértéket ne tegyél Gitbe vagy dokumentációba.**

Tesztelés:

```bash
python -m pip install -r requirements-test.txt
python -m compileall -q .
python -m pytest -q
```

## Fejlesztési áttekintés és prioritások

A jelenlegi fejlesztési állapot, a PR #13 ellenőrzése, a merge-kritériumok és a javasolt javítási sorrend egy helyen: [Fejlesztési áttekintés és javaslatok](docs/DEVELOPMENT_REVIEW_AND_RECOMMENDATIONS.md). A nyitott feladatok és release gate-ek: [Hátralévő feladatok és release gate-ek](docs/REMAINING_WORK_AND_RELEASE_GATES.md). A hosszú távú fejlesztési alap a `main` ág; a PR ágak átmenetiek.

## Teljes dokumentáció

A projekt architektúrája, funkcióinak állapota, adatmodellje, automatizmusai, biztonsági határai, auditja, mentési terve, tesztjei és nyitott blokkolói egyetlen központi dokumentumban találhatók:

**[JARVIS – teljes projekt- és műszaki dokumentáció](docs/JARVIS_DOCUMENTATION.md)**

A legfrissebb hibák, célzott javítások, CI-állapot és biztonsági kapuk összefoglalója: **[CI és üzemeltetési javítási napló](docs/ci-remediation-status.md)**.

A dokumentációban a kódban implementált, automatikusan tesztelt, integrációsan igazolt és productionben ténylegesen működő állapot külön van kezelve.
