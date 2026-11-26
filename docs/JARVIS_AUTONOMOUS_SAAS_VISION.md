# JARVIS – kutatásvezérelt, személyre szabott SaaS-értékesítési és termékfejlesztési modell

**Státusz:** célarchitektúra és fejlesztési specifikáció; nem jelenleg teljesen megvalósított funkció.  
**Kapcsolódó fejlesztési ág:** PR #26 – `docs/pre-feature-readiness-gates`.

## 1. Termékvízió

A JARVIS célja nem egy általános tömeges értékesítési robot. Egy kutatásvezérelt üzleti ügynök legyen, amely önállóan azonosít cégeket, megbízható nyilvános forrásokból feltérképezi a vállalkozást és – ahol releváns és jogszerű – a döntéshozókat, majd minden céghez külön üzleti problémát és arra szabott SaaS-termékjavaslatot dolgoz ki.

A mi üzleti modellünk: a JARVIS felismeri a lehetőséget, kutatással alátámasztja, termékkoncepcióvá alakítja, személyes ajánlatot készít a cégvezetőnek. Ha a cégvezető érdeklődik és elfogadja a koncepciót, a mi csapatunk jóváhagyás után megtervezi és AI segítségével megépíti a terméket.

**Alapelv: előbb a cég problémáját értsük meg, és csak utána válasszunk terméket.** Nem egy előre rögzített SaaS-terméket kell minden leadnek eladni.

## 2. Célfolyamat – a cégtől a személyre szabott termékig

1. **Piacfigyelés és cégfelderítés:** célpiacok, iparágak, méretkategóriák és releváns üzleti jelek alapján új cégek felkutatása.
2. **Cégazonosítás és duplikációszűrés:** domain, normalizált cégnév, ország, cégazonosító és aliasok alapján annak eldöntése, hogy új cégről vagy már ismert rekordról van-e szó.
3. **Cégdosszié készítése:** a cég profilja, termékei/szolgáltatásai, üzleti modellje, ügyfélköre, piacai, technológiai környezete, növekedési jelei, nyilvános hírei, álláshirdetései, működési folyamatai és lehetséges problémái.
4. **Döntéshozó feltérképezése:** nyilvános, szakmai és jogszerű forrásokból a releváns vezetői szerepkör, név, felelősségi terület, szakmai háttér és nyilvános szakmai érdeklődés azonosítása. Nem cél magánéleti vagy érzékeny személyes adatok gyűjtése.
5. **Bizonyíték- és problémaelemzés:** tények, források, dátumok, megbízhatóság és következtetések szétválasztása. A JARVIS több lehetséges üzleti problémát és azok bizonyítékait értékeli.
6. **Egyedi SaaS-lehetőségek generálása:** több megoldási irányt állít elő, és a cég számára várható hasznosság, megvalósíthatóság, fizetési hajlandóságra utaló jelek, integrációs igény, versenyhelyzet, kockázat és becsült fejlesztési költség alapján rangsorol.
7. **Termék- és ajánlási előzmények ellenőrzése:** a globális tiltó/negatív ajánlási napló, a korábbi elutasítások, már meglévő termékek, hasonló ajánlatok és más ügyfeleknek vállalt kizárólagosság ellenőrzése.
8. **Ajánlati csomag készítése:** a legjobb termékkoncepció, a megoldandó probléma, a várható üzleti érték, a működés, a bevezetés, a korlátok és a következő lépés leírása.
9. **Személyre szabott kapcsolatfelvételi tervezet:** a cégvezető szerepéhez és a cég kutatott helyzetéhez illeszkedő, konkrét megfigyelésre épülő, rövid és őszinte levéltervezet. Minden lényegi állítás forrással visszakereshető; nincs kitalált közös ismeretség, hamis személyes kapcsolat vagy nem igazolt állítás.
10. **Emberi felülvizsgálat és engedélyezett outreach:** a JARVIS előnézetet és forrásokat ad; címzett, jogalap, országonkénti marketingkövetelmények, consent/opt-out és küldési korlátok ellenőrzése után külön jóváhagyás szükséges. A jelenlegi outbound e-mail hard-disable továbbra is érvényes; ez a dokumentum nem engedélyezi a küldést.
11. **Válasz és érdeklődés kezelése:** bejövő válasz kategorizálása (érdeklődik, kérdés, elutasítás, később, leiratkozás/nincs további megkeresés), a válasz emberi ellenőrzése és CRM/workflow frissítése.
12. **Ügyfél által elfogadott koncepció → fejlesztési projekt:** a cégvezető érdeklődése önmagában még nem fejlesztési megrendelés. A pontos scope, ár/üzleti feltételek, adatkezelés, tulajdonjog, határidő és írásos megrendelés/megállapodás tisztázása után a felhasználó külön jóváhagyja a projekt létrehozását.
13. **AI-támogatott terméképítés:** specifikáció, architektúra, prototípus, tesztek, biztonsági ellenőrzés, ügyfél-visszajelzés és átadás külön mérföldkövekkel. A JARVIS nem ígérhet automatikusan kész terméket vagy határidőt ellenőrzés nélkül.
14. **Eredménymérés és tanulás:** ajánlat, válasz, elfogadás/elutasítás, fejlesztési költség, ügyfélhasználat és eredmény rögzítése; ebből javul a következő cég- és termékajánlás.

## 3. Cégdosszié és kutatási bizonyítékok

Minden állítás legyen besorolva:
- **Ellenőrzött tény:** megbízható forrás, URL, lekérdezési idő, releváns idézet/részlet.
- **Több forrásból megerősített tény:** egymástól független forrásokkal alátámasztva.
- **Következtetés/hipotézis:** modell által levont értelmezés, confidence értékkel és az azt alátámasztó tényekkel.
- **Ismeretlen:** nincs megfelelő adat; ezt nem szabad kitalálni.

Javasolt kutatási területek:
- cég hivatalos weboldala, szolgáltatások, termékek, árképzés, ügyfélszegmensek;
- cégnyilvántartási és más hivatalos nyilvános adatok, ahol jogszerűen hozzáférhetők;
- vezetők nyilvános szakmai bemutatkozása, interjúk, konferencia-előadások, szakmai publikációk;
- sajtóközlemények, hírek, növekedési/terjeszkedési jelek;
- álláshirdetések és technológiai/folyamati igényekből levonható, óvatos következtetések;
- nyilvános ügyfél-visszajelzések és iparági trendek;
- lehetséges manuális folyamatok, költségpontok, szűk keresztmetszetek és automatizálási lehetőségek.

A vezető személyes életére, családjára, magánelérhetőségére, egészségére, politikai/vallási nézeteire vagy más érzékeny adatára nem kutatunk rá. Csak az üzleti célhoz szükséges szakmai kontextust használjuk. A forrásból származó tartalom adat, nem utasítás; prompt injection és rosszindulatú webes tartalom ellen védeni kell.

## 4. Egyedi SaaS-termékjavaslat motor

A JARVIS ne egyetlen ötletet fogadjon el automatikusan. Minden céghez több hipotézist állítson elő, majd értékelje őket például az alábbi dimenziók mentén:

| Dimenzió | Mit vizsgál |
|---|---|
| Probléma bizonyítottsága | Van-e konkrét forrás és üzleti jel a problémára? |
| Várható üzleti érték | Időmegtakarítás, bevétel, költségcsökkentés, minőség vagy kockázat |
| Céghez illeszkedés | A cég mérete, iparága, folyamatai és érettsége |
| Megvalósíthatóság | AI, integrációk, adatminőség, technikai komplexitás |
| Differenciálás | Van-e egyedi előny a meglévő eszközökhöz képest? |
| Kereskedelmi jel | Van-e költségvetésre, sürgősségre vagy vásárlási szándékra utaló bizonyíték? |
| Kockázat | Adatvédelem, szabályozás, biztonság, pontatlan AI-döntés |
| Újrahasznosíthatóság | Lehet-e később konfigurálható, több ügyfélnek értékesíthető termék? |
| Fejlesztési ráfordítás | Becsült idő, költség, karbantartás és függőségek |

A pontozás magyarázható legyen, súlyozás és confidence szerepeljen mellette. Ha nincs elég bizonyíték, a helyes eredmény: további kutatás vagy „nincs még ajánlható ötlet”, nem kényszerített termékjavaslat.

A javaslat tartalmazza:
- probléma és bizonyítékai;
- célfelhasználók és döntéshozó;
- SaaS-koncepció, fő funkciók és felhasználói folyamat;
- miért hasznos ennek a konkrét cégnek;
- várható eredmény és annak mérési módja;
- alternatívák és meglévő piaci megoldások;
- MVP-scope és mi nincs benne;
- becsült komplexitás/kockázat, feltételezések;
- nyitott kérdések, amelyeket a cégtől kell megkérdezni.

## 5. „Mit ne ajánljunk” – globális termék- és ajánlási napló

Ez a rendszer egyik kötelező központi képessége. Nem elegendő, ha a JARVIS csak az adott lead rekordjában tárolja az elutasítást.

A naplóban külön kell kezelni:
- **Globálisan tiltott ötlet:** többé ne ajánlja egyik cégnek sem.
- **Elvetett termékkoncepció:** korábbi elemzés után nem megfelelő, okkal és dátummal.
- **Cégnél elutasított ajánlat:** az adott cégnek ne ajánlja újra ugyanazt vagy lényegében azonos ötletet.
- **Piaci/technikai kizárás:** jogi, biztonsági, megvalósíthatósági vagy üzleti okból tiltott.
- **Már meglévő termék/megoldás:** ne ajánljon olyat, amit a cég már használ vagy maga kínál, kivéve ha bizonyított, releváns kiegészítésről van szó.
- **Kizárólagosság/ügyfélközi ütközés:** egyedi szerződéses vállalás miatt nem ajánlható másnak.
- **Újravizsgálható ötlet:** csak meghatározott idő vagy új bizonyíték után kerülhet ismét értékelésre.

Minimális mezők:
- ötlet normalizált neve, leírása, kategóriája, feature fingerprintje;
- scope (globális, iparág, cég, ügyfélcsoport);
- státusz és indoklás;
- létrehozó és jóváhagyó;
- forrás/kapcsolt cég, ajánlat és projekt;
- érvényesség kezdete/vége és felülvizsgálati dátum;
- korábbi hasonló ötletek és hasonlósági találatok;
- audit trail, verzió és időbélyegek.

**Ajánlás előtti kötelező ellenőrzés:** pontos és szemantikus hasonlóságkeresés a tiltó naplóban, a korábbi ajánlatokban, elutasításokban, aktív ügyfélprojektekben és a termékkatalógusban. Ütközés esetén blokkolás vagy emberi felülvizsgálat. Az embedding/hasonlósági keresés nem helyettesíti a determinisztikus tiltásokat.

A „ne ajánld” bejegyzés nem törölhető nyomtalanul; feloldása indokolt, auditált, jogosultság-ellenőrzött művelet legyen.

## 6. Személyre szabott e-mail és kapcsolatfelvétel

A személyre szabás a cég valós üzleti helyzetére és a vezető szakmai szerepére épüljön, ne pusztán név behelyettesítésére.

Minden tervezet tartalmazza:
- miért pont ezt a céget kerestük meg;
- mely nyilvános üzleti jelből következtettünk a problémára (forrással);
- mi a feltételezett probléma, és miért fontos;
- hogyan segítene az egyedi SaaS-megoldás;
- milyen konkrét, hihető üzleti eredményt céloz;
- egy rövid, alacsony elköteleződésű következő lépést.

Ne állítson bizonyítatlan ROI-t, ügyféleredményt, integrációt vagy kész terméket. A hipotézist hipotézisként kell megfogalmazni. A levél ne legyen megtévesztően „személyes”, ne használjon érzékeny személyes adatot, és legyen egyértelmű a feladó kiléte és a kapcsolatfelvétel célja.

A címzett adatának eredete, marketingjogalap, országonkénti szabályok, tiltólista, leiratkozás, gyakorisági korlát és suppression lista ellenőrzése kötelező. A jogszerűség nem következtethető ki pusztán abból, hogy az e-mail-cím nyilvános. A JARVIS csak jóváhagyott tervezetet adhat át a küldési modulnak. A jelenlegi outbound hard-disable marad; küldéshez külön implementációs és jogi/biztonsági felülvizsgálat, majd kifejezett felhasználói engedély kell.

## 7. Érdeklődésből fejlesztési projekt

A „tetszik az ötlet” vagy „küldj több információt” nem jelent automatikus megrendelést. Állapotgép javaslat:

`discovered → researched → opportunity_drafted → internally_approved → outreach_eligible → contacted → replied → interested → discovery_call → proposal → accepted → contracted → build_approved → in_development → delivered → measured`

Lehetséges elágazások: `rejected`, `no_response`, `opted_out`, `disqualified`, `on_hold`.

A fejlesztés indításához kötelező:
- ügyfél által elfogadott és verziózott scope;
- szerződés/írásos megrendelés és kereskedelmi feltételek;
- adatkezelési és biztonsági követelmények;
- felelősségek, tulajdonjog és harmadik fél licencek tisztázása;
- MVP elfogadási kritériumok és tesztelési terv;
- külön belső jóváhagyás a projekt létrehozására és erőforrás kiosztására.

A JARVIS ezután projektet, feladatokat, specifikációt, teszttervet és fejlesztési backlogot készíthet. Külső ügyfélnek nem ígérhet automatikusan árat vagy határidőt emberi ellenőrzés nélkül.

## 8. Javasolt adatmodell

A pontos séma későbbi tervezés tárgya; első körben a következő logikai entitások szükségesek:
- `companies`: kanonikus cégazonosító, domain, ország, iparág, státusz.
- `company_aliases`: nevek, domainek és külső azonosítók.
- `company_research_runs`: kutatási futás, scope, állapot, időbélyeg.
- `research_sources`: URL, kiadó, dátum, lekérdezés, tartalmi kivonat/hash.
- `company_facts`: forráshoz kötött tények, érvényesség, confidence.
- `decision_makers`: szakmai szerepkör és csak üzleti célhoz szükséges nyilvános adatok.
- `business_pain_hypotheses`: problémahipotézis, bizonyíték, confidence.
- `saas_ideas`: termékkoncepció, verzió, feature fingerprint, becslések.
- `saas_idea_evaluations`: dimenziónkénti pontszámok, indoklás, rangsor.
- `recommendation_ledger`: ajánlatok, státuszok, cég és döntés.
- `product_exclusion_ledger`: globális és scope-specifikus tiltások/negatív döntések.
- `outreach_drafts`: címzett, források, jogalap-ellenőrzés, verzió, approval.
- `outreach_events`: csak engedélyezett küldés és bejövő válasz eseményei.
- `client_opportunities`: érdeklődés, igényfelmérés, ajánlat, elfogadás.
- `delivery_projects`: szerződött és jóváhagyott fejlesztési projektek.
- `product_outcomes`: használat, eredmény, költség, tanulság.

A tényleges táblák, RLS policy-k, RPC-k és migrációk külön tervezést, review-t és tesztet igényelnek. Ez a dokumentum nem jogosít fel production adatbázis módosítására.

## 9. Ügynökök és háttérfolyamatok

Logikai komponensek:
1. Market Discovery Agent – célpiaci jelzések és cégek keresése.
2. Company Research Agent – forrásgyűjtés és cégdosszié.
3. Decision Maker Research – szakmai döntéshozó és releváns nyilvános kontextus.
4. Opportunity Analyst – üzleti problémák és hipotézisek.
5. SaaS Product Strategist – egyedi termékkoncepciók és rangsor.
6. Exclusion/Novelty Guard – tiltólista, korábbi ötletek és ütközések.
7. Personalization Writer – forrásolt ajánlat és e-mail-tervezet.
8. Response & CRM Agent – bejövő válasz kategorizálása és workflow.
9. Delivery Planner – elfogadott, szerződött ötletből fejlesztési projekt előkészítése.

Ezek kezdetben lehetnek egy alkalmazás moduljai, nem szükséges külön mikroservice-ekre bontani. A háttérfutás idempotens legyen: claim/lease, heartbeat, retry limit, dead-letter, operation ID, rate limit, költségkeret és audit szükséges. A felhasználó állítsa be a célpiacot, kutatási keretet, napi futási limitet és költségkeretet.

## 10. Megvalósítási fázisok és elfogadási feltételek

### Phase 0 – jelenlegi alap stabilizálása
- Meglévő lead/task/memória/approval workflow megtartása.
- Új funkciók csak branch/PR és tesztek mellett.
- Minden új adatforrás és külső szolgáltatás dokumentálása.

### Phase 1 – automatikus cégfelderítés és kutatás
- Idempotens, limitált scheduler/worker.
- Cégduplikációk és kutatási források kezelése.
- Cégdosszié és döntéshozó szakmai profil.
- Forrás, dátum, confidence és stale-data frissítés.
- Read-only működés, outreach nélkül.

**Elfogadás:** ismételt futás nem hoz létre duplikált céget; minden tény visszavezethető forrásra; hiányzó adat nem kitalált; rate/cost limit működik.

### Phase 2 – egyedi SaaS-ötlet és tiltó napló
- Ötletgenerálás több alternatívával.
- Rangsorolás magyarázható pontozással.
- Globális és cégenkénti tiltó/negatív napló.
- Korábbi ajánlatokkal és aktív projektekkel ütközésvizsgálat.

**Elfogadás:** tiltott ötlet nem kerül ajánlható listába; bizonyítékhiánynál a rendszer tartózkodik; az ajánlás indoklása forrásolt és reprodukálható.

### Phase 3 – ajánlati csomag és e-mail-tervezet
- Cégvezető szerepéhez illeszkedő, forrásolt személyre szabás.
- Állítások és források ellenőrzése.
- Belső review, jogalap/opt-out/suppression ellenőrzés.
- Küldés továbbra is kikapcsolva az engedélyezett külön fázisig.

**Elfogadás:** nincs hamis személyre szabás, nem igazolt tény vagy tiltott címzett; minden levéltervezet visszakövethető kutatási rekordokhoz.

### Phase 4 – válaszkezelés és értékesítési workflow
- Inbound válaszok és leiratkozások kezelése.
- Érdeklődő → igényfelmérés → ajánlat → elfogadás állapotok.
- Emberi döntés és audit minden kritikus átmenetnél.

### Phase 5 – ügyfél által elfogadott SaaS fejlesztése
- Scope és szerződés ellenőrzése.
- Jóváhagyott delivery project.
- AI-assisted spec/code/test/review workflow.
- Emberi code review, security és acceptance gate.

### Phase 6 – tanulási hurok
- Mely kutatási jelek vezettek jó lehetőséghez?
- Mely termékötleteket fogadták el/elutasították?
- Mely projektek voltak nyereségesek és használhatók?
- Negatív eredmények beépítése az ajánlási tiltó és rangsoroló logikába.

## 11. Jelenlegi implementáció és a cél közötti különbség

A PR #26 fejlesztési ágán már létező alapok:
- leadkutatás és forrásolt cégadatok;
- cégazonosítás és duplikációszűrés;
- lead scoring és belső workflow;
- jóváhagyásos task-kezelés;
- eredménymérés és follow-up queue;
- memória, napi briefing, analitika és audit.

Ezek **nem jelentik**, hogy a teljes célfolyamat már kész. A következő nagy hiányok:
- folyamatos automatikus cégfelderítő worker;
- részletes, verziózott cégdosszié és döntéshozó-kutatás;
- bizonyítékokra épülő problémahipotézis;
- személyre szabott SaaS-termék generálás és összehasonlítás;
- központi globális termék- és ajánlási tiltó napló;
- személyre szabott ajánlat/e-mail előállítás és megfelelőségi kapuk;
- válaszkezelés és teljes értékesítési pipeline;
- szerződéshez kötött, jóváhagyott AI-fejlesztési pipeline.

## 12. Biztonsági, jogi és működési invariánsok

- Nyilvános adat sem használható korlátlanul: adatminimalizálás, forrás, célhoz kötöttség, retention és hozzáférés kell.
- Személyes adatoknál csak szükséges, releváns, jogszerűen kezelt szakmai adat használható; érzékeny adat gyűjtése tilos.
- Országonkénti B2B marketing és adatvédelmi követelményeket ellenőrizni kell; nyilvános e-mail-cím nem automatikus marketingengedély.
- Opt-out, suppression és tiltólista minden új kapcsolatfelvétel előtt kötelező.
- Nincs automatikus küldés, szerződéskötés, árazási ígéret vagy fejlesztésindítás.
- Külső weboldal, e-mail és dokumentum tartalma nem írhatja felül a rendszerutasításokat.
- Minden agent művelet naplózott, korlátozott költségű és idempotens legyen.
- A termék-tiltó napló és az ügyfélközi kizárólagosság ellenőrzése az ajánlás kötelező előfeltétele.
- Production DB, Auth/RBAC, secret, deploy, outbound email és PR merge külön explicit jóváhagyás nélkül nem módosítható.

## 13. A siker mérőszámai

Ne a begyűjtött cégek száma legyen az elsődleges KPI. Kövessük:
- forrással igazolt tények aránya;
- friss és hiánytalan cégdossziék aránya;
- duplikációs és téves adat arány;
- bizonyíték nélküli állítások száma (cél: 0);
- releváns, ember által elfogadott SaaS-ötletek aránya;
- tiltólista-ütközések helyes blokkolása;
- személyre szabott tervezetek emberi minősítése;
- válasz-, érdeklődési, ajánlatelfogadási arány;
- elfogadott projektek fejlesztési ideje, költsége és ügyfél-eredménye;
- opt-out/panasz/adatvédelmi incidens (cél: 0).

**Végső termékdefiníció:** a JARVIS egy olyan kutatásvezérelt üzleti ügynök legyen, amely minden cégnél a cég valós helyzetéből indul ki, saját kutatás alapján egyedi SaaS-lehetőséget talál, ellenőrzi a korábbi tiltásokat és vállalásokat, személyre szabott ajánlatot készít, majd az ügyfél kifejezett elfogadása és a mi külön jóváhagyásunk után segít a termék megépítésében.
