# JARVIS – főrendszer-készültségi felmérés

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
| Kutatási dosszié és előzmény | Dosszié, snapshot store és read-only előzmény UI implementált; a one-shot runtime a worker sikeres lezárása előtt elmenti a snapshotot, operation ID-alapú idempotenciával és lead FK-kapcsolattal | Az új izolált PostgreSQL CI futás eredménye, Auth/RLS olvasási jogosultság és UI smoke még igazolandó |
| Kutatási job/worker | Queue → claim → grounded Gemini adapter → dossier validáció → snapshot persistence → lead link → complete bekötve; retry/lease-loss útvonal meglévő | Új pgTAP/dblink CI job eredménye, lease expiry/reclaim és retry/dead-letter SQL-életciklus mélyebb lefedése, valós provider smoke szükséges |
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

6. **[KÉSZ – CI #3136] Izolált PostgreSQL worker tesztek.** Snapshot SQL teszt sikeres; `company_research_jobs.test.sql` 15/15 lifecycle/kvóta assertion; `company_research_jobs_concurrency.test.sql` 14/14 két-session `dblink` konkurencia assertion. Elkülönített PostgreSQL 17 CI adatbázisban futott.
7. **[KÉSZ – CI #3136] Kutatási adatút runtime-integráció.** A runtime kötelező snapshot DB injekcióval épül fel; a worker a job complete előtt menti a validált dossziét. Az operation ID-ból determinisztikus snapshot UUID képződik, így az azonos tartalmú mentés utáni retry idempotens. A snapshot a lead_id FK-val kapcsolódik a leadhez. Persist-hiba esetén a worker nem complete-el, hanem retry/dead-letter utat használ. Élő Gemini API-próba és teljes Auth/RLS jogosultsági teszt külön hátravan.
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


## Frissített készültségi állapot – 2026-11-26

**Aktuális PR #28 HEAD:** `4e5bed363285553525aae89ff4aae78b5e79de2b`. **CI:** [Run #3136](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45883574515) – mindhárom job sikeres: Python/AppTest/browser tesztek (`140128615157`), izolált PostgreSQL worker-integráció (`140128614819`), backup–restore (`140128615278`). Eredmény: **1144 passed, 3 skipped, 0 failed**, coverage **90,17%**; `python -m compileall -q .` sikeres. A PostgreSQL job sikeresen lefuttatta a snapshot-tároló tesztet, a **15/15 lifecycle/kvóta** és a **14/14 két-session dblink konkurencia** assertiont.

### P0 – fejlesztési csomag állapota

A Gemini és külső szolgáltatások hibakezelési P0 kódcsomag **elkészült és a fenti teljes CI zölden ellenőrizte**. Ide tartozik a Google GenAI státuszkódok normalizálása, központi retry-besorolás, korlátozott exponenciális retry, 429/503 fallback, auth/config/invalid-request no-retry, biztonságos provider-kód allowlist, titokmentesített hibajelzés és az SMTP duplikált újraküldésének kizárása. A Settings AppTest korábbi hibája is javítva van.

**Korlát:** valódi Google Gemini API-val végzett élő/staging smoke nem történt. A CI a mockolt/tesztelt viselkedést igazolja, nem a szolgáltató élő válaszát. Ez a külső integrációs ellenőrzés továbbra is hátralévő feladat.

### Jelenlegi termékképességek – mi van ma a JARVIS-ban?

- Magyar nyelvű, Gemini-alapú üzleti chat (működéséhez helyi API-konfiguráció szükséges).
- Kifejezett felhasználói kérésre indított, Google Search groundingre épülő lead/cégkutatás; dokumentált korlátja legfeljebb 15 új cég egy futásban.
- Cégazonosítás és duplikációszűrés; lead scoring, kutatási bizonyosság és belső workflow-ajánlások.
- Jóváhagyáshoz kötött task létrehozás/módosítás/lezárás; read-only Feladatok központ és utánkövetési sor.
- Üzleti memória, napi briefing, analitika és audit funkciók.
- Cégdosszié/snapshot és read-only kutatási előzmény UI kódban; a worker runtime→provider→snapshot→lead FK→complete/audit út CI-vel igazolt. Auth módban a snapshot oldal továbbra is fail-closed, amíg az RLS olvasási jogosultság nincs megfelelően kiépítve.
- Read-only Beállítások oldal, konfigurációs státuszok és kézi diagnosztika; titokértékek nem jelennek meg és nem szerkeszthetők.
- Bejövő inbox/e-mail komponensek konfigurációtól függően rendelkezésre állhatnak; **kimenő e-mail küldés hard-disabled**.

### Ami még NINCS kész – a SaaS-vízió és a tényleges termék közötti különbség

A JARVIS jelenleg nem autonóm SaaS-értékesítő vagy önálló SaaS-gyár. Nincs kész automatikus piacfigyelő/cégfelderítő scheduler, folyamatos háttérkutatás, teljesen bekötött és bizonyított worker adatút, automatikus SaaS-termékötlet- és versenytárselemző motor, globális/cégenkénti termék-tiltó és ütközésnapló, automatikus személyre szabott outreach, outbound e-mail, illetve AI-alapú teljes termékfejlesztési/build/release pipeline. Ezek célfunkciók, nem jelenlegi kész képességek.

### Következő javítások és lezárási sorrend

**P1 – következő fő fejlesztési szakasz:**
1. A cégkutatási adatút E2E bekötése és igazolása: queue → claim → grounded Gemini provider → dossier validáció → snapshot mentés → lead-kapcsolat → audit; hiba/retry, lease-loss, duplicate operation ID és rollback viselkedéssel.
2. **[KÉSZ – CI #3136, izolált PostgreSQL 17]** `company_research_jobs.test.sql`: 15/15 lifecycle/kvóta assertion; `company_research_jobs_concurrency.test.sql`: 14/14 valódi, két `dblink` sessionnel futó konkurencia assertion; a snapshot-tároló SQL teszt is sikeres. A futtatás kizárólag eldobható CI-adatbázisban történt.
3. Worker lifecycle teljesítése/tesztelése: lease expiry és reclaim, heartbeat, párhuzamos claim és concurrency plafon, retry/dead-letter, idempotencia, óránkénti/napi/domain kvóták, actual-cost settlement és audit tranzakció.
4. Auth/RLS izolált szerepkörtesztek: reader/admin, valós JWT, RPC, service-role kizárólag trusted server oldalon; fail-closed és nincs jogosultsági fallback.
5. Valódi Google GenAI SDK/izolált staging integrációs próba: 429, 503, timeout, auth, grounding metadata, usage/cost és retry/heartbeat; production kulcs és production DB nélkül.
6. Teljes helyi manuális dashboard smoke: Chat, Feladatok, Analitika, Cégkutatás, Audit, Beállítások; üres adat, hiányzó/hibás konfiguráció, hálózat, kvóta és permission állapotok.
7. Chat gyorsműveletek valódi kattintható műveletté alakítása; user preference mentés csak jóváhagyott adattárolási modell alapján, a titkok és biztonsági zárak változtathatatlanul hagyásával.

**P2 – későbbi terméképítési szakasz:** scheduler/automatikus háttérkutatás; SaaS-ötletmotor és piaci alternatívaelemzés; globális és cégenkénti tiltó/ütközésnapló; ajánlatgenerálás és outreach workflow; jogszerű marketing-hozzájárulás/suppression modell; outbound e-mail külön engedélyezés után; AI-assisted termékfejlesztés és build/test/release pipeline.

### PR és környezeti állapot

PR #28 nyitott, nem merge-ölt, a base a `feature/company-research-phase-1` (stacked PR-lánc: #26 → #27 → #28; a merge sorrend kötelező). A JARVIS app helyi fejlesztés alatt van, nincs production app-host/deploy. A production DB-n nem történt módosítás; nincs production migration, deploy, secret-változtatás vagy e-mailküldés. A dokumentált CI nem jelent production readiness-t.
