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
| `lead_scoring.py` | Lead pontozása |
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
