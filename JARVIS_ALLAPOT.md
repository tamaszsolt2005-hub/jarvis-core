# JARVIS – megvalósított funkciók és aktuális állapot

**Utolsó kódfelülvizsgálat:** 2026-11-17  
**Repository:** `tamaszsolt2005-hub/jarvis-core`  
**Ág:** `main`

Ez a dokumentum a repository aktuális forráskódja, README-je, Supabase-sémája, GitHub Actions workflow-jai és tesztjei alapján készült. A „kész” azt jelenti, hogy a funkció implementálva van a kódban. Ez önmagában nem bizonyítja, hogy az éles Supabase/Gemini-kapcsolat, a Codespaces-felület vagy az ütemezett háttérfolyamat ténylegesen működik.

## 1. A JARVIS jelenlegi alapja

- [x] Chat-központú Streamlit alkalmazás, egyetlen beszélgetési felülettel.
- [x] Sötét, prémium megjelenésű JARVIS felület.
- [x] Gemini-alapú magyar nyelvű válaszgenerálás.
- [x] A modell neve környezeti konfigurációból választható; alapértelmezésben Gemini 3.8 Flash.
- [x] A beszélgetési előzmények korlátozott méretben bekerülnek a következő válasz kontextusába.
- [x] A kontextus-összeállítás korlátozza az egyes üzenetek és a teljes előzmény hosszát.
- [x] A válaszadási utasítások előírják a tények, feltételezések és ismeretlen adatok elkülönítését, az adatforrások és mintanagyságok jelzését, valamint a megalapozatlan számok kerülését.
- [x] A rendszer a felhasználói kérdés alapján választja ki, milyen üzleti adatokat töltsön be a Supabase-ből.
- [x] A korábbi beszélgetésekből, memóriából és webes tartalomból származó szöveg nem írhatja felül a rendszerutasításokat.

## 2. Üzleti adatok és CRM-kapcsolat

- [x] Supabase-kapcsolat a leadek, feladatok, beállítások és technikai adatok lekérdezéséhez.
- [x] A normál üzleti adatlekérdezések olvasási műveletek.
- [x] A leadekhez és feladatokhoz kapcsolódó üzleti kérdések természetes nyelven feltehetők a chatben.
- [x] A proaktív kérdésekhez a JARVIS lejárt feladatokat és – csak megfelelő engedéllyel – esedékes utánkövetéseket keres.
- [x] A személyes lead e-mail-címek és a kézzel rögzített, szabad szöveges CRM-megjegyzések nem kerülnek a Gemini üzleti elemzési kontextusába.
- [x] A lead- és feladatadatok lekérdezése korlátozott rekordszámú; a jelentések feltüntetik a vizsgált adatkör korlátait.

## 3. Weboldal-elemzés

- [x] Üzleti weboldalak automatikus vizsgálata releváns weboldal-rangsorolási vagy weboldalhibákkal kapcsolatos kérdésnél.
- [x] Korlátozott számú, legfeljebb 30 nyilvános weboldal vizsgálata egy ilyen elemzés során.
- [x] HTTP-státuszok és elérhetőségi hibák jelzése.
- [x] 0–100 közötti weboldal-információs pontszám.
- [x] A pontszám az oldal üzleti információtartalmát méri, nem a cég vásárlási szándékát, fizetőképességét vagy konverziós esélyét.
- [x] A weboldal-elemzés nem írja át a CRM-lead rekordjait.
- [x] Biztonságos HTTP-lekérő modul: csak HTTP/HTTPS, szabványos portok, nyilvános IP-címek; DNS-feloldás ellenőrzése és a kapcsolat validált IP-re rögzítése; átirányítások célcímének újraellenőrzése.
- [x] A HTTP-válaszokhoz tartozó erőforrások lezárása.

## 4. Globális, forrásalapú céges leadkutatás

- [x] Gemini Google Search groundinggal támogatott, nyilvános céges kutatás.
- [x] Alapértelmezett célpiac: Magyarország.
- [x] Több országra váltható célpiac, többek között Németország, Franciaország, Ausztria, Svájc, Egyesült Királyság, Olaszország, Spanyolország, Lengyelország, Hollandia, Egyesült Államok és világméretű keresés.
- [x] A célpiac tartós mentése a Supabase `settings` táblájába.
- [x] Iparági és cégméret-korlátozás nélküli kutatás; a kérésben megadott üzleti brief figyelembevétele.
- [x] Legfeljebb 15 új cég feldolgozása egy kutatási futásban.
- [x] Duplikátumok szűrése cégnév és domain alapján.
- [x] A hivatalos weboldal és a támogató forrás URL-jének ellenőrzése a Google grounding hivatkozásaihoz képest.
- [x] Kutatási minőségkapu: a modell által jelzett bizonyosságot a ténylegesen visszaadott, konkrét illeszkedési bizonyítékok számához igazítja.
- [x] Két vagy több bizonyíték szükséges a magas bizonyossághoz; egy bizonyíték esetén legfeljebb közepes bizonyosság és 70/100-as illeszkedési plafon adható.
- [x] Bizonyíték vagy konkrét illeszkedési indoklás hiányában alacsony bizonyosságot és legfeljebb 40–50/100-as pontszámot alkalmaz.
- [x] A bizonyítékhiány nem automatikus negatív tény; a cégkutatás továbbra is csak ellenőrizhető Google grounding forrásokra ment céges rekordot.
- [x] A cégprofil, iparág, ország, lehetséges AI/automatizálási illeszkedés, nyilvános bizonyítékok, kutatási bizonyosság és javasolt következő kutatási lépés rögzítése.
- [x] Külön 0–100-as előzetes üzleti illeszkedési becslés.
- [x] A kutatás kizárólag céges adatokat ment; nem gyűjt személyes neveket, személyes e-mail-címeket vagy telefonszámokat.
- [x] Az új kutatási lead e-mail-címe üres, státusza `research`, `approved_to_contact=false`, `consent_basis=null`.
- [x] A céges kutatási rekord létrehozása nem ad kapcsolatfelvételi engedélyt.
- [x] A célpiacváltás és a leadkutatás kétlépcsős jóváhagyást használ: előnézet, majd külön `Jóváhagyom`; `Elutasítom` megszakítja.
- [x] Napi GitHub Actions kutatási workflow: 08:00 UTC, legfeljebb 15 új cég; kézzel is indítható.

## 5. Leadprioritás és piaci intelligencia

- [x] Strukturált kutatási rekordok rangsorolása 0–100 közötti kutatási prioritással.
- [x] A prioritás súlyai: üzleti illeszkedés 60%, kutatási bizonyosság 25%, nyilvános bizonyítékok mennyisége 15%.
- [x] Alacsony kutatási bizonyosság esetén a prioritási pontszám felső korlátos.
- [x] Iparág és ország szerinti piaci összesítés.
- [x] Mintanagyság, átlagos illeszkedési pontszám és bizonyossági megoszlás megjelenítése.
- [x] Két vagy több példával rendelkező szegmensek külön kiemelése.
- [x] A rendszer jelzi, hogy ezek a korábbi kutatási találatok leíró mintái, nem reprezentatív piackutatás.
- [x] A kutatási prioritás, az üzleti illeszkedés és a weboldal-információs pontszám külön mérőszámok.

## 6. Hosszú távú memória

- [x] Külön Supabase `jarvis_memory` tábla.
- [x] Csak kifejezett felhasználói utasításra ment memóriát; a hétköznapi beszélgetés nem kerül automatikusan elmentésre.
- [x] Kategóriák: üzleti preferencia, döntés, tapasztalat/eredmény és tanulság.
- [x] Memória mentése például: `Jegyezd meg, hogy Magyarország az elsődleges piacunk.`
- [x] Döntés mentése: `Jegyezd meg a döntést: ...`
- [x] Tapasztalat mentése: `Mentsd el a tapasztalatot: ...`
- [x] Tanulság mentése: `Rögzítsd a tanulságot: ...`
- [x] Aktív memóriák listázása: `Mutasd a memóriádat`.
- [x] Egyes emlékek célzott inaktiválása: `Felejtsd el a ...`; minden aktív emlék inaktiválása: `Felejtsd el mindent`.
- [x] Relevanciaalapú memória-visszakeresés, korlátozott számú elem átadása az AI-nak.
- [x] Kategóriaérzékeny visszakeresés: döntési kérdésnél a döntések, eredmény/hiba kérdésnél a tapasztalatok és tanulságok, működési preferenciáknál a preferenciák kapnak előnyt.
- [x] A chatben átadott memóriaelemek és a memórialistában megjelenő elemek kategóriacímkét kapnak, így az AI és a felhasználó látja, milyen típusú emlékről van szó.
- [x] A kategória csak rangsorolási előny: a releváns, más kategóriájú emlékek sem vesznek el automatikusan.
- [x] Jelszavak, API-kulcsok, elérhetőségek és érzékeny személyes adatok mentésének szűrése.
- [x] A memória tartalma adat, nem rendszerutasítás.
- [!] A memória nem önálló, automatikus tanulás: az üzleti eredményeket és döntéseket a felhasználónak kell kifejezetten rögzítenie.

## 7. Üzleti tanulás és döntéstámogatás

- [x] A JARVIS a mentett céges kutatási rekordokból iparági és módszermintákat készít.
- [x] A kifejezetten rögzített döntéseket összekapcsolja azokkal az eredményrekordokkal, amelyekben a döntés mezője explicit módon szerepel.
- [x] A rögzített eredményeket pozitív, negatív és nem besorolható csoportba rendezi.
- [x] Ismétlődő iparág–módszer mintát csak legalább két explicit eredményrekord esetén jelez.
- [x] A döntés és eredmény együttjárását nem állítja be bizonyított ok-okozati kapcsolatként.
- [x] Döntéstámogatási mód: cél, bizonyíték, feltételezés, ismeretlen tényező, alternatíva, előny, költség/erőforrás, kockázat és visszafordíthatóság mérlegelése.
- [x] Ellenérv, kis költségű validációs lépés, mérhető sikerkritérium, leállítási feltétel és bizonyossági szint kérése a döntési válaszokban.
- [x] A rendszer utasítást kap arra, hogy ne találjon ki ROI-, bevétel- vagy konverziós adatokat.
- [!] Az üzleti tanulás minősége az explicit módon rögzített döntések és tényleges eredmények mennyiségétől függ.

## 8. Feladatkezelés a chatből

- [x] Feladat létrehozása természetes nyelv helyett egyértelmű, strukturált paranccsal.
- [x] Feladat módosítása: cím, határidő, prioritás.
- [x] Feladat lezárása.
- [x] Prioritások: `normal`, `high`, `urgent`.
- [x] Határidő kezelése magyarországi időzónával; a megadott nap 23:59-kor jár le.
- [x] Kétlépcsős jóváhagyás minden feladatmódosítás előtt.
- [x] Jóváhagyás előtt előnézet készül; a feladat azonosítóját és címét a rendszer ellenőrzi.
- [x] A következő felhasználói üzenet érvényteleníti a függőben lévő jóváhagyást.
- [x] Lezáráskor a státusz, a befejezési idő és a módosítási idő frissül.
- [x] A funkció a meglévő Supabase `tasks` táblát használja.
- [x] Nincs feladattörlési funkció, és a feladatkezelés nem módosít leadeket.

Példák:
```text
Hozz létre feladat: Ajánlat ellenőrzése; határidő=2026-12-01; prioritás=high
Módosítsd a feladatot: UUID; prioritás=urgent; határidő=2026-12-02; cím=Új cím
Zárd le a feladatot: UUID
```

## 9. Napi vezetői jelentés és proaktív figyelés

- [x] Napi vezetői jelentés a leadekről, feladatokról, kutatási prioritásokról és következő lépésekről.
- [x] Lejárt, mára esedékes, sürgős és magas prioritású nyitott feladatok kiemelése.
- [x] Lejárt utánkövetések jelzése kizárólag jóváhagyott és le nem iratkozott rekordoknál.
- [x] Napi új cégek és a legmagasabb kutatási prioritású lehetőségek listázása.
- [x] Egységesebb napi akcióterv: a lejárt és mára esedékes feladatok mellett a határidő nélküli magas/sürgős prioritású nyitott feladatokat is figyelembe veszi.
- [x] Külön vezetői fókuszblokk összegzi a konkrét napi lépések és a kiemelt feladatok számát.
- [x] Az új cégek napi dátum szerinti besorolása Budapest időzónájában történik, nem a nyers UTC dátum első tíz karaktere alapján.
- [x] Napi változásfigyelés: új cégek, leadstátusz-változások, új feladatok, feladatstátusz-, határidő- és prioritásváltozások.
- [x] Lejárt és mára esedékes feladatok külön monitorozása.
- [x] Első monitorfutáskor alapállapotot rögzít; nem jelenti tévesen újnak a már létező rekordokat.
- [x] A technikai pillanatkép kizárólag a `jarvis_proactive_state` táblába íródik; leadet és feladatot nem módosít.
- [x] A jelentés naponta 08:30 UTC-kor futó GitHub Actions workflow-val készül.
- [x] A jelentés megjelenik a GitHub Actions futás összefoglalójában, és 14 napig artifactként elérhető.
- [!] Ez GitHub Actions jelentés, nem telefonos push értesítés és nem e-mail.
- [!] A napi monitor legfeljebb 2000 leadet és 1000 feladatot vizsgál; a napi briefing legfeljebb 1500 leadet és 1000 feladatot dolgoz fel.

## 10. Biztonság, adatvédelem és hozzáférés

- [x] Titkok környezeti változókból / Codespaces vagy GitHub Actions Secrets konfigurációból olvashatók.
- [x] A Supabase service-role kulcs szerveroldali titokként kezelendő; nem kerülhet kliensoldalra vagy Gitbe.
- [x] A Supabase-sémában az érintett táblákon RLS engedélyezve van.
- [x] A dashboard jelszavas belépést használ.
- [x] A bejelentkezési munkamenet legfeljebb 8 óráig érvényes.
- [x] A függőben lévő jóváhagyás lejár a munkamenet megszűnésekor.
- [x] A webes lekérések SSRF-kockázatának csökkentésére külön biztonságos HTTP-modul van.
- [x] A tesztek nem igényelnek valódi Supabase- vagy Gemini-kulcsokat.
- [x] A rendszer nem tekinti a nyilvános cégadat megtalálását marketing-hozzájárulásnak.

## 11. E-mail és korábbi automatizációk – jelenlegi állapot

- [x] E-mail-tervezet készíthető a chatben, másolható formában.
- [x] A tervezet nem kerül automatikusan adatbázisba.
- [x] A rendszer nem talál ki címzettet.
- [x] Az e-mail-küldés az `email_utils.py` fájlban kódszinten le van tiltva (`EMAIL_DELIVERY_ENABLED = False`).
- [x] A közvetlen SMTP-küldési függvény is hibával leáll, amíg ez a biztonsági zár aktív.
- [x] A korábbi leadküldő és utánkövető szkriptek nem részei az aktív chatfolyamatnak; a küldés tiltott.
- [x] A korábbi általános JARVIS/pipeline workflow-k kézi no-op állapotban vannak; nincs ütemezett import, inbox-figyelés vagy küldés.
- [!] A régi CSV-import, inbox-figyelő, válaszelemző, e-mail-küldő és utánkövető modulok forrásfájljai továbbra is a repositoryban vannak, de nem tekintendők aktív, használatra kész chatfunkciónak.
- [!] E-mail-küldés nincs engedélyezve, és ez a dokumentum nem ad felhatalmazást a bekapcsolására.

## 12. Tesztelés és automatizált minőségellenőrzés

- [x] GitHub Actions CI minden push és pull request esetén fut.
- [x] Python 3.11 környezetben telepíti a függőségeket.
- [x] Lefuttatja a `python -m compileall -q .` szintaxisellenőrzést.
- [x] Lefuttatja a `python -m pytest -q` teszteket.
- [x] Tesztek fedik többek között a memória-kezelést, döntéstámogatást, üzleti tanulást, piaci összesítést, leadprioritást, leadkutatást, feladatműveleteket, napi jelentést, proaktív figyelést, biztonságos HTTP-lekérést, dashboard-szerződést, e-mail-biztonságot és a rendszerdiagnosztikát.
- [x] A rendszerdiagnosztika javított tesztelvárásaival a CI sikeres: 96 teszt sikeres, a `compileall` és a teljes pytest futás is zöld. [GitHub Actions – 43782429221](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/43782429221).
- [!] A sikeres CI a kód és az automatizált tesztek eredményét igazolja, nem az éles szolgáltatások működését.

## 13. Még ellenőrizendő / telepítéstől függő elemek

Az alábbiak nem feltétlenül hiányzó funkciók: az éles környezetben való működésük külön ellenőrzést igényel.

- [ ] Ellenőrizni, hogy a legfrissebb `supabase/schema.sql` lefutott-e a tényleges Supabase-projekten.
- [ ] Ellenőrizni, hogy a `jarvis_memory` és `jarvis_proactive_state` táblák ténylegesen léteznek-e és az RLS-beállítások megfelelnek-e.
- [ ] Ellenőrizni a GitHub Actions külön titkait: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` vagy `SUPABASE_KEY`, valamint a leadkutatáshoz `GEMINI_API_KEY`.
- [ ] Ellenőrizni a Codespaces Secrets / Streamlit secrets konfigurációt és a JARVIS belépési jelszót.
- [ ] Valódi, de kontrollált környezetben ellenőrizni a Gemini-kapcsolatot és a chatválaszokat.
- [ ] Valódi Supabase-adatokkal ellenőrizni az olvasási műveleteket, memória-mentést, jóváhagyott feladatműveleteket és céges leadkutatási beszúrást.
- [ ] Ellenőrizni, hogy a napi leadkutatási és napi briefing workflow-k ténylegesen elindulnak-e, a jelentések létrejönnek-e, és a szükséges titkok rendelkezésre állnak-e.
- [ ] Ellenőrizni, hogy a `jarvis_proactive_state` pillanatkép első és későbbi futásai a tényleges adatbázissal helyesen működnek-e.
- [ ] Éles Streamlit/Codespaces felületen manuális felhasználói tesztet végezni.

## 14. Ami már kifejezetten jól működik / a JARVIS erősségei

Az alábbiak a jelenlegi kódban megvalósított, üzletileg hasznos képességek:

- **Forrásalapú cégkutatás:** nem pusztán cégnévlistát készít; nyilvános forrásokat, hivatalos weboldalt, üzleti illeszkedést és további kutatási lépést kapcsol a cégekhez.
- **Óvatosabb pontozás:** a kutatási bizonyosság és az illeszkedési pontszám nem lehet erősebb a ténylegesen felsorolt bizonyítékoknál. Ez csökkenti a magabiztos, de gyengén alátámasztott találatok kockázatát.
- **Külön kezeli a különböző mérőszámokat:** a weboldal információgazdagsága, az üzleti illeszkedés és a kutatási prioritás nem mosódik össze.
- **Megőrzi az üzleti tapasztalatot:** a döntések, eredmények, tanulságok és preferenciák külön kategóriákban tárolhatók; a visszakeresés a kérdés típusához igazodik.
- **Nem talál ki üzleti sikert:** csak kifejezetten rögzített eredményeket használ a módszerek és döntések értékelésére; az együttjárást nem nevezi bizonyított ok-okozatnak.
- **Cselekvésre fordítja az adatokat:** a napi terv a lejárt, mára esedékes és magas prioritású feladatokat, az engedélyezett utánkövetéseket és a kiemelt kutatási lehetőségeket egy sorrendbe rendezi.
- **Emberi kontrollt tart fenn:** a feladatmódosítások és leadkutatási műveletek jóváhagyást igényelnek; a céges kutatás önmagában nem ad kapcsolatfelvételi engedélyt.
- **Biztonságos alapbeállítások:** az e-mail-küldés kódszinten tiltott, a személyes leadadatok és a szabad szöveges CRM-megjegyzések nem kerülnek automatikusan az AI-kontekstusba.

**A legnagyobb jelenlegi érték:** a JARVIS már összeköti a nyilvános cégkutatást, a korábbi üzleti tapasztalatot és a napi feladatprioritásokat. Így nem csak adatokat listáz, hanem segít eldönteni, mit érdemes először ellenőrizni vagy elvégezni.

## 15. Rendszerdiagnosztika a chatből

- [x] Külön, kézzel indítható diagnosztika a chatben az „Ellenőrizd a rendszert” vagy „Rendszerdiagnosztika” paranccsal.
- [x] A Supabase URL, szerveroldali kulcs, Gemini API-kulcs és dashboard-jelszó konfigurációjának meglétét ellenőrzi; értékeket és titkokat nem jelenít meg.
- [x] Supabase-kapcsolat inicializálása és hat alapvető tábla korlátozott, csak olvasási lekérdezése: leads, tasks, settings, logs, jarvis_memory, jarvis_proactive_state.
- [x] Rövid Gemini API-próbakérést futtat, ha a kulcs konfigurálva van.
- [x] Ellenőrzi, hogy az e-mail-küldési biztonsági zár továbbra is tiltott állapotban van-e.
- [x] Minden ellenőrzéshez külön OK / figyelmet igényel állapotot és rövid hibaleírást ad.
- [x] A diagnosztika nem módosít leadet, feladatot, memóriát vagy beállítást; nem indít kutatást és nem küld e-mailt.
- [!] A Gemini-próbakérés API-használatot és esetleges költséget jelenthet.
- [!] A sikeres pillanatfelvétel nem garantál folyamatos szolgáltatás-elérhetőséget; a GitHub Actions ütemezéseket és a teljes éles folyamatokat nem futtatja le.

A diagnosztika indítása a JARVIS chatben:
```text
Ellenőrizd a rendszert
```

## 16. Rövid összegzés

A repository alapján a JARVIS már rendelkezik chatfelülettel, Gemini-alapú üzleti asszisztenssel, Supabase-adatolvasással, weboldal-elemzéssel, bizonyítékminőség-kapuval kiegészített forrásalapú globális céges leadkutatással, leadprioritással, piaci intelligenciával, kategóriaérzékeny explicit hosszú távú memóriával, döntéstámogatással, döntés–eredmény összekapcsolással, jóváhagyásos feladatkezeléssel, kibővített napi vezetői akciótervvel, proaktív változásfigyeléssel és automatizált teszteléssel.

**Fontos különbség:** a funkciók kódszinten elkészültek és a legutóbbi CI sikeres, de a valós Supabase/Gemini-integrációt, a Codespaces alkalmazást és az ütemezett GitHub Actions futásokat külön, éles környezetben kell ellenőrizni. Az e-mail-küldés szándékosan letiltott.
## 17. Átfogó funkcióellenőrzés – kód- és tesztlefedettségi audit

### Automatizáltan ellenőrzött területek

- [x] Chat és adatlekérési szerződés: dashboard-contract és retrieval tesztek.
- [x] Gemini-közös segédfüggvények, beszélgetési előzmények és konfigurációs segédek.
- [x] Supabase-séma és RLS-táblák szerződéses ellenőrzése.
- [x] Memória mentése, visszakeresése és célzott törlése.
- [x] Üzleti tanulás, döntés–eredmény kapcsolatok és stratégiai összesítések.
- [x] Döntéstámogatási útmutató.
- [x] Globális céges leadkutatás, források, duplikációk, piaci váltás és kapcsolatfelvételi engedély hiánya.
- [x] Leadpontozás és intelligens kutatási prioritás.
- [x] Feladat létrehozása, módosítása, lezárása és jóváhagyási folyamat.
- [x] Napi vezetői jelentés és proaktív változásfigyelés.
- [x] Biztonságos HTTP-kérések és az e-mail-küldés tiltása.
- [x] Válaszlevél-besorolás és a leiratkozási jelzések felismerése.
- [x] Chatből indítható rendszerdiagnosztika.

### Célzott regressziós tesztekkel lefedett további modulok

- [x] web_auditor.py: HTML-feldolgozás, átirányítások, tartalomkorlát, HTTP-hibák és válaszlezárás mockolt tesztjei.
- [x] inbox_monitor.py: IMAP-válaszok sorrendje, ismételt üzenetek, feladóellenőrzés, adatbázis-frissítések és a visszavonhatatlan leiratkozási állapot mockolt tesztjei. A háttérfolyamat továbbra sem aktív.
- [x] inbox_analyzer.py: kompatibilitási osztályozó és központi Gemini-modellkonfiguráció tesztjei.
- [x] lead_gen.py: CSV-import, hibás sorok, időzónás hozzájárulás, mezőkorlátok és duplikációkezelés tesztjei. Ez a régi, kézi importsegéd; nem azonos a chatből indított globális kutatással.
- [x] stats.py és jarvis_status.py: státuszlekérdezések, importkori mellékhatás-mentesség és hibakezelés tesztjei.
- [x] email_sender.py és follow_up.py: a tiltott állapot és a közvetlen SMTP-küldési zár tesztelt; a tényleges küldési ág szándékosan nem aktiválható, ezért nem engedélyezett funkció.

### Ütemezés és működési korlátok

- [x] A CI workflow sikeresen lefutott: Python compileall és 118 automatizált teszt.
- [x] A globális leadkutatás és a napi vezetői jelentés két külön ütemezett workflow.
- [x] A régi, duplikált pipeline-ok kézi no-op workflow-ként vannak hatástalanítva.
- [!] A workflow-fájl megléte nem bizonyítja, hogy a GitHub Actions titkok be vannak állítva vagy a Supabase/Gemini külső szolgáltatások elérhetők.
- [!] Nincs teljes, valós Supabase/Gemini/IMAP/SMTP végpontokat használó integrációs teszt. Az ilyen teszteket csak kontrollált, engedélyezett környezetben szabad futtatni; SMTP-küldés továbbra sem engedélyezett.
- [!] A mockolt tesztek nem helyettesítik az élő IMAP-, Supabase- és Gemini-kapcsolat ellenőrzését. Az inbox monitor nem aktív workflow, az SMTP-küldés továbbra is tiltott.


## 18. 2026-11-17 – hibajavítási és tesztbővítési kör

### Javítások
- [x] Gemini alapértelmezett modell frissítve stabil `gemini-3.8-flash` azonosítóra. A régi `gemini-2.5-flash` és `gemini-2.5-pro` beállítás automatikusan az új alapértelmezésre vált.
- [x] A meglévő Supabase `leads` táblához idempotens `website` oszlopmigráció került a teljes sémába és külön migrációs fájlba.
- [x] A chatből indítható diagnosztika külön ellenőrzi a `leads.website` oszlopot is.
- [x] A napi briefing régi Supabase-séma esetén is elkészül: ha a `website` oszlop hiányzik, biztonságosan a többi leadmezővel folytatja, és jól látható figyelmeztetést tesz a jelentésbe.
- [x] Az IMAP monitor a tárolt utolsó Message-ID utáni válaszokat dolgozza fel; ha a marker kikerült a legutóbbi öt üzenetből, csak a legfrissebbet veszi fel, így elkerüli a régi válaszok ismételt feldolgozását.
- [x] A régi CSV-import csak timezone-aware, időbélyegzett, explicit hozzájárulású és jóváhagyott rekordot fogad el; az e-mail-duplikációt kis-/nagybetűtől függetlenül ellenőrzi.
- [x] A kompatibilitási inbox osztályozó is a központi Gemini-modellbeállítást használja.
- [x] A weboldal-audit HTTP-kérésének hibás behúzása javítva.

### Telepítést igénylő adatbázis-migráció
A kódmódosítás önmagában nem frissíti a külső Supabase-adatbázist. A Supabase SQL Editorban futtasd le a `supabase/migrations/20261117_add_leads_website.sql` tartalmát, vagy a teljes frissített `supabase/schema.sql` fájlt. A migráció idempotens és nem töröl meglévő üzleti adatot. Ezt a külső adatbázison még a felhasználónak kell lefuttatnia; a GitHub commit nem módosítja automatikusan a Supabase-projektet.

### Tesztelési státusz
- A frissített GitHub Actions CI sikeres: Python compileall és **118/118 teszt**.
- A tesztek lefedik a Gemini-modellválasztást, az IMAP üzenetsorrendet és leiratkozást, a CSV-hozzájárulást, a weboldal-auditot, a státuszsegédeket és a Supabase-oszlopdiagnosztikát.
- Az éles Supabase/Gemini/IMAP integrációk külön ellenőrzendők; az automatizált tesztek mockolt külső szolgáltatásokat használnak.
- Az e-mail-küldés változatlanul kódszinten letiltott.
