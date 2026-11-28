# JARVIS – kutatási worker műveletek

**Állapot:** implementálva a PR #35 fejlesztői ágán; CI-ellenőrzés folyamatban.  
**Frissítés – 2026-11-28:** a dashboard RPC-számlálóit biztonságos, nemnegatív egész normalizálás védi; a committed költség nulla értéke külön kezelődik, nem esik vissza a reserved összegre. A hibás értékek és nulla committed összeg regressziós tesztet kaptak. A 8412057 commit CI-je egy f-string szintaktikai hibán bukott; a ca6ba391 javította, de a javító HEAD CI-je még nem igazolt. A migration továbbra is branch-only, production DB-n nem alkalmaztuk.


**Migráció:** `20261127220000_company_research_worker_ops.sql` – repository-only, production adatbázisra nem került fel.

## Mit tud most?

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
