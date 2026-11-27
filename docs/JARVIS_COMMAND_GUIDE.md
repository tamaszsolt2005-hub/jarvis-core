# JARVIS – parancs- és kifejezéskalauz

**Ez a dokumentum azt tanítja meg, mit írj be a JARVIS chatbe, ha konkrét műveletet szeretnél.** A példák a main ágba merge-ölt PR #26–#28 kódjának parser- és routing-szabályaira épülnek. A természetes nyelvű kérdések egy része elemzést indít, de nem minden kifejezés parancs. Ahol külön jóváhagyás szükséges, azt minden esetben feltüntetem.

Kapcsolódó dokumentum: [rendszer- és architektúra-leírás](JARVIS_DOCUMENTATION.md).

## 1. A legfontosabb szabály: javaslat és végrehajtás nem ugyanaz

- Egy kérdésre adott válasz vagy javaslat önmagában nem módosít adatbázist.
- A feladatparancs először csak jóváhagyásra váró műveletet készít elő.
- A következő üzenetben külön kell jóváhagynod a műveletet.
- Ha új, másik kérést írsz a jóváhagyás helyett, a korábbi függő művelet érvényét veszti.
- A kimenő e-mail küldés jelenleg kódszinten tiltott; a jóváhagyás sem kapcsolja be.

Jóváhagyó kifejezések:
- Jóváhagyom
- Jóváhagyom a műveletet
- Végrehajthatod
- Igen, mehet

Elutasító kifejezések:
- Elutasítom
- Mégse
- Ne hajtsd végre

Ha nincs függőben jóváhagyás, a „Jóváhagyom” nem indít el semmit.

## 2. Feladatok kezelése

### 2.1 Új feladat létrehozása

Írd be:

    Hozz létre feladat: Piaci versenytársak elemzése

Opcionális mezők pontosvesszővel elválasztva:

    Hozz létre feladat: Piaci versenytársak elemzése; prioritás=high; határidő=2026-12-01; leírás=Az öt legfontosabb versenytárs összehasonlítása

Elfogadott mezők:
- prioritás: normal, high vagy urgent
- határidő: ÉÉÉÉ-HH-NN formátum
- leírás: legfeljebb 1000 karakter
- cím: alternatív címmező, ha további mezőket adsz meg

A feladat címe 1–180 karakter lehet. Ha nincs prioritás, normal az alapérték. A határidő Budapest időzónában a megadott nap 23:59 órája.

**Mi történik?** JARVIS megmutatja, milyen feladatot készít elő, és jóváhagyást kér. Csak a következő külön „Jóváhagyom” üzenet után történik DB-művelet.

### 2.2 Feladat módosítása

Szükséged lesz a Feladatközpontban látható task UUID-ra.

    Módosítsd a feladatot: 123e4567-e89b-42d3-a456-426614174000; prioritás=urgent; határidő=2026-12-03

Módosítható mezők:
- cím vagy cim
- prioritás vagy prioritas: normal / high / urgent
- határidő vagy hatarido: ÉÉÉÉ-HH-NN
- leírás, leiras, jegyzet vagy notes: legfeljebb 1000 karakter
- eredmény vagy eredmeny: legfeljebb 500 karakter

Példa eredmény rögzítésére:

    Módosítsd a feladatot: 123e4567-e89b-42d3-a456-426614174000; eredmény=pozitív: a pilotigény igazolódott, három érdeklődő jelezte a részvételt

A módosítás előnézetet és külön jóváhagyást igényel. Más mező, például lead státusza vagy consentje ezzel a paranccsal nem módosítható.

### 2.3 Feladat lezárása

    Zárd le a feladatot: 123e4567-e89b-42d3-a456-426614174000

A „Fejezd be a feladatot: UUID” változat is támogatott. A lezárás jóváhagyásköteles. Lezárás előtt rögzítsd az eredményt, ha a feladat üzleti kimenetet mért.

### 2.4 Kutatásból javasolt belső feladat létrehozása

    Hozz létre javasolt feladat: 123e4567-e89b-42d3-a456-426614174000

Itt a UUID **leadazonosító**, nem taskazonosító. JARVIS újraellenőrzi a lead kutatási forrását, a bizonyítékokat és a már kapcsolt feladatokat. Csak érvényes, forrásolt kutatásból készít approval-ready belső feladatot. A leadhez tartozó nyitott task blokkolhatja a duplikált javaslatot.

## 3. Eredményalapú következő teendő

Az eredménymérési workflow-feladat lezárása után JARVIS a feladat jegyzetében tárolt, egyértelmű eredménybesorolást vizsgálja.

Használd az alábbi pontos előtagok egyikét az eredmény mezőben:

| Beírt eredmény | Javasolt belső következő lépés |
|---|---|
| pozitív: ... | Pozitív üzleti eredmény és lehetőség belső értékelése |
| negatív: ... | Negatív eredmény okának és lezárásának felülvizsgálata |
| nincs válasz: ... | Újraminősítés és kutatás frissítése |
| más / nincs besorolás | Emberi eredménybesorolás kérése |

Példák:
- eredmény=pozitív: a pilotigény igazolódott
- eredmény=negatív: a költségkeret nem megfelelő
- eredmény=nincs válasz: két megkeresési kísérlet után sem érkezett válasz

A JARVIS nem következtet a szabad szövegből pozitív vagy negatív kimenetelre. A besorolás csak a lezárt outcome_measurement workflow-feladatnál indít ajánlást. Az ajánlás read-only; a következő taskot külön paranccsal és jóváhagyással lehet létrehozni. Nem indít kapcsolatfelvételt.

## 4. Leadkutatás és célpiac

### 4.1 Céges kutatás indítása

Példák explicit kutatási kérésre:

    Leadkutatás: keress magyarországi ipari automatizálási beszállítókat
    Keress 10 potenciális ügyfelet a német logisztikai szektorban
    Céges lead keresés: magyar építőipari generálkivitelezők

A kutatás nyilvános, forrásolt céges információkat keres. Egy futás legfeljebb 15 új céget vehet fel. A már meglévő cégeket a közös cégazonosítási/deduplikációs logika kezeli. Ez nem ad kapcsolatfelvételi engedélyt, és nem gyűjt automatikusan személyes e-mail-címeket.

A tényleges keresés és leadírás előtt JARVIS megmutatja a jóváhagyásra váró műveletet. Csak külön „Jóváhagyom” üzenetre indul.

### 4.2 Célpiac váltása

Példák:

    Válts célpiacot Németországra
    Állítsd át a kutatási piacot Ausztriára
    Válts célpiacot Worldwide piacra

A célpiac-váltás külön jóváhagyást kér. Támogatott országok: Magyarország, Németország, Franciaország, Ausztria, Svájc, Egyesült Királyság, Olaszország, Spanyolország, Lengyelország, Románia, Hollandia, Portugália, Belgium, Csehország, Szlovákia, Svédország, Dánia, Norvégia, Finnország, Írország, USA, Kanada és Worldwide. Ismeretlen országot JARVIS elutasít.

A piacváltás és a kutatás két külön fogalom: a piac beállítása nem indít automatikusan kutatást. Ha ugyanabban a kérésben kutatást is kérsz, a jóváhagyási előnézet mindkettőt jelezheti.

## 5. Hosszú távú üzleti memória

Memóriát kizárólag kifejezett utasításra módosít.

### 5.1 Mentés

Általános üzleti preferencia:

    Jegyezd meg: a riportokat mindig magyar nyelven kérem

Döntés:

    Jegyezd meg a döntést: a következő negyedévben a német piacot priorizáljuk

Tanulság:

    Rögzítsd a tanulságot: a személyre szabott bemutató több releváns visszajelzést hozott

Tapasztalat / eredmény:

    Mentsd el a tapasztalatot: iparág=logisztika; módszer=személyre szabott bemutató; döntés=folytatjuk; eredmény=3 minősített érdeklődő

A mentés legfeljebb 700 karakteres lehet. Titkot, API-kulcsot, jelszót, tokent, e-mail-címet, telefonszámot vagy érzékeny személyes adatot ne adj meg; ezeket a rendszer elutasítja.

### 5.2 Memória megtekintése

    Mutasd a memóriádat
    Mit jegyeztél meg?
    Mire emlékszel?
    Memória áttekintés

A JARVIS az aktív memóriaelemekből legfeljebb 50-et jelenít meg.

### 5.3 Memóriaelem inaktiválása

    Felejtsd el a német piacra vonatkozó döntést

A keresés a megadott kifejezés jelentős szavai alapján próbál egyezést találni. Üres cél vagy „felejts el mindent” esetén az összes aktív memóriaelem inaktiválódik. Ez nem fizikai törlés, és nem azonos a chat-előzmények törlésével.

## 6. Napi briefing és általános elemzés

A következő kifejezések a napi read-only vezetői jelentést kérik:

    Készíts napi jelentést
    Reggeli jelentés
    Vezetői összefoglaló
    Mai üzleti terv
    Mai prioritások
    Változásfigyelés

A jelentés összefoglalhatja a leadkutatási lehetőségeket, belső következő feladatokat, nyitott és lejárt taskokat, valamint a consent alapján jogosult utánkövetési jelzéseket. Nem küld üzenetet és nem módosít rekordot.

Példák általános analitikai kérdésre:

    Elemezd a leadek konverziós trendjét
    Mutasd a rendszerhasználati statisztikákat
    Hasonlítsd össze a kutatási eredményeket
    Milyen üzleti tanulságokat látunk a korábbi eredményekből?

Ezek természetes nyelvű elemzési kérések, nem kötött parancsok. A JARVIS az elérhető és releváns adatok alapján válaszol; ha az adatforrás hibás vagy hiányos, azt jeleznie kell.

## 7. Opportunity Center – dashboard használat

Az Opportunity Engine nem chat-parancsokkal működik, hanem a Streamlit dashboard külön **Opportunity Center** oldalán.

1. **Cégproblémák:** nézd át a cégekhez kapcsolt hipotéziseket, confidence értékeket, státuszokat és forrásokat. A hipotézis nem bizonyított tény.
2. **Ismétlődő mintázatok:** validált mintázat csak legalább két különböző cég problémájára támaszkodhat.
3. **SaaS-ötletek:** a mintázatokhoz kapcsolt termékjelöltek és azok értékelési állapota.
4. **Értékelési előnézet:** válassz validált mintázatot és az ahhoz kapcsolódó SaaS-jelöltet, majd az „Értékelési előnézet készítése” gombbal indítsd az értékelést. Ez külső Gemini-hívást indíthat, ezért csak tudatosan használd.
5. **Jóváhagyás:** scored eredménynél hitelesített admin/operator explicit „Jóváhagyom és véglegesen mentem” gombbal rögzítheti a döntést. A mentés végleges, append-only előzményt hoz létre.
6. **Döntési előzmények:** a korábbi jóváhagyások és pontszámok visszanézhetők, de nem szerkeszthetők.

A reader szerepkör csak olvasási jogosultságot kap. Megosztott dashboard-jelszó vagy anon hozzáférés nem jogosít jóváhagyásra. A preview önmagában nem mentés; insufficient-evidence eredmény nem hagyható jóvá. A migrációkat productionben külön jóváhagyás és felülvizsgálat nélkül nem szabad futtatni.

Részletes technikai leírás: [Opportunity Engine – működés és biztonsági modell](OPPORTUNITY_ENGINE.md).

## 8. Mit nem szabad parancsként kezelni?

- A „küldj e-mailt” kérés nem jelenti azt, hogy az e-mail valóban kimehet. A kimenő küldés kódszinten tiltott.
- Az utánkövetési sor megjelenése nem indít follow-upot.
- A workflow-ajánlás nem hoz létre taskot automatikusan.
- A leadkutatás nem jelent kapcsolatfelvételi engedélyt.
- A „Jóváhagyom” csak az éppen függő, előnézetben megmutatott műveletre vonatkozhat.
- A tetszőleges, természetes nyelvű mondat nem helyettesíti a strukturált task-parancs mezőit.

## 9. Gyors hibakeresés

| Helyzet | Mit ellenőrizz? |
|---|---|
| A task parancs nem indul | Pontos előtag, pontosvessző, mező=érték formátum, UUID |
| A jóváhagyás nem működik | Van-e függő művelet? Nem küldtél-e közben másik kérést? |
| Nincs workflow-javaslat | Van-e forrásolt Leadkutatás; rekord és megfelelő task állapot? |
| Nincs outcome-javaslat | Lezárt outcome_measurement task? Eredmény pontos prefixszel? Nincs más nyitott task? |
| Nem jelenik meg follow-up | Consent, approved_to_contact, opt-out, reply, follow_up_count és dátum ellenőrzése |
| Memória nem menthető | Legfeljebb 700 karakter? Nem tartalmaz tiltott titkot vagy személyes adatot? |
| Kutatás nem indul | Explicit céges kutatási kérés? Előnézet jóváhagyása? Támogatott célpiac? |

**Megjegyzés:** a dokumentált kód a main ágba merge-ölve van. A production alkalmazás nincs deployolva; a helyi működést külön manuális dashboard smoke-kal kell ellenőrizni.
