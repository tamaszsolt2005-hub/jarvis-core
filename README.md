## Leadkezelő

A Leadkezelő számozott, a meglévő 0–100-as kutatási prioritás szerint rendezett leadkártyákat, forrásolt cégdossziékat, emberi jóváhagyást/elutasítást és elutasított leadek AI-megbeszélését biztosítja. Részletek: [Lead Review Workflow](docs/LEAD_REVIEW_WORKFLOW.md). A jóváhagyás nem ad kapcsolatfelvételi hozzájárulást és nem küld e-mailt.

> **HITeles, frissített állapot – 2026-11-27 13:37 CET.** Ez a státuszblokk a dokumentum alábbi korábbi, dátumozott állapotjelentéseit felülírja. A vizsgált kód a `feature/opportunity-center-readonly` branch PR #35-ös állapota, HEAD: `f90225235b804ca0d13930d11bbf1f1ae627e9f2`. PR #35 nyitott, Draft, nem merge-ölt; a PR #34-re épül. A HEAD-hez tartozó automatikus JARVIS CI run `45999509740` befejeződött `success` eredménnyel. A felhasználó kérésének megfelelően lokális tesztet és kézi CI-dispatch-et nem futtattunk. Ez a CI az izolált tesztkörnyezetet igazolja, nem production üzemet.
>
> **Kész a kódban (PR #35):** Opportunity Engine adatmodell és dashboard; céges problémahipotézisek és legalább két külön céghez kötött validált piaci mintázatok; SaaS-jelöltek; hatdimenziós, forrásbizonyítékhoz kötött scoring; evaluator preview session state-ben; explicit admin/operator jóváhagyás és append-only assessment history; közös `intelligence_engine.py` evidence/provenance szerződés és append-only `intelligence_evidence` index Lead-, dossier- és pain-forrásokhoz; Intelligence áttekintő; származtatott Intelligence Graph és Graphviz dashboardfül. A gráf forrásai a domain táblák, az AI által kitalált kapcsolatok nem válnak automatikusan igazolt élekké. A gráf Python projection determinisztikus, duplikált node ID esetén bemenet-sorrendtől függetlenül választ rekordot.
>
> **Biztonsági és release-határ:** a PR #35 migrációi csak a repository/CI részei; production adatbázison nem futottak le. A dashboard nincs production deployolva. Az assessment preview nem ment automatikusan; a mentés explicit admin/operator jóváhagyás. A dashboard authenticated/RLS útvonalat használ, nincs service-role write bypass. A PR merge, production migráció, Auth/RLS éles módosítás és deploy külön, konkrét engedélyt igényel.
>
> **Pontosítás a már meglévő kutatási pipeline-ról:** a cégfelderítés és a kutatási worker nem hiányzó funkció. A `global_lead_research.py` grounded, országválasztásos cégeket keres és leadként ment; a dossier/snapshot réteg forrásolt cégprofilt állít elő; a `company_research_worker.py` egy job queue/claim/lease/heartbeat/retry/dead-letter életciklust kezel; a `company_research_execution.py` a provider→dossier→snapshot→lead mentési útvonalat köti össze; a `company_research_runtime.py` explicit hívásra egy worker jobot futtat végig. Ezek kódoldali elemei CI-ben teszteltek, de schedulerből történő folyamatos futtatás és élő Gemini/staging smoke nincs igazolva. **A tényleges hiányzó összekötő réteg:** a már mentett Lead/dossier/pain adatokból automatikusan vagy egyértelműen indítható, end-to-end cross-company pattern discovery → SaaS candidate generation → evaluation/approval folyamat; különösen annak bizonyítása, hogy a pain-ek több cég között megbízhatóan csoportosulnak és a pattern/opp rekordok létrejönnek. Emellett hiányzik a folyamatos scheduleres kutatás, valós ügyfélinterjú/fizetési hajlandóság-validáció, élő staging/provider smoke és production release. A már meglévő cégkutatási/worker rendszert újraépíteni nem cél.
>
> **Javasolt következő sorrend:** (1) PR #34/#35 kód-, migráció-, RLS- és dokumentációs review, stacked PR függőség tisztázása; (2) izolált staging környezetben Auth/JWT/RLS és migráció smoke, production érintése nélkül; (3) Opportunity Discovery adatfolyam első, kézi/explicit indítású vertical slice-e: kiválasztott cégek → grounded kutatás → dossier/evidence → pain hypothesis → market pattern; (4) adatminőségi és evidence-minimum szabályok, mintázat deduplikáció és emberi validáció; (5) ügyfélinterjúk/fizetési hajlandóság validálása, majd SaaS-jelölt értékelés; (6) csak ezután scheduler/automatizálás és release-terv. Tesztet helyben nem futtatunk, kézi CI-dispatch nincs.

---

# JARVIS

> **AKTUÁLIS FEJLESZTÉSI ÁLLAPOT – 2026-11-27 (PR #34 és PR #35).** A `feature/daily-hard-budget-cap` ág PR #34-e továbbra is open + draft, merged=false. Az Opportunity Engine fejlesztése a `feature/opportunity-center-readonly` ágon, a [PR #35](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/35) részeként található; PR #35 a PR #34-re épül, open + draft, merged=false. A PR aktuális HEAD-jét és a hozzá tartozó automatikus CI-állapotot a GitHub PR-oldalán kell ellenőrizni; korábbi SHA zöld CI-je nem igazolja az újabb commitokat. Egyik PR sem merge-ölhető külön, konkrét felhasználói engedély nélkül.
>
> **PR #35-ben implementált:** központi, append-only `intelligence_evidence` bizonyítéktár a Lead-, cégdosszié- és Opportunity-forrásokhoz; pontos Google-grounding URL-ellenőrzés; Intelligence áttekintő dashboardfül; Opportunity Center dashboard; forrásolt céges problémahipotézisek; legalább két különböző vállalathoz kötött, validálható piaci mintázatok; SaaS-jelöltek; hatdimenziós, bizonyítékhoz kötött pontozás; provider-neutral evaluator és session-state előnézet; explicit admin/operator jóváhagyás; immutable, append-only döntési előzmény, idempotenciakulcs, actor/model/version/time és opportunity/pattern snapshot mezők.
>
> **Pontozás:** probléma bizonyítottsága 25%, üzleti érték 20%, fizetési hajlandóság 15%, megvalósíthatóság 15%, újraértékesíthetőség 15%, kockázat 10% fordított irányban. Hiányzó score-dimenzió esetén nincs összpontszám. Minden dimenzióhoz rationale és source evidence szükséges; a hipotézis nem válik automatikusan ténnyé.
>
> **Jogosultság:** hitelesített `admin` és `operator` szerepkör explicit gombnyomással menthet; `reader` csak olvashat; anon nem fér hozzá. A DB trigger ellenőrzi a szerepkört, a validált mintázatot, a két külön céges alátámasztást és a forrás-egyezést. A jóváhagyási előzmény UPDATE/DELETE művelete tiltott. A dashboard user path nem használ service-role írási megkerülést.
>
> **Migrációk:** `20261127100000` core, `20261127110000` scoring, `20261127120000` score evidence, `20261127130000` approval history, `20261127140000` központi Intelligence evidence store. Ezek a PR branch részei; production adatbázison nem futottak le. A dashboard nincs production deployolva.
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
| [Opportunity Engine](docs/OPPORTUNITY_ENGINE.md) | Problémahipotézisek, közös Intelligence Engine provenance, piaci mintázatok, pontozás és emberi jóváhagyás |
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

## Intelligence Graph

A Leadek, cégdossziék, problémahipotézisek, piaci mintázatok, SaaS-jelöltek, jóváhagyott értékelések és forrásbizonyítékok közötti kapcsolatok külön, származtatott gráfrétegben jelennek meg. A gráf az eredeti üzleti táblákból épül, azokat nem helyettesíti. Részletek: [Intelligence Graph architektúra](docs/INTELLIGENCE_GRAPH.md).


## Lead e-mail workflow

A jóváhagyott leadekhez személyre szabott, szerkeszthető e-mail-piszkozat készíthető. A piszkozat külön jóváhagyása, a kötelező elutasítási visszajelzés és a strukturált globális stílusprofil részletei: [Lead Email Draft and Approval Workflow](docs/LEAD_EMAIL_WORKFLOW.md). A küldési kódzár változatlanul aktív; a jóváhagyott e-mailek nem kerülnek automatikus küldésre.

## Rendszerállapot és fejlesztési hiányok

- [JARVIS központi rendszer- és összeszerelési dokumentáció](docs/JARVIS_MASTER_DOCUMENTATION.md)
- [JARVIS képességhiány- és prioritási jelentés](docs/JARVIS_CAPABILITY_GAP_REPORT.md) – mi működik már, mi nincs még kész, és milyen sorrendben érdemes továbbfejleszteni.


## Automatikus Opportunity Discovery

A napi cégkutatási worker a forrásolt dossier-okból strukturált problémahipotéziseket ment, majd determinisztikusan keresi a több cégnél ismétlődő mintázatokat. Az eredmény csak `candidate` piaci minta és `draft` SaaS-jelölt; validálás, pontozás és jóváhagyás emberi döntés. Részletek: [Opportunity Engine pipeline](docs/OPPORTUNITY_ENGINE.md).

## CRM – ügyfél-életciklus

A jóváhagyott leadek kézzel követhető státuszai, interakciós naplója és következő teendői: [CRM ügyfél-életciklus dokumentáció](docs/LEAD_CUSTOMER_LIFECYCLE.md). A folyamat nem küld e-mailt és nem válaszol automatikusan az ügyfeleknek.


## Kutatási worker üzemeltetése

- [Kutatási worker műveletek és pause/resume](docs/RESEARCH_WORKER_OPERATIONS.md)


## Fejlesztési állapot – 2026-11-27 18:05 CET

> Ez a frissítés a fenti, korábbi dátumozott státuszoknál újabb, célzott UI- és dokumentációs változásokat rögzíti. Nem állítja, hogy a PR aktuális HEAD-je vagy CI-je most ellenőrizve lett.

- **Lead Intelligence Center:** a Leadkezelő kétpaneles elrendezést kapott: bal oldali kereshető/szűrhető leadlista, jobb oldali kiválasztott lead részletező panel. A változtatások a `feature/opportunity-center-readonly` ágon: alap UI-frissítés `1e933a81dc1c3812ff408f32702d942bc10d03b4`, kétpaneles szerkezet `a2dbfda7a88e8c5a53fad1b3b8d051793bf0bfcf`, keresés bekötése `8e4ae2b56f588d39b0c523965dee9809efc7046b`.
- **Analitika:** a mai és korábbi események időbélyege külön formátumot használ, így a régebbi esemény nem tűnik jövőbelinek. Commit: `cfb1da6d39b67ee02516c54759806738f14b064a`.
- **E-mail központ:** javítva a jóváhagyott, elutasított, stílusprofil és engedélyek/küldési sor fülek tartalmának index-hozzárendelése. Commit: `5962eda938c2f3950097c3c24b0a2b0fb22cf717`.
- **Ellenőrzési korlát:** a fenti módosítások GitHub-fájl-visszaolvasással ellenőrizve; böngészős megjelenítés nem igazolt. A felhasználó kérésére külön tesztet nem futtattunk. Merge és deploy nem történt.
- **Adatállapot értelmezése:** a legutóbb ellenőrzött production pillanatképben 11 lead mellett nem volt strukturált grounding source és nem volt cégkutatási snapshot; 0 jóváhagyott lead és 0 e-mail-piszkozat szerepelt. Ezért a Lead pontozatlansága és az E-mail/CRM üres állapota önmagában nem UI-hiba. A Feladatközpont 0-s adatbázis-állapota ehhez a frissítéshez nem lett újra lekérdezve.

Részletes képernyő- és fejlesztési terv: [Lead Intelligence Center](docs/LEAD_INTELLIGENCE_CENTER.md).
