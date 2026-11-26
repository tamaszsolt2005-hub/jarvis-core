# JARVIS – rendszer- és architektúra-dokumentáció

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

A függvény nem módosít DB-t, nem küld üzenetet és nem ütemez munkát. A tényleges worker és a hiteles outreach event integráció még hátravan.

## 6. Jóváhagyás és külső mellékhatások

- A chat javaslata önmagában nem hajt végre műveletet.
- A task írási műveletek explicit approval folyamaton mennek keresztül.
- A follow-up queue read-only és consent-aware.
- Az outbound e-mail hard-disabled.
- A szerződés és érdeklődés nem automatikus projektindítás.

## 7. Helyi fejlesztés és ellenőrzés

```bash
python -m pip install -r requirements.txt
streamlit run dashboard.py --server.port 8501
python -m pip install -r requirements-test.txt
python -m compileall -q .
python -m pytest -q
```

A GitHub Actions CI az aktuális commitra fut. Csak az adott SHA-n sikeresen befejezett jobok tekinthetők igazoltnak.
