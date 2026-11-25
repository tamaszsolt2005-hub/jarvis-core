# JARVIS – Chat-first B2B Business Intelligence

A JARVIS egy magyar nyelvű, Streamlit-alapú B2B üzleti intelligencia-asszisztens. Természetes nyelvű chatfelületen keresztül támogatja a céges leadkutatást, üzleti elemzést, feladatkezelést, memóriát, vezetői jelentéseket és a jóváhagyáshoz kötött e-mail-folyamatokat.

## Fő képességek

- Magyar nyelvű chat és Gemini-alapú válaszgenerálás.
- Forrásalapú globális céges leadkutatás és weboldal-audit.
- Leadpriorizálás, üzleti stratégiai összesítések és explicit üzleti memória.
- Jóváhagyásos feladatkezelés, analitika és napi vezetői briefing.
- Jóváhagyott chat e-mail-küldési kísérlet, valamint hozzájárulás-ellenőrzött háttér e-mail- és inbox-folyamatok.
- Proaktív lead- és feladatváltozás-figyelés, rendszerdiagnosztika és auditfunkciók.

**Fontos:** a repositoryban implementált funkció nem feltétlenül jelent aktív, éles integrációt. A Supabase production séma jelenleg eltér a repository migrációs állapotától; az auditmigráció és a teljes üzleti RBAC production bevezetése blokkolt. Az éles, age-titkosított adatbázis-logikai mentés és S3-feltöltés 2026-11-25-én sikeresen ellenőrizve lett; a CI izolált PostgreSQL restore-tesztje is sikeres. A main aktuális teljes CI-futása (45617334463) mindkét jobbal sikeres; a PR #13 négy fájl-összevezető commitja után új, külön PR CI-futás indult.

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

A legfrissebb hibák, célzott javítások, CI-állapot és biztonsági kapuk összefoglalója: **[CI és üzemeltetési javítási napló](docs/ci-remediation-status.md)**.

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

A `e6736101405180c220d6b96b5a7a3c1d890813e0` commiton mért **762 passed, 3 skipped, 96.47% coverage** történeti CI-baseline, nem a jelenlegi PR-head eredménye. A main újabb teljes CI-futása [45617334463](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45617334463) mindkét jobbal sikeres. A PR #13 négy fájl-összevezető commitja után a friss PR CI futása külön ellenőrzendő. Ez nem helyettesíti a valós Supabase Auth/RLS validációt. Részletek a [PR #13 CI-validációs naplóban](docs/PR13_CI_VALIDATION_2026-11-24.md).


## Production Supabase validation artifacts

- [2026-11-25 production schema snapshot](docs/PRODUCTION_SCHEMA_SNAPSHOT_2026-11-25.md)
- [Migration drift and reconciliation](docs/SUPABASE_MIGRATION_DRIFT_RECONCILIATION.md)
- [Production recovery and backup/restore plan](docs/production-migration-recovery.md)

The repository contains a manually triggered Auth/JWT/RLS smoke workflow intended only for an already-existing, explicitly authorized isolated Supabase environment; it must not create a new project or branch and must never target production. The production backup workflow completed successfully on 2026-11-25 (run 45611038142): it uploaded the age-encrypted logical dump to S3 with SSE-KMS, downloaded it, decrypted it and verified the manifest hashes. The separate PostgreSQL 17 CI restore round-trip also passed in run 45617334463. Neither workflow applies production schema changes. Real Auth/JWT/RLS validation remains unrun.


## Fejlesztési áttekintés és prioritások

A fejlesztési javaslatok és ellenőrzött státuszuk egyetlen helyen: [Fejlesztési áttekintés és javaslatok](docs/DEVELOPMENT_REVIEW_AND_RECOMMENDATIONS.md). A merge és production release gate-ek: [Hátralévő feladatok és release gate-ek](docs/REMAINING_WORK_AND_RELEASE_GATES.md). A hosszú távú fejlesztési alap a `main`; a PR ágak átmenetiek.
