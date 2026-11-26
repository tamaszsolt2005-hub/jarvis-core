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

- [Aktuális állapot és következő lépések](docs/CURRENT_STATE_AND_NEXT_STEPS.md)
- [Elsődleges fejlesztési útiterv – mindig ezt olvasd először](docs/JARVIS_DEVELOPMENT_ROADMAP.md)
- [AI fejlesztési útmutató](AGENTS.md)
- [JARVIS képességei és architektúrája](docs/JARVIS_DOCUMENTATION.md)
- [Production állapot és migrációs terv](docs/PRODUCTION_STATE_AND_MIGRATION_PLAN.md)
- [Fejlesztési backlog](docs/DEVELOPMENT_REVIEW_AND_RECOMMENDATIONS.md)
- [Production/release kapuk](docs/REMAINING_WORK_AND_RELEASE_GATES.md)

A tartós fejlesztési ág a `main`. A production Supabase migrációs eltéréseket rendezni kell; Auth/RBAC aktiválása és production séma-módosítás csak a dokumentált kapuk lezárása és külön jóváhagyás után történhet.




## Aktuális fejlesztési állapot

A JARVIS még nincs telepítve publikus vagy production app-hostra; jelenleg helyi Streamlit dashboardból fejlesztjük. A Supabase production adatbázis létezése nem jelenti az alkalmazás telepítését. A PR #26 nyitott, nem merge-ölt; a legfrissebb állapotot a [PR oldalán](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26) lehet követni. A legfrissebb állapotot és a funkciófejlesztés előtti teendőket az [aktuális állapot és következő lépések](docs/CURRENT_STATE_AND_NEXT_STEPS.md) dokumentum tartalmazza.

A PR #26-ban elkészült a közös, tranzakciós `upsert_company_lead` RPC, a normalizált cégnév/domain aliasok zárolása és a CSV/global research íróútvonalak közös használata. A két-session PostgreSQL konkurenciateszt és a legutóbbi, kódot is tartalmazó teljes PR CI sikeres; a későbbi dokumentációs commitok ellenőrzése a PR checkjein követhető. A kimenő e-mail továbbra is hard-disabled. Production deploy, migráció, Auth/RBAC aktiválás vagy PR merge nem történt.
