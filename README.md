# JARVIS

> **AKTUÁLIS FEJLESZTÉSI ÁLLAPOT – 2026-11-27 (PR #34 és PR #35).** A `feature/daily-hard-budget-cap` ág PR #34-e továbbra is open + draft, merged=false. Az Opportunity Engine fejlesztése a `feature/opportunity-center-readonly` ágon, a [PR #35](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/35) részeként található; PR #35 a PR #34-re épül, open + draft, merged=false. A legutóbb ellenőrzött kód-HEAD `8cb080856f745dc5f8278f78a836791a75b48355`; a dokumentációs commitok ezt a HEAD-et tovább fogják mozgatni. Egyik PR sem merge-ölhető külön, konkrét felhasználói engedély nélkül.
>
> **PR #35-ben implementált:** Opportunity Center dashboard; forrásolt céges problémahipotézisek; legalább két különböző vállalathoz kötött, validálható piaci mintázatok; SaaS-jelöltek; hatdimenziós, bizonyítékhoz kötött pontozás; provider-neutral evaluator és session-state előnézet; explicit admin/operator jóváhagyás; immutable, append-only döntési előzmény, idempotenciakulcs, actor/model/version/time és opportunity/pattern snapshot mezők.
>
> **Pontozás:** probléma bizonyítottsága 25%, üzleti érték 20%, fizetési hajlandóság 15%, megvalósíthatóság 15%, újraértékesíthetőség 15%, kockázat 10% fordított irányban. Hiányzó score-dimenzió esetén nincs összpontszám. Minden dimenzióhoz rationale és source evidence szükséges; a hipotézis nem válik automatikusan ténnyé.
>
> **Jogosultság:** hitelesített `admin` és `operator` szerepkör explicit gombnyomással menthet; `reader` csak olvashat; anon nem fér hozzá. A DB trigger ellenőrzi a szerepkört, a validált mintázatot, a két külön céges alátámasztást és a forrás-egyezést. A jóváhagyási előzmény UPDATE/DELETE művelete tiltott. A dashboard user path nem használ service-role írási megkerülést.
>
> **Migrációk:** `20261127100000` core, `20261127110000` scoring, `20261127120000` score evidence, `20261127130000` approval history. Ezek a PR branch részei; production adatbázison nem futottak le. A dashboard nincs production deployolva.
>
> **CI és tesztelés:** a felhasználó kérésére lokális tesztet és kézi CI-dispatch-et nem futtattunk. A kód commitján a GitHub Actions automatikusan indult; a korábbi ellenőrzéskor run `45987043894` folyamatban volt, ez nem jelent zöld CI-t. A dokumentációs commit után az aktuális PR HEAD-hez tartozó legfrissebb CI-t külön kell ellenőrizni. A CI izolált adatbázis, nem production-validáció.
>
> **Következő lépések:** dokumentációs és kód review; a legfrissebb CI eredmény megvárása; Auth/JWT/RLS és migrációk izolált környezetű felülvizsgálata; külön jóváhagyás után staging smoke. Production migration, Auth/RLS éles módosítás, deploy és PR merge továbbra is külön engedélyhez kötött.
Magyar nyelvű, Streamlit-alapú üzleti asszisztens, jelenleg helyi fejlesztés alatt.

**Központi dokumentáció:** [JARVIS Master Documentation](docs/JARVIS_MASTER_DOCUMENTATION.md)  
**Aktuális állapot:** a PR #26, #27 és #28 merge-ölve a `main` ágba. Lásd az [aktuális állapotjelentést](docs/CURRENT_STATE_AND_NEXT_STEPS.md).

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

A snapshot- és worker-migrációk a main ágon vannak; CI-ben izolált PostgreSQL 17 adatbázisban teszteltek. A worker/queue/provider kód implementált, de ütemezett automatikus indítás és élő Gemini/staging futás még nincs bekapcsolva. A teljes SaaS-ötletmotor, globális termék-tiltó napló és automatikus outreach célfunkció, nem kész rendszer.

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
| [Opportunity Engine](docs/OPPORTUNITY_ENGINE.md) | Problémahipotézisek, piaci mintázatok, pontozás és emberi jóváhagyás |
| [SaaS-vízió](docs/JARVIS_AUTONOMOUS_SAAS_VISION.md) | Cégkutatásból egyedi SaaS-ajánlat és fejlesztés |
| [Parancs kalauz](docs/JARVIS_COMMAND_GUIDE.md) | Ténylegesen támogatott chat-parancsok |
| [Fejlesztési backlog](docs/DEVELOPMENT_REVIEW_AND_RECOMMENDATIONS.md) | Technikai hiányok és következő feladatok |
| [Release gate-ek](docs/REMAINING_WORK_AND_RELEASE_GATES.md) | Production előtti kötelező ellenőrzések |
| [Production állapot](docs/PRODUCTION_STATE_AND_MIGRATION_PLAN.md) | Időbélyegzett, read-only production megfigyelések |
| [Főrendszer-készültségi felmérés](docs/JARVIS_MAIN_SYSTEM_READINESS.md) | Core funkciók, készre jelentési kritériumok, hátralévő P0/P1/P2 feladatok |
| [E-mail idempotencia](docs/EMAIL_PROVIDER_IDEMPOTENCY.md) | E-mail provider és retry-korlátok |

## Biztonsági és release szabályok

- A JARVIS alkalmazás nincs production hostra deployolva. A létező Supabase production projekt ettől különálló.
- A kimenő e-mail küldés kódszinten hard-disabled.
- A nyilvános e-mail-cím nem jelent automatikus marketingengedélyt.
- Production Supabase módosítás, migration futtatás, Auth/RBAC, secret, deploy és külső küldés külön, konkrét jóváhagyás nélkül tilos.
- PR merge külön jóváhagyást igényel.
- CI státuszt mindig az aktuális PR head SHA alapján kell ellenőrizni.
- A `.env*` és `.streamlit/secrets.toml` fájlok titkokat tartalmazhatnak; ezeket ne commitold és ne másold chatbe.


## Aktuális implementációs állapot – 2026-11-26

> **Aktuális állapot – 2026-11-26 (a korábbi státuszblokkokat felülírja).** A PR #26, #27 és #28 mind merge-ölve van a `main` ágba. A PR #28 merge commitja: `9ceb2f7fdd0130240c15dc4e1701d3fba1bdb53c`. A PR #28 HEAD-hez tartozó CI #3187 (run `45900450820`) mindhárom jobja sikeres: Python/AppTest/browser tesztek, izolált PostgreSQL 17 worker-integráció, valamint backup–restore/security. A PR #26 HEAD-en a JARVIS CI, CodeQL és dependency audit sikeres; a PR #27 HEAD-en a JARVIS CI sikeres. A merge commiton külön post-merge workflow/státusz nem jelent meg, ezért a merge utáni újrafuttatás nem tekinthető igazoltnak.
>
> **Implementált és CI-vel tesztelt:** cégdosszié és append-only snapshot tárolás; read-only előzmény-dashboard; worker job lifecycle, repository/RPC adapter, queue bridge és worker; injektálható grounded Gemini provider adapter; snapshot mentés a job sikeres lezárása előtt; idempotencia; lease/heartbeat/retry/dead-letter; PostgreSQL lifecycle, kvóta, security és két-session konkurenciatesztek. A CI izolált adatbázist használ, nem productiont.
>
> **Még nincs élesben igazolva / nincs bekapcsolva:** ütemezett automatikus futtatás; a worker schedulerből történő indítása; élő Gemini API/staging smoke; Auth-os snapshot SELECT (a dashboard Auth módban fail-closed, a snapshot tábla service_role-only); teljes manuális helyi dashboard smoke; production app-host és deploy.
>
> **Költségkorlát:** a becsült költségfoglalás, actual-cost settlement callback és tranzakciós elszámolás kódban megvan. A provider adapter nincs élő szolgáltatói hívással validálva, és az actual cost a becslést meghaladhatja; ezért a napi hard cap teljes kikényszerítése még külön feladat.
>
> **Biztonsági határ:** production Supabase migráció/DDL/DML, grant/RLS/Auth módosítás, secret-változtatás, deploy és outbound e-mail nem történt. A kimenő e-mail hard-disabled. A CI-zöld állapot önmagában nem production readiness.
>
> **Következő fókusz:** (1) napi hard budget cap és reservation-overrun védelem; (2) scheduler/operációs vezérlés és worker futtatási életciklus; (3) izolált Auth/JWT/RLS jogosultsági tesztek, különösen snapshot history hozzáférés; (4) élő, nem production Gemini staging smoke usage/grounding/retry/heartbeat ellenőrzéssel; (5) teljes helyi dashboard manuális smoke; (6) production migration drift és hozzáférési modell független felülvizsgálata, majd külön release-döntés.
>
> A dokumentum korábbi PR-állapotai, régi CI-run számai és „nincs worker” megjegyzései történeti feljegyzések; a fenti blokk az aktuális összefoglaló. Részletek: [PR #26](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26), [PR #27](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/27), [PR #28](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/28), [CI #3187](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45900450820).


