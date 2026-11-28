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

# JARVIS – rendszer- és architektúra-dokumentáció

> **Aktuális állapot – 2026-11-26 (a korábbi státuszblokkokat felülírja).** A PR #26, #27 és #28 mind merge-ölve van a `main` ágba. A legutóbbi main commit: `9ceb2f7fdd0130240c15dc4e1701d3fba1bdb53c`. A PR #28 HEAD-hez tartozó CI #3187 (run `45900450820`) mindhárom jobja sikeres: Python/AppTest/browser tesztek, izolált PostgreSQL 17 worker-integráció, valamint backup–restore/security. A PR #26 HEAD-en a JARVIS CI, CodeQL és dependency audit sikeres; a PR #27 HEAD-en a JARVIS CI sikeres. A merge commiton külön post-merge workflow/státusz nem jelent meg, ezért a merge utáni újrafuttatás nem tekinthető igazoltnak.
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


**Központi, teljes áttekintés:** [JARVIS Master Documentation](JARVIS_MASTER_DOCUMENTATION.md)  
**Aktuális implementáció:** [CURRENT_STATE_AND_NEXT_STEPS.md](CURRENT_STATE_AND_NEXT_STEPS.md)  
**Fejlesztési sorrend:** [JARVIS_DEVELOPMENT_ROADMAP.md](JARVIS_DEVELOPMENT_ROADMAP.md)

Ez a dokumentum a jelenlegi fejlesztési branch rendszerhatárait és a fő adatfolyamokat foglalja össze. Nem állítja, hogy minden modul productionben aktív.

> **Fejlesztési ág kiegészítés – 2026-11-27:** az Opportunity Center és az Opportunity Engine az open, draft [PR #35](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/35) része. A migrációk repository-only állapotúak; production DB-módosítás és deploy nem történt. Részletek: [Opportunity Engine](OPPORTUNITY_ENGINE.md).


## 1. Környezet

A JARVIS egy Python 3.11 / Streamlit alkalmazás Gemini API-val és Supabase/PostgreSQL háttérrel. A dashboard helyi fejlesztés alatt áll; nincs JARVIS production app-host. A Supabase production projekt különálló, és a branch migrációi nincsenek rá alkalmazva.

## 2. Fő komponensek

| Komponens | Felelősség |
|---|---|
| `dashboard.py` | Streamlit UI, chat és oldalak |
| `global_lead_research.py` | Explicit kérésre induló, grounding-alapú céges kutatás |
| `company_dossier.py` | Strukturált, forrásellenőrzött dosszié építése, stamp és freshness |
| `company_research_store.py` | Teljes dosszié snapshot mentése és történetlekérdezése |
| `company_research_policy.py` | Read-only döntés a cégkutatás-frissítés jogosultságáról |
| `company_research_refresh_planner.py` | Stale, jogosult leadek read-only kiválasztása és prioritása |
| `opportunity_models.py` | Opportunity score-számítás és forrásbizonyíték-validáció |
| `opportunity_evaluator.py` | Provider-neutral, bizonyítékhoz kötött SaaS-jelölt értékelési előnézet |
| `lead_identity.py` | Cégazonosítási és deduplikációs logika |
| `lead_scoring.py` | Régi, adatmező-teljességi Lead heurisztika |
| `intelligent_lead_scoring.py` | Kutatásalapú Lead prioritás |
| `scoring_core.py` | Közös súlyozott pontszámítási és validációs mag |
| `lead_workflow.py` | Belső következő lépések javaslata |
| `task_actions.py` | Jóváhagyásos task-műveletek |
| `reply_analyzer.py` | Bejövő válasz kategorizálásának alapjai |
| `jarvis_memory.py` | Explicit üzleti memória |
| `daily_briefing.py` | Napi összefoglaló |
| `audit_admin.py` | Audit megjelenítés és export |

## 3. Cégkutatási adatfolyam

1. A felhasználó explicit kutatási kérést ad.
2. A Gemini/Google Search grounding nyilvános céges találatokat ad.
3. A kutatási kód validálja a strukturált adatokat és a grounding URL-eket.
4. A dossziéépítő csak engedélyezett kategóriákat és grounding domainhez kapcsolt forrásokat tart meg.
5. A leadazonosítás deduplikálja a céget.
6. A teljes dosszié snapshot metaadatot kap, majd a snapshot store append-only rekordként menti.
7. A lead notes mező rövid összefoglalót tartalmaz.
8. Az audit rögzíti a kutatási snapshot eseményt.

A kutatási folyamat nem küld e-mailt, nem állít be kapcsolatfelvételi engedélyt és nem indít termékfejlesztést.

## 4. Snapshot store és migráció

A `company_research_store.py` ellenőrzi:
- snapshot UUID;
- pozitív schema version;
- timezone-aware kutatási időpont;
- a facts és decision_maker kanonikus JSON tartalmának SHA-256 lenyomata;
- UUID formátumú lead ID;
- validált cégdomain.

A `company_research_snapshots` tábla:
- leadhez kapcsolt snapshot UUID;
- cégdomain, schema version, kutatási időpont;
- SHA-256 fingerprint és teljes JSON dosszié;
- egyedi snapshot azonosító és időrendi indexek;
- RLS engedélyezve;
- anon és authenticated szerepkörnek nincs tábla-hozzáférése;
- service_role SELECT/INSERT jogosultságot kap.

A migráció a feature branch része, CI izolált PostgreSQL környezetében ellenőrizendő. Productionben nem futott le. A táblához az alkalmazás nem ad update/delete útvonalat; a migráció repository szinten dokumentált append-only működést céloz.

## 5. Kutatási frissítés policy

A `company_research_policy.py` tiszta döntési függvény:
- explicit elutasítás, opt-out és do-not-contact kizár;
- két vagy több rögzített follow-up után, ha nincs inbound válasz, szüneteltet;
- a meg nem keresett cégeket kutatásra jogosultnak hagyja;
- a nem elutasító bejövő választ nem tekinti válaszhiánynak.

A függvény nem módosít DB-t, nem küld üzenetet és nem ütemez munkát. A `company_research_refresh_planner.py` a policy eredményét és a snapshot frissességét kombinálva ad vissza limitált, rendezett candidate listát. Ez is tiszta, read-only függvény; nem olvas DB-t és nem foglal munkát. A DB-lekérdezés, a hiteles outreach event integráció és a tényleges worker még hátravan.

## 6. Opportunity Engine

Az Opportunity Center a céges kutatási eredményeket összekapcsolja, hogy több cégnél ismétlődő problémákból újraértékesíthető SaaS-lehetőségeket azonosítson. A részletes folyamatot, score-súlyokat, táblákat, migrációkat és jogosultsági modellt az [Opportunity Engine dokumentáció](OPPORTUNITY_ENGINE.md) írja le.

Fő elemek:
- `business_pain_hypotheses`: forráshoz kötött, cégspecifikus problémahipotézisek;
- `market_problem_patterns` és `market_pattern_pains`: több cég problémáit összekötő piaci mintázatok; validáláshoz legalább két különböző cég kell;
- `saas_opportunities`: piaci mintázathoz rendelt SaaS-jelöltek, hat score-dimenzióval és score-evidence-szel;
- `opportunity_assessments`: explicit emberi jóváhagyással mentett, append-only értékelési pillanatképek.

A dashboard külön füleken mutatja a céges problémákat, piaci mintázatokat, SaaS-jelölteket, értékelési előnézetet és döntési előzményeket. A provider-neutral evaluator explicit gombnyomásra fut; preview esetén nincs DB-írás. A mentéshez hitelesített admin/operator szükséges. A reader csak olvashat. A DB trigger ellenőrzi a jogosultságot, a validált mintázatot, a két céges alátámasztást és a forrás-egyezést; az értékelési előzmények nem módosíthatók és nem törölhetők.

A migrációk és dashboard-kód a PR #35 feature branchben vannak. Production DB-n nem futottak le, production deploy nem történt.

## 7. Jóváhagyás és külső mellékhatások

- A chat javaslata önmagában nem hajt végre műveletet.
- A task írási műveletek explicit approval folyamaton mennek keresztül.
- A follow-up queue read-only és consent-aware.
- Az outbound e-mail hard-disabled.
- A szerződés és érdeklődés nem automatikus projektindítás.

## 8. Helyi fejlesztés és ellenőrzés

```bash
python -m pip install -r requirements.txt
streamlit run dashboard.py --server.port 8501
python -m pip install -r requirements-test.txt
python -m compileall -q .
python -m pytest -q
```

A GitHub Actions CI az aktuális commitra fut. Csak az adott SHA-n sikeresen befejezett jobok tekinthetők igazoltnak.


## 9. Intelligence Graph

A központi evidence store-ra épülő gráfréteg a Leadeket, cégdosszié-snapshotokat, problémahipotéziseket, piaci mintázatokat, SaaS-jelölteket, jóváhagyott értékeléseket és bizonyítékokat kapcsolja össze. A `intelligence_entities` és `intelligence_relationships` származtatott projection táblák; az eredeti domain táblák maradnak a hiteles források. A dashboard **Intelligence Graph** füle read-only, RLS-en keresztül olvas. Részletek: [Intelligence Graph dokumentáció](INTELLIGENCE_GRAPH.md).
