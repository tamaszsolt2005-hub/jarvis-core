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

- A GitHub Actions `JARVIS CI` futása a vizsgált commiton elindult: run `45872355721`.
- A legutóbbi lekérdezéskor a `test` és a `backup-restore-integration` job is `in_progress` állapotú volt; a böngészőtelepítés, illetve az izolált PostgreSQL/pgTAP lépések még futottak.
- A teljes teszt sikeressége ezért még nem igazolt. A futás lezárása után az aktuális head SHA-hoz tartozó eredményt kell újra lekérdezni.

## 3. Főrendszer-funkciók állapotképe

| Terület | Kód/dokumentáció alapján | A késznek minősítés feltétele |
|---|---|---|
| Magyar nyelvű chat | Implementált, Gemini-konfigurációt igényel | Helyi, valós konfigurációval végzett chat smoke; hiba- és timeout-kezelés |
| Leadkutatás és cégazonosítás | Forrásolt kutatás és közös deduplikációs út implementált a fejlesztési ágakban | Aktuális CI, izolált DB concurrency teszt, valós provider smoke külön tesztkörnyezetben |
| Lead scoring és workflow ajánlás | Implementált | Valós lead mintákon eredmény- és magyarázhatósági ellenőrzés |
| Task-kezelés | Jóváhagyásos create/update/close út és atomikus SQL szerződés implementált | Teljes chat → approval → DB → audit E2E; jogosultsági és visszajátszási teszt |
| Task center | Read-only dashboard oldal | Szűrés/rendezés/határidő és üres/hibaállapot kézi smoke |
| Kutatási dosszié és előzmény | Dosszié, snapshot store és read-only előzmény UI implementált | A store és worker közti tartós mentési adatút igazolása; UI jogosultság/hiba smoke |
| Kutatási job/worker | Job lifecycle, RPC repository, queue, worker, Gemini adapter és one-shot runtime kódban | Izolált PostgreSQL konkurenciateszt, end-to-end job → provider → snapshot, lease/retry/költség tesztek |
| Memória | Explicit mentési/listázási/inaktiválási funkció | Kategória-, jogosultság-, adatmegőrzési és valós DB smoke |
| Napi briefing és analitika | Implementált komponensek | Helyi, adatbázissal végzett smoke és helyességellenőrzés |
| Audit | Admin megjelenítés/export és SQL hash-chain alapok | Audit fail-closed E2E, jogosultság, láncintegritás és export smoke |
| Beállítások és konfiguráció | A teljes Settings oldal és operációs konfiguráció nem igazolt késznek | Funkcionális leltár; minden látható menüpont működjön vagy legyen eltávolítva/egyértelműen jelölve |
| E-mail | Outbound hard-disabled | Ez szándékos biztonsági korlát; küldés nem része a főrendszer készre jelentésének |

## 4. Mi hiányzik a főrendszer készre jelentéséhez?

### P0 – kötelező lezárás

1. **Aktuális CI zöldre futtatása.** A Python/unit/AppTest/browser tesztek, PostgreSQL 17 migration/pgTAP és concurrency tesztek, backup–restore, CodeQL és dependency audit eredményét az aktuális PR headhez kell kötni. Sikertelen jobokat javítani, majd teljes releváns futást ismételni.
2. **Teljes helyi smoke teszt.** Friss, dokumentált fejlesztői környezetben telepítés, konfigurációellenőrzés, Streamlit indulás, chat, leadkutatás, lead lista, task approval, task center, memória, briefing, analitika, audit és kutatási előzmény végigpróbálása.
3. **Végponttól végpontig tartó core workflow teszt.** Lead létrehozás/azonosítás → scoring → task javaslat → approval → atomikus DB művelet → audit → outcome feldolgozás. Ellenőrizni kell a duplikált kérés, timeout, visszajátszás, párhuzamos kérés és audit-hiba viselkedését.
4. **Dashboard teljességi leltár.** Minden látható navigációs elemnek legyen működő funkciója; a placeholder/dekoratív Settings vagy más menüpont ne tűnjön kész funkciónak.
5. **Konfigurációs és hibaállapotok.** Hiányzó/hibás Gemini vagy Supabase konfiguráció, hálózati hiba, rate limit, jogosultsághiány és üres adatbázis esetén érthető, biztonságos hibaüzenet kell; titok nem kerülhet logba vagy UI-ra.

### P1 – megbízható belső használat és későbbi release előfeltétele

6. **Izolált PostgreSQL worker tesztek.** A job create idempotencia, párhuzamos claim, concurrency plafon, lease expiry/reclaim, heartbeat, retry/dead-letter, atomikus budget/hourly/domain kvóta, actual-cost settlement és audit tranzakciók valós PG17 tesztjei. A fake repository teszt önmagában nem bizonyít SQL konkurenciát.
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

1. Fejezzük be és javítsuk zöldre a PR #28 aktuális CI-jét.
2. Készítsünk core E2E tesztet a lead → approval/task → audit folyamatra.
3. Zárjuk le a dashboard menüpont- és konfigurációs leltárt.
4. Zárjuk le a worker SQL konkurencia- és kutatási snapshot E2E tesztjeit.
5. Végezzen a fejlesztői környezetben egy dokumentált teljes manuális smoke tesztet.
6. Ezek után adjunk külön minősítést: „helyi főrendszer kész”, „belső használatra kész”, illetve „production release-re kész”.

**Jelenlegi minősítés:** a JARVIS főrendszerének több alapfunkciója implementált, de a teljes core E2E és aktuális CI bizonyíték hiányában még nem tekinthető késznek. A teljes autonóm SaaS-ügynök ettől függetlenül további, nagyobb fejlesztési fázisokat igényel.

## 7. Kapcsolódó dokumentumok

- [Központi dokumentáció](JARVIS_MASTER_DOCUMENTATION.md)
- [Aktuális állapot](CURRENT_STATE_AND_NEXT_STEPS.md)
- [Fejlesztési roadmap](JARVIS_DEVELOPMENT_ROADMAP.md)
- [Release gate-ek](REMAINING_WORK_AND_RELEASE_GATES.md)
- [Production állapot és migrációs terv](PRODUCTION_STATE_AND_MIGRATION_PLAN.md)