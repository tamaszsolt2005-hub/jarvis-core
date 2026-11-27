# JARVIS Opportunity Engine – működés és biztonsági modell

## Cél

Az Opportunity Engine a céges kutatás során feltárt, forrásokkal alátámasztott problémákból ismétlődő piaci mintázatokat, majd újraértékesíthető SaaS-termékjelölteket keres. Nem tekinti a modell által megfogalmazott hipotézist bizonyított ténynek. Az értékelés döntéstámogatás; a végső döntést ember hozza meg.

## Központi JARVIS Intelligence Engine

A `intelligence_engine.py` a Lead-, cégdosszié- és Opportunity-területek közös, provider- és adatbázis-független bizonyíték/provenance szerződése. Az egységes `EvidenceRecord` megőrzi a forrás URL-t, kivonatot, forrástípust, megfigyelési és rögzítési időt, bizonyíték-jelleget, kapcsolódó entitást, opcionális snapshot-azonosítót és determinisztikus evidence-azonosítót.

A meglévő cégdosszié snapshotok a régi `facts` és `decision_maker` mezők megtartása mellett `evidence_records` listát is tartalmaznak. Az Opportunity pain bizonyítékai ugyanarra a szerződésre normalizálhatók; a hipotézis státusza ettől nem változik. A Lead scoring adapter kizárólag a külön strukturált `research_evidence` rekordokat veszi át; a szabad szöveges kutatási jegyzet nem válik automatikusan forrássá. A `build_intelligence_snapshot` a különböző domainből érkező rekordokat deduplikálja és forrás-/domain-szintű összesítést készít.

A `intelligence_evidence` a tartós, központi evidence index. A `20261127140000_intelligence_evidence_store.sql` migráció a Lead rekordok strukturált `research_evidence` mezőjét, a `company_research_snapshots.dossier.evidence_records` listát és a `business_pain_hypotheses.evidence` elemeit append-only módon indexeli. A forrásrekordok domain-specifikus táblákban maradnak az eredeti üzleti folyamataik szerint; a központi tábla ezek egységes, kereshető és deduplikált provenance nézete. A korábbi cégdosszié- és pain-rekordok közvetlen `INSERT ... SELECT` backfillen keresztül kerülnek az indexbe, az immutable forrástáblák UPDATE-je nélkül. A trigger csak érvényes HTTP(S) URL-lel és kivonattal rendelkező strukturált elemet vesz át; a Lead-kutatás és a cégdosszié a Google groundingban szereplő pontos forrás-URL-t követeli meg, nem elég az azonos domain; szabad szöveges Lead-jegyzetből nem készít bizonyítékot. A `evidence_id` alapján ismételt ingest nem hoz létre duplikátumot. A központi indexből nincs UPDATE/DELETE jogosultság; authenticated admin/operator/reader szerepkör csak olvashat, a service_role csak SELECT/INSERT jogosultságot kap.

A dashboard Opportunity Center oldalán az **Intelligence áttekintő** fül közös domain-összesítést, forráskivonatokat, forráslinkeket, evidence-típust, megfigyelési/rögzítési időt és entitásazonosítót jelenít meg. A nézet legfeljebb 500 rekordot mutat; ez megjelenítési korlát, nem a tárolt adatok korlátozása.

Ez a réteg nem új autonóm kutató vagy döntéshozó. Nem generál tényeket, nem változtat Lead/Opportunity súlyokon, és nem vonja össze a két pontszám üzleti jelentését. A strukturált, URL-lel alátámasztott bizonyítékot külön kezeli a szabad szöveges Lead-kutatási jegyzetektől; utóbbi önmagában nem válik hiteles forrásrekorddá.


A funkció a `feature/opportunity-center-readonly` fejlesztési ágban, a [PR #35](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/35) részeként készült. A PR draft és nincs merge-ölve. A migrációk repository-fájlok; production adatbázison nem futottak le.

## Folyamat

1. **Cégdosszié és források:** a meglévő kutatási dossziék tényei, URL-jei és kivonatai adják a bemenetet.
2. **Céges problémahipotézis:** egy vállalathoz kapcsolt, forrásokkal ellátott, confidence értékkel és státusszal rendelkező állítás. Hipotézis, nem automatikusan igazolt tény.
3. **Ismétlődő piaci mintázat:** több különböző vállalat problémáit összekapcsoló minta. A `validated` státuszhoz legalább két különböző cég szükséges. Ha a támogatás két cég alá esik, a minta `under_review` állapotba kerül.
4. **SaaS-jelölt:** egy piaci mintázathoz kötött névvel és összefoglalóval rendelkező termékötlet.
5. **Értékelési előnézet:** az evaluator a kiválasztott, validált mintázat és a hozzá tartozó SaaS-jelölt bizonyítékait értékeli. A preview a Streamlit session state-ben marad; önmagában nem ment DB-rekordot.
6. **Emberi jóváhagyás:** scored előnézet esetén hitelesített `admin` vagy `operator` explicit gombnyomással végleges, append-only értékelési rekordot menthet.
7. **Döntési előzmények:** a mentett pillanatképek megtekinthetők, de nem szerkeszthetők és nem törölhetők.

## Pontozási modell

A hat dimenzió súlyozott értékelése:

| Dimenzió | Súly | Értelmezés |
|---|---:|---|
| Probléma bizonyítottsága (`problem_evidence`) | 25% | A probléma forrásokkal mennyire alátámasztott |
| Várható üzleti érték (`business_value`) | 20% | A megoldás várható üzleti haszna |
| Fizetési hajlandóság (`willingness_to_pay`) | 15% | A fizetési hajlandóságra utaló jelek |
| Megvalósíthatóság (`feasibility`) | 15% | A megoldás technikai és működési megvalósíthatósága |
| Újraértékesíthetőség (`reusability`) | 15% | A probléma több cégnél való ismétlődése és a termék újraértékesíthetősége |
| Kockázat (`risk`) | 10% | Kockázati pontszám, fordított irányban számítva |

Minden dimenzió 0–100 tartományú. A kockázat dimenzió hozzájárulása `(100 - risk) × 0.10`. A teljes képlet:

```text
weighted_score =
  problem_evidence * 0.25
  + business_value * 0.20
  + willingness_to_pay * 0.15
  + feasibility * 0.15
  + reusability * 0.15
  + (100 - risk) * 0.10
```

A számítás két tizedesre kerekít. Hiányos dimenziók esetén nincs összpontszám; a hiányzó értéket nem helyettesíti nullával. Minden dimenzióhoz külön, nem üres indoklás és forrásbizonyíték szükséges. Az értékelés confidence értéke külön mező, 0–1 tartományban; nem azonos a weighted score értékével.

## Kapcsolat a Lead scoringgal

A JARVIS két külön üzleti kérdést értékel, ezért a két eredmény nem vonható össze egyetlen pontszámmá:

- **Lead prioritás (intelligent_lead_scoring.py):** mely cégek kutatása/üzleti illeszkedése érdemel előbb figyelmet? Súlyok: üzleti illeszkedés 60%, kutatási bizonyosság 25%, bizonyíték-erősség 15%. Ez nem vásárlási szándék vagy fizetőképesség.
- **Opportunity Score (opportunity_models.py):** mennyire értékes és újraértékesíthető egy több cégnél visszatérő probléma megoldása? A hat Opportunity-dimenzió saját súlyozását használja.

A két pontozás közös, determinisztikus számítási magot (scoring_core.py) használ: 0–100 tartományellenőrzés, hiányzó dimenzió esetén nincs összpontszám, súlyösszeg-validáció, fordított dimenzió és egységes kerekítés. A dimenziók, súlyok és üzleti értelmezések külön maradnak. Így a számítási szabályok közösek, de a Lead prioritás nem keveredik a SaaS-lehetőség értékével.

A régebbi lead_scoring.py::score_lead egyszerű adatmező-teljességi heurisztika; nem a kutatásalapú Lead prioritás és nem Opportunity Score. Nem szabad e három eredményt egyetlen rangsorként kezelni.

## Bizonyítékok

A score evidence minden dimenziójához legalább egy forrásreferencia szükséges. A referencia tartalmazza:
- a kapcsolódó `pain_hypothesis_id` azonosítót;
- a forrás `source_url` URL-jét;
- a forrásból származó `excerpt` kivonatot;
- `observed_at` időpontot vagy `undated` jelölést;
- `evidence_type` értéket: `supporting`, `contradicting` vagy `context`.

A Python validátor a referenciákat a kiválasztott cégproblémák tárolt evidence elemeivel egyezteti. Az approval DB-trigger ismét ellenőrzi, hogy a forrás URL-je és kivonata a jóváhagyott mintázathoz kapcsolt problémaforrások között szerepel-e. A bizonyíték lehet ellentmondó vagy kontextuális is; ezek nem minősülnek automatikusan támogató bizonyítéknak.

## Adatmodell és migrációk

A kapcsolódó migrációk időrendi sorrendben:
- `20261127100000_opportunity_engine_core.sql`: céges problémahipotézisek, piaci mintázatok, mintázat–probléma kapcsolatok és SaaS-jelöltek; RLS és a legalább két külön céghez kötött validáció.
- `20261127110000_opportunity_scoring.sql`: hat score-dimenzió, assessment confidence, indoklás és generált weighted score.
- `20261127120000_opportunity_score_evidence.sql`: dimenziónkénti forrásbizonyíték mező.
- `20261127130000_opportunity_assessment_approvals.sql`: jóváhagyott, append-only értékelési előzmények.
- `20261127140000_intelligence_evidence_store.sql`: tartós, append-only központi bizonyítékindex, három domain forrás-triggerjei, backfill, RLS és olvasási jogosultságok.

Az `opportunity_assessments` külön értékelési pillanatképet tárol: opportunity és market pattern azonosító, a jelölt és mintázat nevét/összefoglalóját rögzítő snapshot mezők, egyedi idempotenciakulcs, hat pontszám, generált összpontszám, confidence, rationale, evidence, evaluator modell/verzió, jóváhagyó Auth user UUID és jóváhagyási időpont. A score összpontszámát az adatbázis generált oszlopa számítja, nem a kliens küldi be.

## Jogosultság és integritás

- `admin` és `operator`: a dashboardon explicit jóváhagyással INSERT műveletet végezhet.
- `reader`: csak SELECT hozzáférést kap az értékelési előzményekhez.
- `anon`: nem kap hozzáférést.
- A jóváhagyó személyazonosságát az adatbázis a hitelesített `auth.uid()` értékből állítja be és ellenőrzi; a kliens nem választhat másik jóváhagyót.
- A trigger ellenőrzi az admin/operator szerepkört, a jelölt és mintázat összetartozását, a mintázat validált állapotát, a két különböző céges alátámasztást és a források egyezését.
- Az egyedi idempotenciakulcs megakadályozza ugyanazon jóváhagyási kísérlet duplikált rekordját.
- UPDATE és DELETE műveletet trigger utasít el: az értékelési előzmény append-only.
- A dashboard authenticated Supabase klienssel ment; a user path nem használ service-role írási kerülőutat.

A táblához a service_role SELECT jogosultsága megmarad a szerveroldali olvasási feladatok számára, de ez nem ad felhatalmazást a dashboard user útvonalának service-role írására.

## Dashboard

Az Opportunity Center fő részei:
- **Intelligence áttekintő:** központi, forrásolt evidence rekordok domain-összesítése, forráslinkek, bizonyíték-jelleg és időbélyegek.
- **Cégproblémák:** egyedi hipotézisek, confidence, státusz és források.
- **Ismétlődő mintázatok:** a több cégnél megfigyelt problémák és a kapcsolódó céges bizonyítékok.
- **SaaS-ötletek:** a piaci mintázatokhoz kapcsolt termékjelöltek és score állapot.
- **Értékelési előnézet:** validált mintázat és hozzá tartozó jelölt kiválasztása, majd explicit gombbal evaluator futtatása.
- **Döntési előzmények:** korábban jóváhagyott értékelések listája.
- **Cégdossziék:** a meglévő dosszié-előzmények külön hozzáférési modellje.

A preview nem automatikus mentés. Elégtelen bizonyíték esetén nem készül pontszám és nem jelenik meg jóváhagyható scored eredmény. A jóváhagyás végleges, ezért a felület figyelmeztetést jelenít meg előtte. A sikeres mentés után a döntési előzmények fül olvassa vissza a rekordot.

## CI és ellenőrzési korlátok

A CI workflow izolált PostgreSQL környezetben futtatja a migrációkat és a pgTAP teszteket. A jóváhagyási tesztfájl: `supabase/tests/opportunity_assessment_approvals.test.sql` (10 assertion a jelenlegi implementáció szerint). A scoring és source-evidence migrációk a jóváhagyási migráció előtt kerülnek alkalmazásra; a migrációk idempotencia-ellenőrzése is része a workflow-nak.

A CI az `intelligence_evidence_store.test.sql` 12 pgTAP assertionjével ellenőrzi a központi tábla RLS-jogosultságait, a három domain triggeres indexelését és a reader olvasási útvonalát; a migrációt ismételten is lefuttatja idempotencia-ellenőrzésként.

A fejlesztési munkamenetben a felhasználó kérésére lokális tesztfuttatás és kézi CI-dispatch nem történt. A push után GitHub Actions automatikusan indult; a konkrét commit CI-eredményét mindig a [PR #35 Actions futásai](https://github.com/tamaszsolt2005-hub/jarvis-core/actions) alapján kell ellenőrizni. A workflow elindulása önmagában nem jelent sikeres tesztet.

## Jelenlegi release-határ

- A PR #35 draft és nincs merge-ölve.
- A migrációk a feature branchben vannak; production adatbázison nem futottak le.
- A dashboard feature production deployja nem történt meg.
- A CI izolált adatbázisa nem production-validáció.
- Merge, production migráció, Auth/RLS éles módosítás és deploy külön, explicit jóváhagyást igényel.


## Intelligence Graph

A központi evidence indexre épülő, lekérdezhető entitás- és kapcsolati gráf a [JARVIS Intelligence Graph dokumentációban](INTELLIGENCE_GRAPH.md) szerepel. A `20261127150000_intelligence_graph.sql` migráció a meglévő Lead-, cégdosszié-, pain-, market pattern-, SaaS opportunity-, assessment- és evidence rekordokból származtatott csomópontokat és éleket tart fenn. A dashboard külön **Intelligence Graph** fület ad; a nézet read-only, RLS-védett, és csak igazolt forrás-/adatkapcsolatokat jelenít meg. A gráf nem tesz AI-hipotézist automatikusan bizonyított kapcsolattá.
