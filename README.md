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




## Aktuális fejlesztési állapot – 2026-11-26

A fejlesztés a [PR #26](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26) nyitott ágán folyik (`docs/pre-feature-readiness-gates`); a PR nincs merge-ölve. A 2026-11-26-án CI-vel igazolt commit `79dfb5b85afaa3ae21405b295bb23880019ec54d`; az ezt követő változtatások dokumentációs frissítések. Ezen a commiton a CI 838 tesztet sikeresen futtatott (3 kihagyott), 91,29%-os lefedettséggel; a PostgreSQL 17 backup–restore integráció, CodeQL és dependency audit is sikeres.

- JARVIS CI: **838 passed, 3 skipped, 0 failed**, 91.29% coverage.
- PostgreSQL 17 izolált migrációs/pgTAP és backup/restore integráció: sikeres.
- CodeQL: sikeres.
- pip-audit: sikeres.

A global lead research név/domain deduplikációja jelenleg alkalmazásszintű; párhuzamos worker-ek között nincs DB-szintű atomikus garancia. Nem alkalmaztunk kockázatos cégnév/domain unique indexet; a tranzakciós DB/RPC claim megoldás tervezése nyitott. A részleteket és a release gate-eket az elsődleges [fejlesztési útiterv](docs/JARVIS_DEVELOPMENT_ROADMAP.md) rögzíti.

A 2026-11-26-i friss read-only production Supabase audit 7 remote migrációt, 8/8 RLS-enabled táblát és 0 RLS-policyt talált; a private schema, alkalmazási RPC-k és production Auth userek hiányoznak. A `leads_email_normalized_uidx` index és migráció nincs productionben, bár a jelenlegi 11 lead között nem volt normalizált email-duplikáció. A tényleges JARVIS app host/URL továbbra sincs igazolva. Production migráció/írás, GRANT/REVOKE, Auth/RBAC aktiválás, secret-változtatás, SMTP-küldés nem történt. A kimenő e-mail hard-disabled; a PR merge külön jóváhagyást igényel.
