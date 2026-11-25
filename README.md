# JARVIS – Chat-first B2B Business Intelligence

A JARVIS egy magyar nyelvű, Streamlit-alapú B2B üzleti intelligencia-asszisztens. Természetes nyelvű chatfelületen keresztül támogatja a céges leadkutatást, üzleti elemzést, feladatkezelést, memóriát, vezetői jelentéseket és a jóváhagyáshoz kötött e-mail-folyamatokat.

## Fő képességek

- Magyar nyelvű chat és Gemini-alapú válaszgenerálás.
- Forrásalapú globális céges leadkutatás és weboldal-audit.
- Leadpriorizálás, üzleti stratégiai összesítések és explicit üzleti memória.
- Jóváhagyásos feladatkezelés, analitika és napi vezetői briefing.
- Jóváhagyott chat e-mail-küldési kísérlet, valamint hozzájárulás-ellenőrzött háttér e-mail- és inbox-folyamatok.
- Proaktív lead- és feladatváltozás-figyelés, rendszerdiagnosztika és auditfunkciók.

**Fontos:** a repositoryban implementált funkció nem feltétlenül jelent aktív, éles integrációt. A Supabase production séma jelenleg eltér a repository migrációs állapotától; az auditmigráció és a teljes üzleti RBAC production bevezetése blokkolt. A valós e-mail-kézbesítés és az adatbázis-mentés/visszaállítás sincs igazolva.

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

## Teljes dokumentáció

A projekt architektúrája, funkcióinak állapota, adatmodellje, automatizmusai, biztonsági határai, auditja, mentési terve, tesztjei és nyitott blokkolói egyetlen központi dokumentumban találhatók:

**[JARVIS – teljes projekt- és műszaki dokumentáció](docs/JARVIS_DOCUMENTATION.md)**

A dokumentációban a kódban implementált, automatikusan tesztelt, integrációsan igazolt és productionben ténylegesen működő állapot külön van kezelve.


## Fejlesztési és élesítési állapot

A PR #13 Auth/RBAC és a production migráció/backup jelenlegi blokkolói,
valamint a következő feladatok a
[prioritásos hiány- és élesítési listában](docs/REMAINING_WORK_AND_RELEASE_GATES.md)
követhetők. A CI-eredmények és azok korlátai:
[PR #13 CI-validáció](docs/PR13_CI_VALIDATION_2026-11-24.md).

## Aktuális migrációs és production állapot

- [Friss production read-only ellenőrzés](docs/PRODUCTION_REVALIDATION_2026-11-24_1851UTC.md)
- [Supabase migrációs drift és helyreállítási terv](docs/SUPABASE_MIGRATION_DRIFT_RECONCILIATION.md)
- [Hátralévő feladatok és élesítési kapuk](docs/REMAINING_WORK_AND_RELEASE_GATES.md)
- [Legfrissebb PR #13 CI-eredmények](docs/PR13_CI_VALIDATION_2026-11-24.md)

A jelenlegi PR #13 head (`e6736101405180c220d6b96b5a7a3c1d890813e0`) teljesen zöld CI-eredménye: **762 passed, 3 skipped, 96.47% coverage**. A PostgreSQL 17 + pgTAP és izolált age backup/restore integráció szintén sikeres. Ez nem helyettesíti a production backupot vagy a valós Supabase Auth/RLS validációt. Részletek a [PR #13 CI-validációs naplóban](docs/PR13_CI_VALIDATION_2026-11-24.md).


## Production Supabase validation artifacts

- [2026-11-25 production schema snapshot](docs/PRODUCTION_SCHEMA_SNAPSHOT_2026-11-25.md)
- [Migration drift and reconciliation](docs/SUPABASE_MIGRATION_DRIFT_RECONCILIATION.md)
- [Production recovery and backup/restore plan](docs/production-migration-recovery.md)

The repository now contains a manual live Auth/JWT/RLS smoke workflow for a disposable Supabase branch and a production backup workflow that verifies an encrypted S3 object and restores it into a separate PostgreSQL 17 target. Neither workflow changes the production schema. Required secrets and the isolated test branch must be configured before execution.
