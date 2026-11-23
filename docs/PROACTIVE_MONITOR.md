# Napi proaktív monitor

## Futtatási sorrend

| Idő (UTC) | Folyamat |
|---:|---|
| 08:00 | Globális céges leadkutatás |
| 08:20 | Proaktív lead- és feladatváltozás-figyelés |
| 08:30 | Napi vezetői briefing |

A monitor külön is indítható a GitHub Actions **JARVIS Daily Proactive Monitor**
workflow-jának kézi futtatásával.

## Adatbiztonság és hatókör

- A monitor a meglévő Supabase projektet használja; nem hoz létre projektet,
  adatbázis-ágat vagy új táblát.
- Legfeljebb 2000 leadet és 1000 feladatot vizsgál.
- Az első sikeres futás csak alapállapotot ment, nem jelenti tévesen újnak
  a már meglévő rekordokat.
- A következő futások az előző sikeres pillanatképhez viszonyítják az új
  rekordokat és a státusz-, prioritás- és határidő-változásokat.
- Sikeres futáskor a `jarvis_proactive_state` tábla
  `daily_proactive_snapshot` kulcsú sorát upserteli; ez technikai állapotírás,
  tehát a monitor nem teljesen read-only. Hiba esetén a központi hibajelentő
  a `logs` táblába is megpróbálhat warning eseményt írni.
- Nem módosít leadet, feladatot, beállítást vagy e-mail-tervezetet; nem küld
  e-mailt és nem indít külső kapcsolatfelvételt.
- A workflow hiányzó Supabase titkok esetén kihagyja a futást, adatbázishiba
  esetén pedig sikertelenül zárul, nem jelzi sikeresnek a hibás futást.

## Korlátok

A mintavételi limitek miatt a jelentés nem teljes adatbázis-audit. Ha a
táblákban 2000-nél több lead vagy 1000-nél több feladat van, a monitor
jelenlegi lekérdezése csak a Supabase által visszaadott mintát vizsgálja.
A jelentés artifactként 14 napig érhető el.

A PR #12 commitján a GitHub Actions JARVIS CI 2026-11-23-án sikeresen lefutott:
`compileall`, a teljes unit/AppTest/browser tesztlépés, CloudFormation-validáció
és a böngészőfüggőségek telepítése is sikeres volt. A mockolt tesztek és a CI
nem helyettesítik az éles Supabase-kapcsolat, a GitHub Actions titkok vagy az
ütemezett futás ellenőrzését. Éles integrációs futás még nincs igazolva.
