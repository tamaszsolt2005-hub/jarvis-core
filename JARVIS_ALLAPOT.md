# JARVIS – megvalósított funkciók és aktuális állapot

**Utolsó kódfelülvizsgálat:** 2026-11-16  
**Repository:** `tamaszsolt2005-hub/jarvis-core`  
**Ág:** `main`

Ez a dokumentum a repository aktuális forráskódja, README-je, Supabase-sémája, GitHub Actions workflow-jai és tesztjei alapján készült. A „kész” azt jelenti, hogy a funkció implementálva van a kódban. Ez önmagában nem bizonyítja, hogy az éles Supabase/Gemini-kapcsolat, a Codespaces-felület vagy az ütemezett háttérfolyamat ténylegesen működik.

## 1. A JARVIS jelenlegi alapja

- [x] Chat-központú Streamlit alkalmazás, egyetlen beszélgetési felülettel.
- [x] Sötét, prémium megjelenésű JARVIS felület.
- [x] Gemini-alapú magyar nyelvű válaszgenerálás.
- [x] A modell neve környezeti konfigurációból választható; alapértelmezésben Gemini 2.5 Flash.
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
- [x] Tesztek fedik többek között a memória-kezelést, döntéstámogatást, üzleti tanulást, piaci összesítést, leadprioritást, leadkutatást, feladatműveleteket, napi jelentést, proaktív figyelést, biztonságos HTTP-lekérést, dashboard-szerződést és e-mail-biztonságot.
- [x] A legutóbbi, a döntés–eredmény összekapcsolás módosításait is tartalmazó CI-futás sikeres: [GitHub Actions – 43779618293](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/43779618293).
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

## 14. Rövid összegzés

A repository alapján a JARVIS már rendelkezik chatfelülettel, Gemini-alapú üzleti asszisztenssel, Supabase-adatolvasással, weboldal-elemzéssel, forrásalapú globális céges leadkutatással, leadprioritással, piaci intelligenciával, explicit hosszú távú memóriával, döntéstámogatással, döntés–eredmény összekapcsolással, jóváhagyásos feladatkezeléssel, napi vezetői jelentéssel, proaktív változásfigyeléssel és automatizált teszteléssel.

**Fontos különbség:** a funkciók kódszinten elkészültek és a legutóbbi CI sikeres, de a valós Supabase/Gemini-integrációt, a Codespaces alkalmazást és az ütemezett GitHub Actions futásokat külön, éles környezetben kell ellenőrizni. Az e-mail-küldés szándékosan letiltott.
