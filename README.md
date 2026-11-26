# JARVIS

Magyar nyelvű, Streamlit-alapú üzleti asszisztens. A rendszer jelenlegi fejlesztési ága a PR #26; a JARVIS alkalmazás helyi fejlesztés alatt áll, production alkalmazás-hostra nincs telepítve.

## Első lépések
1. Olvasd el a [fejlesztési útitervet](docs/JARVIS_DEVELOPMENT_ROADMAP.md).
2. A tényleges jelenlegi állapotot az [aktuális állapot dokumentum](docs/CURRENT_STATE_AND_NEXT_STEPS.md) írja le.
3. A beírható, ténylegesen támogatott parancsokat a [Parancs- és kifejezéskalauz](docs/JARVIS_COMMAND_GUIDE.md) mutatja be.
4. A komponensek, adatfolyamok és biztonsági határok a [műszaki dokumentációban](docs/JARVIS_DOCUMENTATION.md) találhatók.

## Fő képességek a PR #26 fejlesztési ágban
- Magyar nyelvű Gemini-alapú chat és kontextus-összeállítás.
- Explicit kérésre indított céges leadkutatás, nyilvános grounding-forrásokkal; célpiac-választás és legfeljebb 15 új cég kutatási futásonként.
- Cégazonosítás és deduplikáció: normalizált cégnév/domain aliasok, tranzakciós upsert_company_lead RPC, párhuzamos írás elleni DB-zár.
- Leadpontozás, kutatási bizonyosság és belső következőfeladat-ajánlás.
- Jóváhagyásos feladatkezelés: létrehozás, módosítás, lezárás; egyszer használatos, principal- és payload-kötött approval; atomikus végrehajtás és operation ID-alapú replay-védelem.
- Feladatközpont: szűrhető/rendezhető, read-only feladatlista és consent-aware, read-only utánkövetési sor.
- Eredményalapú következő teendő: lezárt eredménymérési task explicit pozitív/negatív/nincs válasz besorolásából belső javaslat.
- Hosszú távú üzleti memória: explicit parancsra mentés/listázás/inaktiválás; döntés, eredmény és tanulság külön kategóriában.
- Napi briefing, analitika, audit és üzleti kontextus.
- E-mail/inbox komponensek; a kimenő e-mail küldés kódszinten hard-disabled.
- Opcionális Supabase Auth/RBAC admin/operator/reader szerepkörökkel; production aktiválás nincs igazolva.

Ezek a képességek a fejlesztési ág kódbeli funkciói, nem production szolgáltatási ígéretek. A tényleges parancsok, előfeltételek és korlátozások: [Parancs- és kifejezéskalauz](docs/JARVIS_COMMAND_GUIDE.md).

## Technológia
Python 3.11, Streamlit, Google Gemini API, Supabase/PostgreSQL, GitHub Actions, pytest, Streamlit AppTest, Playwright, PostgreSQL 17 és pgTAP.

## Helyi indítás
    python -m pip install -r requirements.txt
    streamlit run dashboard.py --server.port 8501

Tesztelés:
    python -m pip install -r requirements-test.txt
    python -m compileall -q .
    python -m pytest -q

Titokértéket ne másolj chatbe, naplóba vagy Gitbe. A .env* és .streamlit/secrets.toml fájlok kizártak a verziókezelésből.

## Dokumentumtérkép
| Dokumentum | Mire való |
|---|---|
| [Fejlesztési útiterv](docs/JARVIS_DEVELOPMENT_ROADMAP.md) | Fejlesztési irány és prioritások |\n| [Önálló SaaS-ügynök vízió](docs/JARVIS_AUTONOMOUS_SAAS_VISION.md) | Automatikus cégkutatás, egyedi SaaS-ajánlat, tiltó napló, személyes outreach és AI-termékfejlesztés célarchitektúrája |
| [Aktuális állapot](docs/CURRENT_STATE_AND_NEXT_STEPS.md) | Mi van kész, mi fut, mi nincs telepítve |
| [Parancs- és kifejezéskalauz](docs/JARVIS_COMMAND_GUIDE.md) | Magyar parancsok, példák, jóváhagyás |
| [Rendszer- és architektúra-dokumentáció](docs/JARVIS_DOCUMENTATION.md) | Modulok, adatfolyamok, jogosultságok |
| [Fejlesztési backlog](docs/DEVELOPMENT_REVIEW_AND_RECOMMENDATIONS.md) | Hiányzó funkciók és műszaki munka |
| [Production állapot és migrációs terv](docs/PRODUCTION_STATE_AND_MIGRATION_PLAN.md) | Időbélyegzett read-only production megfigyelések |
| [Release gate-ek](docs/REMAINING_WORK_AND_RELEASE_GATES.md) | Élesítés előtti ellenőrzések |
| [E-mail provider/idempotencia](docs/EMAIL_PROVIDER_IDEMPOTENCY.md) | E-mail állapot és retry-korlátok |
| [Fejlesztői/AI ügynök útmutató](AGENTS.md) | Repo-munkavégzési szabályok |

## Fejlesztési és release szabályok
- A PR #26 nyitott és nem merge-ölt; a fejlesztés a docs/pre-feature-readiness-gates ágon történik.
- A PR CI állapotát mindig az aktuális head SHA-hoz kell kötni; régi zöld futás nem igazolja az újabb commitokat.
- A Supabase production DB létezése nem jelenti a JARVIS alkalmazás deployját.
- Production migráció, DDL/DML, GRANT/REVOKE, Auth/RBAC aktiválás, secretmódosítás, deploy és e-mailküldés külön, konkrét jóváhagyás nélkül tilos.
- A PR merge külön jóváhagyást igényel.
