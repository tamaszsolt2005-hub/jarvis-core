# JARVIS – főrendszer-készültségi felmérés

**Dátum:** 2026-11-26  
**Vizsgált ág:** `feature/company-research-dashboard-readonly` (PR #28, stacked PR #27 → #26)  
**Vizsgált commit:** `3974a808d72134ca27291eddec498ba01ccd9d4c`  
**Állapot:** fejlesztési ág; nem production release és nem merge-ölt állapot.

## 1. Mit nevezünk kész főrendszernek?

A JARVIS főrendszere a napi belső üzleti asszisztensi munkafolyamat: magyar nyelvű chat, lead- és cégadatok kezelése, forrásolt leadkutatás, lead scoring, feladatkezelés jóváhagyással, üzleti memória, briefing, analitika és audit. Ezt külön kell választani a teljes autonóm SaaS-ügynök víziótól.

**Főrendszer-kész** akkor mondható ki, ha a fenti funkciók egyetlen, dokumentált helyi futtatási útvonalon végig használhatók; az adatbázis- és jogosultsági szerződések izolált környezetben igazoltak; a hibák, duplikációk és jogosulatlan műveletek fail-closed módon kezeltek; a teljes aktuális CI zöld; és az alkalmazás kézi smoke tesztjei is dokumentáltak.

Ez nem jelenti azt, hogy az autonóm kutatás, SaaS-termékötlet motor, outreach vagy AI-fejlesztési pipeline is kész.

## 2. A mostani javítások és dokumentációfrissítések

- A Gemini Google Search grounding provider szinkron hívása alatt konfigurálható időközű, leállítható háttérszál frissíti a worker lease-t.
- A heartbeat hamis eredménye vagy kivétele lease-vesztést jelez; ilyen esetben a provider eredménye nem adható vissza sikeres kutatási eredményként.
- A heartbeat szál leállítása és joinolása után is ellenőrizzük a lease-vesztést, így a kérés legvégén bekövetkező elvesztés sem csúszik át sikeres eredményként.
- Két célzott teszt került a `tests/test_company_research_execution.py` fájlba: periodikus lease-megújítás blokkolt provider-kérés alatt, illetve lease-vesztés kezelése.
- Frissült a master dokumentáció, a fejlesztési roadmap és az aktuális állapot dokumentuma; a korábbi, már nem érvényes heartbeat-leírásokat korrigáltuk.
- A javítás a PR #28 fejlesztési ágán van. Nem történt merge, production migráció, deploy, secret-módosítás vagy e-mailküldés.

### Ellenőrzési státusz

- A core lead → scoring → task approval → PostgreSQL → audit javításokat tartalmazó `36d615f6770ce097ba7a69954a7748ad237b8fd0` commiton a push- és PR-triggerelt teljes JARVIS CI sikeres volt: run `45873698960` és `45873705730`.
- A két futás Python/AppTest/Playwright tesztjei, PostgreSQL 17 integrációs/pgTAP ellenőrzései, backup–restore lépései és a build ellenőrzések sikeresek.
- A dashboard navigációs audit után újabb módosítások kerültek a branchre (Settings oldal, AppTestek, üres tasklista melletti utánkövetési sor javítása); ezek a későbbi commitok még nem szerepelnek a fenti zöld futásokban. A teljes zöld minősítéshez az új aktuális HEAD-en ismételt teljes CI szükséges.

## 3. Főrendszer-funkciók állapotképe

| Terület | Kód/dokumentáció alapján | A késznek minősítés feltétele |
|---|---|---|
| Magyar nyelvű chat | Implementált, Gemini-konfigurációt igényel | Helyi, valós konfigurációval végzett chat smoke; hiba- és timeout-kezelés |
| Leadkutatás és cégazonosítás | Forrásolt kutatás és közös deduplikációs út implementált a fejlesztési ágakban | Aktuális CI, izolált DB concurrency teszt, valós provider smoke külön tesztkörnyezetben |
| Lead scoring és workflow ajánlás | Implementált | Valós lead mintákon eredmény- és magyarázhatósági ellenőrzés |
| Task-kezelés | Jóváhagyásos create/update/close út és atomikus SQL szerződés implementált | Teljes chat → approval → DB → audit E2E; jogosultsági és visszajátszási teszt |
| Task center | Read-only oldal; üres tasklista mellett is megjelenik az utánkövetési sor | Szűrés/rendezés/határidő, üres/hibaállapot és jogosultsági kézi smoke |
| Kutatási dosszié és előzmény | Dosszié, snapshot store és read-only előzmény UI implementált; legacy dashboard módban elérhető | A store és worker közti tartós mentési adatút igazolása; Auth/RLS olvasási jogosultság és UI smoke |
| Kutatási job/worker | Job lifecycle, RPC repository, queue, worker, Gemini adapter és one-shot runtime kódban; két új PostgreSQL SQL tesztcsomag elkészült | Az izolált pgTAP/dblink tesztek futtatása még hátra van; job → provider → snapshot E2E, lease/retry és teljes költségelszámolás igazolása szükséges |
| Memória | Explicit mentési/listázási/inaktiválási funkció | Kategória-, jogosultság-, adatmegőrzési és valós DB smoke |
| Napi briefing és analitika | Implementált komponensek | Helyi, adatbázissal végzett smoke és helyességellenőrzés |
| Audit | Külön Supabase Auth-admin belépéssel védett megjelenítés/export és SQL hash-chain alapok | Valós admin belépés, szerepkör, láncintegritás és export smoke; a közös dashboard-jelszó nem elegendő |
| Beállítások és konfiguráció | Működő, read-only Settings oldal: konfiguráció jelenlétét jelzi titokérték nélkül; settings.read jogosultság; diagnosztika kézi indítású és Auth módban admin-only | Tartós felhasználói preferenciák és biztonságos, mentett beállításkezelés még nincs; titkok/Auth/RLS/e-mail-zár nem szerkeszthető a UI-ból |
| E-mail | Outbound hard-disabled | Ez szándékos biztonsági korlát; küldés nem része a főrendszer készre jelentésének |



### 3.1 Dashboard navigációs és jogosultsági mátrix

| Oldal | Funkció | Hozzáférés és korlát |
|---|---|---|
| Chat | Magyar nyelvű beszélgetés és jóváhagyásos művelet-előkészítés | A bejelentkezett munkamenet adatbázis-kliense; a módosítások külön jóváhagyási és backend jogosultsági kapun mennek át |
| Feladatok | Read-only feladatközpont, szűrés/rendezés, utánkövetési sor | Auth módban tasks.read; a módosítás továbbra is a chat jóváhagyási útján történik |
| Analitika | Naplóalapú mutatók és grafikonok | Auth módban analytics.read; adatforráshiba nem jelenik meg üres adatként |
| Cégkutatás | Read-only, forrásolt snapshot előzmények | Legacy dashboard módban olvasható; Auth módban fail-closed, amíg a snapshot RLS olvasási jogosultság nincs kivezetve |
| Audit napló | Auditlapozás, hash-lánc ellenőrzés és auditált CSV export | Külön, ellenőrzött Supabase Auth admin belépés szükséges; a közös dashboard-jelszó nem elegendő |
| Beállítások | Runtime konfigurációs státuszok és kézi rendszerdiagnosztika | Auth módban settings.read; teljes diagnosztika admin-only; titokértékek nem jelennek meg, beállítások nem módosíthatók |

## 4. Mi hiányzik a főrendszer készre jelentéséhez?

### P0 – kötelező lezárás

1. **Célzott aktuális regresszióellenőrzés.** Először csak az új/módosított hibakezelési modulok unit tesztjei és a két korábban elbukott Settings AppTest futtatandó. A változatlan backup–restore, korábban sikeres core E2E és más, azóta nem módosított területek tesztjeit nem ismételjük meg. Teljes CI csak a worker/snapshot/Auth integrációs mérföldkő végén, illetve merge/release előtt szükséges.
2. **Teljes helyi smoke teszt.** Friss, dokumentált fejlesztői környezetben telepítés, konfigurációellenőrzés, Streamlit indulás, chat, leadkutatás, lead lista, task approval, task center, memória, briefing, analitika, audit és kutatási előzmény végigpróbálása.
3. **Végponttól végpontig tartó core workflow teszt.** Lead létrehozás/azonosítás → scoring → task javaslat → approval → atomikus DB művelet → audit → outcome feldolgozás. Ellenőrizni kell a duplikált kérés, timeout, visszajátszás, párhuzamos kérés és audit-hiba viselkedését.
4. **Dashboard navigációs leltár – részben lezárva.** A Chat, Feladatok, Analitika, Cégkutatás, Audit napló és Beállítások mind valódi Streamlit navigációs gomb és dedikált útvonal. A Beállítások read-only konfigurációs áttekintést és kézi diagnosztikát ad. A cégkutatási előzmény Auth/RLS módban szándékosan fail-closed, az Audit külön admin Auth-belépést kér. A valós Auth/RLS és manuális smoke továbbra is szükséges.
5. **Konfigurációs és hibaállapotok – implementálva, célzott teszt még szükséges.** A hiányzó/hibás konfiguráció, hálózati hiba, rate limit, jogosultsághiány és timeout központi kategorizálást és titokmentes magyar útmutatót kapott. A módosított hibakezelési teszteket és a két javított Settings AppTestet célzottan ellenőrizni kell.

### P1 – megbízható belső használat és későbbi release előfeltétele

6. **Izolált PostgreSQL worker tesztek – forrás elkészült, futtatás hátra van.** A `company_research_jobs.test.sql` 15 pgTAP ellenőrzést tartalmaz a create idempotenciára, napi/óránkénti/domain kvótára, claim plafonra, heartbeat-re, actual-cost settlementre és auditra. A `company_research_jobs_concurrency.test.sql` 12 pgTAP assertionnel két független `dblink` sessionben vizsgálja a párhuzamos budget reservationt és claimet. A helyi `supabase test db` futás eredménye még nem igazolt. A lease expiry/reclaim és retry/dead-letter SQL-életciklus célzott lefedése még szükséges.
7. **Kutatási adatút lezárása.** A job handler eredményének snapshot store-ba mentése, a lead rekordhoz kapcsolás, audit esemény és hiba esetén konzisztens retry/rollback legyen E2E tesztelve. Jelenleg a provider/runtime önmagában még nem bizonyít teljes, tartós cégkutatási adatfolyamot.
8. **Valós provider smoke izolált tesztkörnyezetben.** Injektált Gemini klienssel, tesztkulccsal és szigorú költségkerettel ellenőrizni a grounding metaadatokat, usage adatokat, timeoutot, retryt és heartbeatet. Production secret vagy production DB nem használható ehhez.
9. **Auth/RLS és szerepkör tesztek.** Az alkalmazás tényleges felhasználói hozzáférése, service-role határok és read/write RPC-k jogosultságai legyenek dokumentálva és izolált tesztben igazolva.
10. **Üzemeltetési alapok.** Strukturált, titokmentes logok, health check, konfigurációs leírás, mentés/visszaállítási eljárás, hibajelzés és kézi rollback terv.

### P2 – nem blokkolja a belső core asszisztens készre jelentését

- Automatikus scheduler és folyamatos háttérkutatás.
- Teljes SaaS-termékötlet motor, pontozás és piaci alternatíva elemzés.
- Globális és cégenkénti „mit ne ajánljunk” napló, szemantikus ütközésvizsgálat.
- Személyre szabott ajánlatgenerálás és outreach workflow.
- Országonkénti marketingjogalap, suppression és outbound email engedélyezése. Az outbound email maradjon hard-disabled, amíg külön jogi/biztonsági és termékjóváhagyás nincs.
- AI-assisted termékfejlesztés, szerződéses kapuk, automatikus build/test/release és tanulási ciklus.

## 5. Külön production release kapuk

A főrendszer helyi fejlesztői készültsége és a production release két külön döntés. Production release előtt külön szükséges: JARVIS app-host kiválasztása; friss, read-only Supabase schema/migration ledger audit; migration drift egyeztetés; független SQL review; Auth/JWT/RLS modell és smoke; app deploy és runtime health; backup/restore bizonyíték; migrációs rollout és rollback terv. Ezek közül semmi nem következik automatikusan a PR #28 CI sikeréből.

Production Supabase módosítás, migration futtatás, GRANT/REVOKE, Auth/RBAC, secret, deploy, outbound email és PR merge külön, konkrét jóváhagyást igényel. A jelen felmérés ezeket nem hajtja végre.

## 6. Javasolt lezárási sorrend

1. Futtassuk célzottan a hibakezeléshez és a javított Settings AppTestekhez tartozó teszteket; csak a hibás vagy módosított részt javítsuk.
2. A korábban zöld core lead → approval/task → audit E2E eredményt tartsuk meg bizonyítékként; csak akkor ismételjük, ha az érintett workflow kódja változik.
3. Zárjuk le a worker SQL konkurencia- és kutatási snapshot E2E tesztjeit izolált PostgreSQL-ben.
4. Végezzük el az Auth/RLS szerepkör- és jogosultsági teszteket izolált környezetben.
5. Végezzen a fejlesztői környezetben egy dokumentált teljes manuális smoke tesztet.
6. A fenti integrációs csomag után egyszer futtassuk a teljes CI-t, majd adjunk külön minősítést: „helyi főrendszer kész”, „belső használatra kész”, illetve „production release-re kész”.

**Dashboard-audit megállapítás (2026-11-26):** a korábban dekoratív, nem kattintható Beállítások menüpont valódi oldalt kapott. A Settings csak konfigurációs jelenlétet mutat, titokértéket nem; Auth módban settings.read jogosultság szükséges, a Gemini diagnosztikai próbakérés pedig kizárólag kézi gombnyomásra és admin szerepkörrel fut. A Feladatközpont korábban korai `return` miatt üres tasklista esetén elrejtette a jogosultsági feltételeknek megfelelő utánkövetési sort; ezt javítottuk és regressziós AppTestet adtunk hozzá. A dashboard státuszfelirata a nem igazolt „Rendszer Online” helyett „Munkamenet aktív”.

**Jelenlegi minősítés:** a JARVIS főrendszerének több alapfunkciója implementált, de a valós Auth/RLS hozzáférés, manuális teljes smoke és az aktuális commit teljes CI bizonyítéka továbbra is szükséges. A teljes autonóm SaaS-ügynök ettől függetlenül további, nagyobb fejlesztési fázisokat igényel.

## 7. Kapcsolódó dokumentumok

- [Központi dokumentáció](JARVIS_MASTER_DOCUMENTATION.md)
- [Aktuális állapot](CURRENT_STATE_AND_NEXT_STEPS.md)
- [Fejlesztési roadmap](JARVIS_DEVELOPMENT_ROADMAP.md)
- [Release gate-ek](REMAINING_WORK_AND_RELEASE_GATES.md)
- [Production állapot és migrációs terv](PRODUCTION_STATE_AND_MIGRATION_PLAN.md)

## 7. Konfigurációs, hálózati, API-limit és jogosultsági hibák

A `jarvis_errors.py` egységes `classify_error()` kategóriákat és magyar `user_facing_error()` útmutatót ad. A chat nem mutatja meg a provider teljes kivételszövegét, csak a biztonságos teendőt és – ha rendelkezésre áll – a nem érzékeny HTTP hibakódot. A Gemini kliens korlátozott retryt használ átmeneti hálózati, timeout, rate-limit és szolgáltatás-elérhetőségi hibákra; 401/403 és RLS/jogosultsági hibák esetén nincs újrapróbálkozás és nincs service-role fallback. A konfigurációs hibaüzenetek a helyi secrets/runtime konfiguráció ellenőrzésére irányítanak, de titokértéket nem kérnek.

A kategorizálás és a retry viselkedés célzott unit tesztekkel lefedett. A jelenlegi fejlesztési HEAD teljes CI-eredményét külön kell igazolni; a korábbi CI #3019 teszt jobja sikertelen volt, ezért annak zöld státusza nem állítható. Production rendszeren nem történt változtatás.


## 8. Konfigurációs és runtime hibakezelés – implementálva, célzott ellenőrzés hátra

A jarvis_errors.py egységesen kategorizálja a hiányzó/hibás konfigurációt, jogosultsági és hitelesítési hibát, rate limitet/kvótát, hálózati hibát, timeoutot, szolgáltatáskiesést és hibás kérést. A required_secret() az üres/whitespace értéket is hiányzónak tekinti, a Supabase URL required_http_url() útvonalon HTTP(S) és host validációt kapott. A chat és a diagnosztikai UI biztonságos magyar útmutatót mutat, nem a szolgáltató nyers kivételszövegét.

A Gemini kliens korlátozott retryt használ átmeneti hibákra, és csak rate-limit/szolgáltatás-túlterhelés esetén próbál tartalék modellt. 401/403, RLS és más jogosultsági hiba nem retry-zik és nem vált át service-role útra. Az implementációhoz célzott unit/AppTestek készültek; az új commiton ezek eredménye még nincs igazolva.

## 9. Tesztelési elv

A már sikeresen ellenőrzött, azóta nem módosított területeket nem teszteljük újra minden commit után. A célzott tesztelés a módosított modulokra és azok közvetlen integrációira terjed ki. Teljes CI csak nagyobb integrációs mérföldkőnél vagy merge/release előtt szükséges. A részletes, commit-SHA-hoz kötött tesztbizonyíték és fennmaradó feladatlista a JARVIS_REMAINING_WORK_REPORT.md dokumentumban van.
