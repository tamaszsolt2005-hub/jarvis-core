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

A fejlesztés a [PR #26](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26) nyitott ágán folyik (`docs/pre-feature-readiness-gates`); a PR nincs merge-ölve. Az új cég-RPC, CSV-kontaktprioritás és kétfázisú lead write-lockdown kódja a `96d4aa48a312b1942e61bb7c659dce6cdd790b0f` commiton teljes CI-vel igazolt.

- JARVIS CI: Python/AppTest/browser tesztjob sikeres; coverage artifact feltöltve.
- PostgreSQL 17 migráció replay, SQL/pgTAP, két-session cégclaim és backup/restore integráció: sikeres.
- CodeQL: sikeres.
- Dependency vulnerability audit: sikeres.

A PR #26 ágban elkészült a közös, tranzakciós `upsert_company_lead` RPC: a normalizált cégnév és webdomain aliasokat advisory lock védi. A kompatibilis rollout miatt a közvetlen INSERT-jog visszavonása külön, második migrációban történik az új RPC-t használó alkalmazás telepítése után. A CSV-import az összes külön hozzájárulással igazolt emailjelöltet megőrzi, és rangsor alapján választ; a személyes Gmail-jelölt (pl. `xy@gmail.com`) előzi az általános `info@` címet. Már megkezdett kommunikáció után a cím nem cserélhető. A két párhuzamos PostgreSQL session race teszt és a teljes CI még ellenőrzés alatt áll.

A 2026-11-26-i read-only production audit 7 remote migrációt, 8/8 RLS-enabled táblát és 0 RLS-policyt talált; a private schema, alkalmazási RPC-k és production Auth userek hiányoznak. A lead email unique index hiányzik productionből. Az új `20261126120000_atomic_company_lead_identity_and_contact_priority.sql` és `20261126130000_enforce_atomic_company_lead_writes.sql` migrációk kizárólag a PR ágban vannak, productionben nem futottak. A tényleges JARVIS app host/URL továbbra sincs igazolva. Production DDL/DML, GRANT/REVOKE, Auth/RBAC aktiválás, secret-változtatás, deploy és SMTP-küldés nem történt. A kimenő e-mail hard-disabled; a PR merge külön jóváhagyást igényel.
