# JARVIS

Magyar nyelvű, Streamlit-alapú üzleti asszisztens. A JARVIS leadkutatást, weboldal-elemzést, üzleti összefoglalókat, feladatkezelést, memóriát, vezetői briefinget és jóváhagyáshoz kötött e-mail-folyamatokat támogat.

## Fejlesztési irány

**Elsőként olvasd el a [JARVIS elsődleges fejlesztési útitervét](docs/JARVIS_DEVELOPMENT_ROADMAP.md).** Ez rögzíti a fejlesztés kötelező sorrendjét, az öt fő célt és a mindenkori haladási állapotot.

## Fő képességek

- Gemini-alapú, magyar nyelvű chat.
- Webes céges leadkutatás, weboldal-audit és leadpontozás.
- Üzleti tanulás, stratégiai összesítés, döntéstámogatás és analitika.
- Leadek, feladatok és üzleti memória kezelése.
- Explicit jóváhagyáshoz kötött feladatműveletek és auditnaplózás.
- Napi vezetői briefing, utánkövetés és proaktív változásfigyelés.
- E-mail-tervezetek, inbox-feldolgozás és SMTP-küldési infrastruktúra; az éles kimenő küldés biztonsági kapcsolóhoz kötött.
- Opcionális Supabase Auth és admin/operator/reader jogosultsági modell; productionben jelenleg nem aktív.

A repositoryban meglévő funkció nem feltétlenül aktív production integráció. A valós külső szolgáltatás és a production adatbázis állapotát külön kell igazolni.

## Technológia

- Python 3.11, Streamlit
- Google Gemini API
- Supabase / PostgreSQL
- GitHub Actions, pytest, Streamlit AppTest, Playwright
- PostgreSQL 17 és pgTAP migrációs integrációs tesztekhez

## Indítás

```bash
python -m pip install -r requirements.txt
streamlit run dashboard.py --server.port 8501
```

Tesztelés:

```bash
python -m pip install -r requirements-test.txt
python -m compileall -q .
python -m pytest -q
```

A szükséges környezeti változókat a kód és a telepítési környezet határozza meg. Tipikus alapkulcsok: `SUPABASE_URL`, szerveroldali Supabase kulcs, `GEMINI_API_KEY`, `JARVIS_DASHBOARD_PASSWORD`. A tényleges konfigurációt titokértékek megosztása nélkül kell ellenőrizni. Titkot soha ne tegyél Gitbe.

## Dokumentáció és AI-fejlesztés

- [Elsődleges fejlesztési útiterv – mindig ezt olvasd először](docs/JARVIS_DEVELOPMENT_ROADMAP.md)
- [AI fejlesztési útmutató](AGENTS.md)
- [JARVIS képességei és architektúrája](docs/JARVIS_DOCUMENTATION.md)
- [Production állapot és migrációs terv](docs/PRODUCTION_STATE_AND_MIGRATION_PLAN.md)
- [Fejlesztési backlog](docs/DEVELOPMENT_REVIEW_AND_RECOMMENDATIONS.md)
- [Production/release kapuk](docs/REMAINING_WORK_AND_RELEASE_GATES.md)

A tartós fejlesztési ág a `main`. A production Supabase migrációs eltéréseket rendezni kell; Auth/RBAC aktiválása és production séma-módosítás csak a dokumentált kapuk lezárása és külön jóváhagyás után történhet.


## Aktuális fejlesztési állapot – 2026-11-25

A jelenlegi munka a [PR #26](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26) ágon folyik (`docs/pre-feature-readiness-gates`). A PR nem merge-ölt. A kód- és tesztváltozások CI-vel igazolt commitja: `38693f2f93b790608aef37a33f190a86e611ff0d` (mindkét job sikeres a `45689264377` futásban). A dokumentációs frissítések utáni PR-head: `a PR oldalon látható aktuális head`; erre a headre új teljes CI-eredmény még nincs. A production migráció, deploy és jogosultságmódosítás továbbra sincs végrehajtva.


- E-mail provider/idempotencia terv: [docs/EMAIL_PROVIDER_IDEMPOTENCY.md](docs/EMAIL_PROVIDER_IDEMPOTENCY.md). A Resend adapter előkészített, de a kimenő küldés továbbra is hard-disabled.
