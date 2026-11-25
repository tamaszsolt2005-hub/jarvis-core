# JARVIS – elsődleges fejlesztési útiterv

**Ez a dokumentum a JARVIS fejlesztésének elsődleges iránytűje.** Minden új fejlesztési munkamenet elején ezt kell először elolvasni. A feladatokat az alábbi sorrendben kell végrehajtani; ettől csak a felhasználó kifejezett döntésével térjünk el.

## Alapelv

A JARVIS fokozatosan váljon megbízható, biztonságos és önállóbb üzleti asszisztenssé. Figyelhet, elemezhet, felismerhet lehetőségeket és javasolhat műveleteket, de külső vagy üzleti hatású végrehajtás csak megfelelő jogosultsággal és explicit jóváhagyással történhet.

## A fejlesztés öt egymásra épülő területe

### 1. Megbízhatóság és biztonság

Cél: a jelenlegi működés legyen kiszámítható, hibákkal és párhuzamos végrehajtással szemben ellenálló.

- Javítsuk ki a backup workflow importhibáját.
- Tegyük atomikussá az egyszer használatos jóváhagyások felhasználását, beleértve a konkurens kérések kezelését.
- Egészítsük ki a műveletek idempotenciáját: ismételt kérés vagy bizonytalan külső válasz ne okozzon duplikált feladatot vagy mellékhatást.
- Az érzékeny műveletek auditálása legyen fail-closed.
- A kimenő e-mail és más külső mellékhatások maradjanak tiltva, amíg a biztonságos idempotencia és a végponttól végpontig tesztek nem igazolják a működést.

**Lezárási feltétel:** a javítások regressziós és konkurenciatesztekkel igazoltak; a backup teljes friss futása sikeres, beleértve a mentés ellenőrzését és a visszaállítási próbát.

### 2. Supabase és jogosultságkezelés

Cél: az adatbázis állapota, a migrációs előzmények, az Auth és az RLS ellenőrizhetően összhangban legyenek.

- Térképezzük fel és rendezzük a repository és a production migration ledger/séma közötti eltéréseket.
- A migrációkat production-shape PostgreSQL 17 izolált környezetben játsszuk vissza, adatmegőrzési ellenőrzéssel.
- Teszteljük az Auth, session refresh, JWT, szerepkörök és RLS működését kizárólag már létező, engedélyezett izolált Supabase környezetben.
- Válasszuk szét a felhasználói JWT-alapú és a háttérfolyamatok service-role hozzáférését.
- Készítsünk bizonyítékokon alapuló éles átállási tervet, visszaállási tervvel és ellenőrzési kapukkal.

**Lezárási feltétel:** migrációs eltérésekre jóváhagyott, tesztelt rendezési terv; izolált Auth/JWT/RLS tesztek zöldek; dokumentált production cutover és rollback terv.

**Éles korlát:** production DDL/DML, migration push/repair, ledger-módosítás, GRANT/REVOKE, RLS/Auth módosítás és feature flag bekapcsolás külön, konkrét felhasználói jóváhagyás nélkül tilos. Az izolált tesztek nem jelentenek production engedélyt.

### 3. Önállóbb üzleti asszisztens

Cél: a JARVIS ne csak kérdésekre válaszoljon, hanem proaktívan támogassa az üzleti munkát.

- Figyelje a leadeket és a releváns üzleti változásokat.
- Ismerje fel és indokolja meg a lehetséges üzleti lehetőségeket.
- Készítsen javasolt feladatokat, prioritást és következő lépéseket.
- Mutassa meg a javaslatok forrását, bizonytalanságát és várható üzleti értékét.
- A feladatok és külső műveletek végrehajtása maradjon explicit jóváhagyáshoz kötött.

**Lezárási feltétel:** a proaktív javaslatok visszakövethetők, tesztelhetők, duplikációmentesek, és jóváhagyás nélkül nem váltanak ki tiltott mellékhatást.

### 4. Üzleti munkafolyamatok automatizálása

Cél: a különálló képességekből mérhető, végigkövethető üzleti folyamat álljon össze.

**Folyamat:** Leadkutatás → minősítés → stratégia → feladat → jóváhagyás → utánkövetés → eredménymérés.

- Minden lépésnek legyen egyértelmű bemenete, kimenete, állapota és felelőse.
- A folyamat legyen megszakítható, folytatható és idempotens.
- A jóváhagyási pontok legyenek láthatók; jóváhagyás nélkül ne történjen külső végrehajtás.
- Mérjük a leadminőséget, a konverziót, az utánkövetés eredményét és a végrehajtás sikerességét.

**Lezárási feltétel:** a teljes folyamat tesztelhető, auditálható, újraindítható és üzleti eredményekkel mérhető.

### 5. Tudás és hosszú távú memória

Cél: olyan tartós üzleti tudásréteg kialakítása, amely összekapcsolja a leadekről, ügyfelekről, interakciókról, döntésekről, feladatokról és eredményekről rendelkezésre álló információkat.

- Őrizze meg a releváns üzleti kontextust és annak forrását.
- Kapcsolja össze a korábbi döntéseket, végrehajtott lépéseket és azok eredményeit.
- Tegye visszakereshetővé a tanulságokat, és használja fel őket a későbbi javaslatok javítására.
- Kezelje az adatok frissességét, bizonytalanságát, hozzáférési jogosultságait és törlési/megőrzési szabályait.
- Ne tekintse a modell által generált következtetést ellenőrzött ténynek; különítse el a forrást, a tényt és a következtetést.

**Lezárási feltétel:** a tudás visszakereshető, forrásolt, jogosultságkezelt és mérhetően javítja a javaslatok minőségét.

## Haladáskövetés

A dokumentumot folyamatosan frissítsük; ne hozzunk létre párhuzamos, dátumozott roadmapeket.

| Sorrend | Terület | Státusz |
|---|---|---|
| 1 | Megbízhatóság és biztonság | Folyamatban – a backup hiba és az idempotencia javítása hátravan |
| 2 | Supabase és jogosultságkezelés | Előkészítve – izolált tesztelés és migrációs rendezés hátravan |
| 3 | Önállóbb üzleti asszisztens | Tervezett |
| 4 | Üzleti munkafolyamatok automatizálása | Tervezett |
| 5 | Tudás és hosszú távú memória | Tervezett |

A státuszokat minden munkamenetben a tényleges kód, teszteredmény, CI-futás és – ahol releváns – engedélyezett integrációs bizonyíték alapján frissítsük. Egy feladat csak akkor tekinthető késznek, ha a lezárási feltétele teljesült. A „kódban implementált”, „automatikusan tesztelt”, „külső integrációval igazolt” és „productionben aktív” állapotokat mindig különböztessük meg.

## Munkamenet-szabály

1. Elsőként ezt az útitervet olvasd el.
2. Ezután olvasd el az `AGENTS.md`-t, a `README.md`-t és az aktuális feladathoz tartozó részletes dokumentációt.
3. A legkorábbi még nyitott területen dolgozz; ne ugorj későbbi pontra pusztán azért, mert az kényelmesebb.
4. Minden változtatás után futtasd a releváns teszteket, frissítsd a státuszt és az érintett részletes dokumentációt.
5. Production műveletet csak a dokumentált biztonsági kapuk és külön, konkrét jóváhagyás alapján végezz.

## Kapcsolódó részletes dokumentumok

- [AI fejlesztési útmutató](../AGENTS.md)
- [JARVIS képességei és architektúrája](JARVIS_DOCUMENTATION.md)
- [Production állapot és migrációs terv](PRODUCTION_STATE_AND_MIGRATION_PLAN.md)
- [Fejlesztési backlog](DEVELOPMENT_REVIEW_AND_RECOMMENDATIONS.md)
- [Production/release kapuk](REMAINING_WORK_AND_RELEASE_GATES.md)
