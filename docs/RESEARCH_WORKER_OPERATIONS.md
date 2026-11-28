# JARVIS – kutatási worker műveletek

**Állapot:** implementálva a PR #35 fejlesztői ágán; CI-ellenőrzés folyamatban.  
**Frissítés – 2026-11-28:** a dashboard RPC-számlálóit biztonságos, nemnegatív egész normalizálás védi; a committed költség nulla értéke külön kezelődik, nem esik vissza a reserved összegre. A hibás értékek és nulla committed összeg regressziós tesztet kaptak. A 8412057 commit CI-je egy f-string szintaktikai hibán bukott; a ca6ba391 javította, de a javító HEAD CI-je még nem igazolt. A migration továbbra is branch-only, production DB-n nem alkalmaztuk.


**Migráció:** `20261127220000_company_research_worker_ops.sql` – repository-only, production adatbázisra nem került fel.

## P2 – provideroldali Google Search költségkorlát (2026-11-28)

**Ellenőrzési eredmény: a jelenlegi Gemini Google Search grounding API-hívásban nincs dokumentált, kérésenkénti maximális keresési lekérdezésszám-paraméter.** A modell dönt arról, hogy indít-e keresést, és egyetlen promptból több keresési lekérdezést is generálhat. A válasz `grounding_metadata.web_search_queries` mezője utólag jelzi a tényleges lekérdezéseket; ez elszámolási/riasztási adat, nem előzetes korlátozó mechanizmus.

A jelenlegi adapter ezért:
- egy `generate_content` hívásban adja át a `google_search` eszközt;
- a válasz metadata alapján méri a keresési lekérdezések számát;
- a költségbecslésben szereplő `max_search_queries_per_attempt` értéket **foglalási feltételezésként**, nem provider hard limitként kezeli;
- hiányzó keresési metadata esetén, ha a grounding díjköteles, nem véglegesíti a tényleges költséget, hanem a foglalást tartja fenn.

**Következmény:** a napi budget és a foglalási becslés védi a queue további feladatait, de nem garantálja, hogy egyetlen Gemini kérés ne lépje túl a becsült keresési keretet. A metadata utólagos ellenőrzése sem tudja visszafordítani a már végrehajtott kereséseket.

**Biztonságos következő architektúra, külön jóváhagyás és költségmodell-ellenőrzés után:** a beépített Google Search grounding helyett explicit, alkalmazás által vezérelt keresőadapter, amely egyenként indítja a kereséseket, minden keresés előtt atomikusan ellenőrzi és lefoglalja a maradék napi query-budgetet, majd a limit elérésekor nem küld újabb provider keresést. Ez külön provider/API és grounding-minőség változás; jelenleg nem kapcsoltuk be és nem indítottunk külső keresést.

## Mit tud most?

**P2 scheduler kill switch – 2026-11-28:** a napi GitHub Actions job csak akkor futhat, ha a repository `JARVIS_COMPANY_RESEARCH_SCHEDULE_ENABLED` változója explicit `true`. Ugyanezt a belépési pont Python-oldalon is ellenőrzi még a konfiguráció, Supabase-kliens vagy Gemini-kliens betöltése előtt. A változó nincs bekapcsolva; az ütemezett futtatás jelenleg szándékosan tiltott.

- A meglévő napi `company-research-refresh.yml` workflow továbbra is időzítetten indítja a bounded kutatási ciklust.
- Az új vezérlőállapot egyetlen, adatbázisban tárolt pause/resume kapcsoló.
- Szüneteltetéskor a ciklus már a queue feltöltése előtt leáll; a claim RPC atomikusan is ellenőrzi a pause állapotot.
- A már futó, érvényes lease-szel rendelkező feladat befejeződhet. Új feladatot a worker nem vesz fel.
- A várakozó és retry feladatok a sorban maradnak; újraindítás után a következő ütemezett ciklus feldolgozhatja őket.
- A Kutatási műveletek oldal mutatja a queued/running/retry_wait/succeeded/dead_letter darabszámokat, a napi költségfoglalást és elszámolást, a legutóbbi feladatokat és a pause/resume eseményeket.

## Jogosultságok és audit

- Admin/operator: megtekintés, szüneteltetés és újraindítás.
- Reader: kizárólag olvasás.
- Anon és legacy shared-password munkamenet: nincs hozzáférés.
- A dashboard kizárólag az ellenőrzött Auth-felhasználó JWT-jével hívott RPC-ket használ; nem használ service-role adatbázis-klienst.
- A vezérlő táblák közvetlen olvasása/írása tiltott az API-szerepköröknek. A változtatások indoklással, append-only eseménynaplóba kerülnek.

## Mi nincs még meg?

- Külső riasztás (pl. Slack/push) dead-letter, költségplafon vagy tartós workflow-hiba esetén.
- Részletes idősoros provider-latencia, token- és költségtrend.
- Több régió/piac külön ütemezése és worker-pool kezelése.
- A stagingben végzett, több egymást követő napi ciklusos üzemi validáció.

## Biztonsági határok

- A pause/resume nem indít manuális futtatást és nem módosít napi hard budgetet.
- Nem küld e-mailt, nem válaszol ügyfélnek, és nem ad kapcsolatfelvételi engedélyt.
- A napi költségplafon és a korábbi domain/hour kvóták változatlanul érvényesek.
- A migrációt nem futtattuk production adatbázison; PR #35 továbbra is draft, merge nélkül.
