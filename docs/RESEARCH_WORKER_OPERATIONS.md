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
- A nem production tesztfuttatásban végzett, több egymást követő ciklusos validáció; külön staging DB nem készül.

## Biztonsági határok

- A pause/resume nem indít manuális futtatást és nem módosít napi hard budgetet.
- Nem küld e-mailt, nem válaszol ügyfélnek, és nem ad kapcsolatfelvételi engedélyt.
- A napi költségplafon és a korábbi domain/hour kvóták változatlanul érvényesek.
- A migrációt nem futtattuk production adatbázison; PR #35 továbbra is draft, merge nélkül.


## Irányadó állapotfrissítés – 2026-11-28 16:32 CET

Ez a blokk felülírja a dokumentum korábbi, más HEAD-re, CI-futásra vagy release-állapotra vonatkozó „aktuális” pillanatképeit. A korábbi dátumozott részek történeti naplóként maradnak meg.

- **Vizsgált ág:** `feature/opportunity-center-readonly`; **PR:** [#35](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/35), nyitott, draft, nem merge-ölt; **vizsgált HEAD:** `cb17d197b17325e86b78b9565f8ba95528f66e02`.
- A PR API szerint a mergeability jelenleg `false`. A HEAD-hez a lekérdezéskor nem volt visszaadott PR workflow-run; ezért erre a commitra friss zöld CI, coverage, CodeQL vagy dependency-audit eredmény nem állítható.
- A korábban mért 83,3%-os coverage és korábbi sikeres integrációs/security jobok **nem** bizonyítják a jelenlegi HEAD állapotát. A legutóbbi ismert mobil böngészőteszt-hiba javításának eredményét új, a jelenlegi HEAD-hez kötött futásból kell igazolni.
- P1/P2 funkciók a feature branchben implementációs állapotúak; ez nem jelent production aktiválást. A PR migrációi nincsenek production adatbázison alkalmazva, a branch UI nincs production deployolva.
- A P2 Research Ops dashboard helyi riasztásai: dead-letter, budget-kihasználtság/túllépés és lejárt/hiányzó lease. Külső értesítés nincs bekötve.
- A scheduler kill switch kódban és workflow-ban fail-closed; a `JARVIS_COMPANY_RESEARCH_SCHEDULE_ENABLED` nincs engedélyezve. A workert és schedulert nem indítottuk el.
- A Gemini beépített Google Search grounding egyetlen kérésére nincs igazolt, konfigurálható query-count hard limit. A metadata utólagos elszámolásra használható, nem előzetes korlátozásra. A napi budget jelenlegi foglalása ezért nem garantálja az egyetlen hívás költségének plafonját.
- A production Auth könyvtár korábban ellenőrzött állapotában 0 felhasználó volt; CRM owner assignmenthez nincs aktív assignable Auth user. Ezt nem szabad automatikus user-létrehozással vagy meghívóval megkerülni.

### Környezeti döntés – nincs fizetős staging adatbázis

A projektben **nem hozunk létre külön Supabase development/staging ágat vagy fizetős staging projektet**. A CI migrációs és SQL-tesztjeihez kizárólag a workflow által felállított ideiglenes, izolált PostgreSQL használható. Ez nem staging és nem production. A production Supabase projekt marad az egyetlen tartós adatbázis; azon nincs próbamigráció és nincs tesztadat-módosítás. Éles migráció csak a release gate-ek lezárása után, ellenőrzött sorrendben és backup/rollback tervvel történhet. Az alkalmazás böngészős smoke-ja jelenleg a CI-ben elérhető tesztkörnyezetre korlátozódik; nem állítunk be külön fizetős staging infrastruktúrát.

### Következő kötelező munkák

1. A jelenlegi HEAD-re automatikus JARVIS CI indítása/megérkezése és teljes sikerének ellenőrzése; coverage legalább 82%.
2. A mobil login/chat és dashboard screenshotok friss artifactjainak ellenőrzése; a böngészőtesztek zöld eredménye önmagában nem helyettesíti a screenshot review-t.
3. CodeQL és dependency audit futtatása és zöld eredményének igazolása ugyanezen a HEAD-en.
4. Migrációs, RLS, GRANT, SECURITY DEFINER, search_path és Auth/JWT jogosultsági review.
5. P2: provideroldali query-korlát helyett egyenként vezérelt keresőadapter vagy más, bizonyítható alkalmazásszintű query-budget; alert history; költség/latency/usage idősoros megfigyelés.
6. P1 üzleti validáció: Opportunity Discovery végponttól végpontig, CRM owner/follow-up, ajánlat/pilot/outcome és valós ügyfélinterjúk. A technikai pontszám nem bizonyít fizetési hajlandóságot.
7. Release után: production migráció és deploy csak külön ellenőrzött lépésben; scheduler és outbound e-mail továbbra is kikapcsolva marad, amíg külön jóváhagyás nincs.

### Prioritási sorrend

- **P0 – release gate:** friss teljes CI, coverage ≥82%, CodeQL, dependency audit, migráció/security review, UI smoke és rollback/backup runbook.
- **P1 – üzleti folyamat:** Opportunity pain→pattern→SaaS candidate→review→assessment E2E; CRM owner és follow-up; inbound reply audit/CRM; ajánlat/pilot és valós WTP-validáció.
- **P2 – üzemi megbízhatóság:** valódi query/cost limit, alert history/notification (külön döntés után), provider latency/usage monitoring, scheduler többciklusos ellenőrzése az aktiválás előtt. A scheduler marad opt-in.
- **P3 – termékesítés:** PRD→backlog→prototípus→build/test/release, multi-tenant és billing csak akkor, ha külső SaaS értékesítési cél lesz.
