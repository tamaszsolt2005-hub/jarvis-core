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

A fejlesztés a [PR #26](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26) nyitott ágán folyik (`docs/pre-feature-readiness-gates`). A legutóbbi dokumentációs head: `4e53eb19acb1d4859a7e0964a8d0e10cdc0f6322`; a PR nincs merge-ölve. A teljes CI/CodeQL/dependency auditot igazoló kód- és dokumentációs head: `7c8e6970a733884f4423821cddf3731f58e5b392`. Az azóta következő commitok dokumentációs korrekciók; ezekhez még nincs visszaigazolt új workflow-eredmény.

A headhez tartozó ellenőrzések mind sikeresek:
- JARVIS CI: tesztek és backup/restore integráció.
- CodeQL Python statikus elemzés.
- pip-audit a `requirements-test.txt` alapján (runtime és tesztfüggőségek).

További repós védelem: heti Dependabot frissítési ellenőrzés Python- és GitHub Actions-függőségekre. A sikeres CI nem igazolja a production deployt, a production Supabase-sémát vagy az SMTP-hitelesítést.

E-mail: a kiválasztott útvonal Gmail SMTP (`EMAIL_PROVIDER=smtp`); a GitHub workflow az `EMAIL_USER` és `EMAIL_PASSWORD` secretneveket használja. A kimenő küldés továbbra is kódszinten hard-disabled, az outbound workflow-lépés tiltott. A Resend adapter alternatív kódútvonal, nem az aktív provider.

Production deploy, adatbázis-migráció, GRANT/REVOKE, Auth/RBAC-változtatás és e-mail-küldés nem történt. A production host továbbra sem igazolt.
