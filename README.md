# JARVIS

Magyar nyelvű, Streamlit-alapú üzleti asszisztens, jelenleg helyi fejlesztés alatt.

**Központi dokumentáció:** [JARVIS Master Documentation](docs/JARVIS_MASTER_DOCUMENTATION.md)  
**Aktuális fejlesztési PR:** [#27 – company research phase 1](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/27) – nyitott, nem merge-ölt.  
**Alap PR:** [#26 – readiness gates és termékvízió](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26) – nyitott, nem merge-ölt.

## Mi a JARVIS?

A JARVIS jelenlegi funkciói közé tartozik a magyar nyelvű Gemini chat, a nyilvános forrásokra támaszkodó leadkutatás, a lead scoring, a jóváhagyásos task-kezelés, az üzleti memória, a napi briefing, az analitika és az audit.

A hosszú távú cél egy kutatásvezérelt üzleti ügynök: minden cég valós helyzetét elemzi, egyedi SaaS-terméklehetőséget keres, figyelembe veszi a korábbi elutasításokat és tiltásokat, majd személyre szabott ajánlatot készít. A teljes autonóm pipeline még nincs megvalósítva.

## Jelenlegi cégkutatási fejlesztés

A `feature/company-research-phase-1` ág a következőket tartalmazza:
- grounding-alapú üzleti tények és nyilvános szakmai döntéshozói kontextus;
- forrás/domain ellenőrzés és kompakt cégdosszié;
- snapshot UUID, időbélyeg és SHA-256 tartalomlenyomat;
- append-only kutatási előzménytároló és repository migráció;
- fail-closed dosszié-frissességi szabály;
- read-only refresh candidate planner: stale dossziék kiválasztása, meg nem keresett cégek előresorolása, elutasítások és opt-out kizárása;
- kutatási frissítési jogosultsági policy: elutasítás/opt-out kizárása, két válasz nélküli follow-up utáni szüneteltetés, meg nem keresett leadek megtartása.

A snapshot tároló migrációja csak a feature branchben és a CI izolált adatbázisában szerepel. A refresh policy és a read-only candidate planner még nincs schedulerbe, DB-lekérdező folyamatba vagy workerbe kötve. A teljes SaaS-ötletmotor, globális termék-tiltó napló és automatikus outreach célfunkció, nem kész rendszer.

## Helyi indítás

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

## Dokumentumtérkép

| Dokumentum | Tartalom |
|---|---|
| [Master dokumentáció](docs/JARVIS_MASTER_DOCUMENTATION.md) | A projekt teljes, összevont áttekintése és az aktuális státusz |
| [Aktuális állapot](docs/CURRENT_STATE_AND_NEXT_STEPS.md) | Kész, folyamatban lévő és hátralévő munka |
| [Fejlesztési útiterv](docs/JARVIS_DEVELOPMENT_ROADMAP.md) | Fázisok, prioritások, elfogadási feltételek |
| [Architektúra](docs/JARVIS_DOCUMENTATION.md) | Modulok, adatfolyamok, adatbiztonság |
| [SaaS-vízió](docs/JARVIS_AUTONOMOUS_SAAS_VISION.md) | Cégkutatásból egyedi SaaS-ajánlat és fejlesztés |
| [Parancs kalauz](docs/JARVIS_COMMAND_GUIDE.md) | Ténylegesen támogatott chat-parancsok |
| [Fejlesztési backlog](docs/DEVELOPMENT_REVIEW_AND_RECOMMENDATIONS.md) | Technikai hiányok és következő feladatok |
| [Release gate-ek](docs/REMAINING_WORK_AND_RELEASE_GATES.md) | Production előtti kötelező ellenőrzések |
| [Production állapot](docs/PRODUCTION_STATE_AND_MIGRATION_PLAN.md) | Időbélyegzett, read-only production megfigyelések |
| [E-mail idempotencia](docs/EMAIL_PROVIDER_IDEMPOTENCY.md) | E-mail provider és retry-korlátok |

## Biztonsági és release szabályok

- A JARVIS alkalmazás nincs production hostra deployolva. A létező Supabase production projekt ettől különálló.
- A kimenő e-mail küldés kódszinten hard-disabled.
- A nyilvános e-mail-cím nem jelent automatikus marketingengedélyt.
- Production Supabase módosítás, migration futtatás, Auth/RBAC, secret, deploy és külső küldés külön, konkrét jóváhagyás nélkül tilos.
- PR merge külön jóváhagyást igényel.
- CI státuszt mindig az aktuális PR head SHA alapján kell ellenőrizni.
- A `.env*` és `.streamlit/secrets.toml` fájlok titkokat tartalmazhatnak; ezeket ne commitold és ne másold chatbe.
