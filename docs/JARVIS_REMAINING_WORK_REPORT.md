# JARVIS – hátralévő feladatok és ellenőrzési jelentés

**Dátum:** 2026-11-26  
**Fejlesztési ág:** `feature/company-research-dashboard-readonly`  
**PR:** [#28](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/28) – nyitott, nem merge-ölt  
**Cél:** helyi fejlesztői JARVIS lezárása; hosting és production bevezetés későbbi, külön döntés.

## 1. Vezetői összefoglaló

A JARVIS fő workflow-jának alapjai megvannak: chat, leadkutatás/scoring, jóváhagyott taskműveletek, audit, analitika, memória és dashboard. A dashboard navigációs audit, a read-only Beállítások oldal, az üres tasklista melletti utánkövetési sor javítása, valamint a központi runtime hibakategorizálás is bekerült a PR #28 ágba.

**A JARVIS még nem jelenthető késznek.** A legfontosabb hiányok: az új hibakezelési módosítások célzott tesztbizonyítéka, a cégkutatási worker és snapshot mentés teljes E2E útja, a worker SQL konkurenciájának izolált PostgreSQL ellenőrzése, a valós Auth/RLS jogosultsági tesztek és a dokumentált helyi manuális smoke.

A PR #28 nyitva marad. Merge, production deploy, production migration és production konfigurációmódosítás nem történt.

## 2. Mi készült el

- A dashboard Chat, Feladatok, Analitika, Cégkutatás, Audit napló és Beállítások útvonalainak áttekintése.
- A Beállítások dedikált, kattintható, read-only oldal; titokértékek nem jelennek meg.
- Kézi, költségre figyelmeztető diagnosztika; Auth módban jogosultságkorlátozással.
- Üres tasklista esetén is megjelenik a jogosultsági feltételeknek megfelelő utánkövetési sor.
- Egységes hibakategóriák: hiányzó/hibás konfiguráció, permission, authentication, rate limit/kvóta, hálózat, timeout, szolgáltatáskiesés, hibás kérés és ismeretlen hiba.
- Kötelező secret whitespace-validációja és Supabase HTTP(S) URL ellenőrzése.
- A Gemini korlátozott retryt használ átmeneti hibákra; tartalék modell csak rate limit/túlterhelés esetén. Hitelesítési és jogosultsági hibára nincs retry vagy jogosultságváltás.
- A chat és diagnosztika biztonságos, magyar hibaútmutatót mutat, nyers provider kivétel és titok nélkül.
- A korábbi CI-ben jelzett két Settings AppTest hibás elvárása javítva.
- Dokumentáció frissítve a működési korlátokról és a szelektív tesztelési elvről.

## 3. Tesztbizonyíték – mi van már ellenőrizve?

### Korábban igazolt eredmények

| Ellenőrzés | Bizonyíték | Állapot / korlát |
|---|---|---|
| Core lead → scoring → task approval → PostgreSQL → audit workflow | `36d615f6770ce097ba7a69954a7748ad237b8fd0`, CI run `45873698960` és `45873705730` | Sikeres ezen a korábbi commiton; az újabb dashboard és hibakezelési kódot nem igazolja |
| PostgreSQL backup–restore CI job | CI run `45875325010` | Sikeres; nem kell újrafuttatni, amíg a backup/restore útvonal nem változik |
| Unit/AppTest/browser tesztcsomag a korábbi dashboard HEAD-en | CI run `45875325010` | 1104 passed, 3 skipped, 2 failed; coverage 90,24%. A két hiba Settings AppTest assertion volt |
| Compile/egyéb előkészítő CI lépések | CI run `45875325010` | A naplóban sikeresek |
| Worker SQL konkurencia és költségkvóták | Új pgTAP lifecycle/kvóta teszt + külön, két `dblink` sessiont használó párhuzamos claim/budget teszt a PR #28 ágon | A tesztek megíródtak, de még nem futottak le izolált PostgreSQL-en; eredmény nem igazolt |
| Valós Gemini provider smoke | Nincs | Nem futott productionben; izolált tesztkörnyezetben még szükséges |

A két korábbi Settings AppTest hibát javítottuk, de a javítás utáni aktuális kódon ezek célzott újrafuttatása még nem igazolt. Nem állítjuk, hogy a legfrissebb ág CI-je zöld.

## 4. Következő feladatok – prioritási sorrendben

### P0 – a mostani fejlesztési egység lezárása

1. **Csak az érintett hibakezelési tesztek futtatása**
   - `tests/test_jarvis_errors.py`
   - `tests/test_jarvis_common.py`
   - A hibajelzést módosító dashboard ág célzott AppTestjei, különösen a korábban elbukott két Settings teszt.
   - Esetleges hiba esetén csak az érintett tesztet/kódot javítsuk.
   - A változatlan backup–restore és teljes, korábban lefedett tesztkör ismétlése nem szükséges most.

2. **Hibakategorizálás valós provider kivételalakokkal**
   - Google GenAI SDK tényleges 429/RESOURCE_EXHAUSTED, 503/UNAVAILABLE, timeout és auth kivételtípusainak izolált tesztelése.
   - Ellenőrizni, hogy a hálózati kivétel besorolása nem túl tág, és a retry kizárólag idempotens generálási kérésre vonatkozik.
   - Bizonyítani, hogy a titokmentesítés nem fed fel API-kulcsot, Bearer tokent vagy credentialt.

### P1 – belső főrendszer megbízhatósága

3. **Cégkutatási adatút E2E lezárása**
   - Queue → claim → grounded Gemini provider → dossier validáció → snapshot mentés → lead-kapcsolat → audit.
   - Hiba, retry, lease-vesztés és duplikált operation ID esetén konzisztens állapot.
   - Most még a provider/runtime alap és a snapshot store külön-külön létezik; a teljes bekötött adatút nincs igazolva.

4. **Worker SQL izolált PostgreSQL teszt – tesztek előkészítve, futtatás hátra van**
   - `supabase/tests/company_research_jobs.test.sql`: idempotencia, napi/óránkénti/domain kvóta, concurrency plafon, heartbeat, actual-cost settlement és audit.
   - `supabase/tests/company_research_jobs_concurrency.test.sql`: két független PostgreSQL `dblink` sessionnel valódi párhuzamos budget reservation és worker claim verseny.
   - A futtatás helyi, izolált Supabase/PostgreSQL környezetben: `supabase test db` (a lokális DB elindítása után; `dblink` extension szükséges).
   - A SQL tesztek jelenleg nincsenek lefuttatva, ezért sem a race, sem a kvóták működését nem jelöljük igazoltnak.
   - A fake repository teszt nem helyettesíti a valódi PostgreSQL konkurenciatesztet.

5. **Auth/RLS jogosultsági teszt**
   - Olvasó és admin szerepkör külön.
   - Dashboard táblák és RPC-k valós user JWT-vel.
   - Service-role kizárólag szerveroldali, megbízható kódban.
   - Cégkutatási snapshot read út engedélyezése csak explicit RLS és jogosultság után.
   - Jogosultsághiány esetén fail-closed; nincs legacy/service-role fallback.

6. **Teljes helyi manuális smoke**
   - Chat, feladatok, analitika, cégkutatás, audit, beállítások.
   - Üres adatok, hiányzó konfiguráció, hibás kulcs, hálózati hiba, kvóta, permission denied.
   - Eredmény, környezet és commit SHA rögzítése.

7. **Fennmaradó dashboard UX**
   - A Chat kezdőoldali „Ötletek”, „Elemzés”, „Feladatok”, „Üzleti összefoglaló” elemek jelenleg statikus vizuális javaslatok; valódi gyorsműveletté kell alakítani.
   - Beállítások felhasználói preferenciáinak mentése csak létező, megfelelő adattárolási modell kiválasztása után; titkok és biztonsági zárak továbbra sem szerkeszthetők dashboardból.
   - Cégkutatás Auth/RLS read path lezárása.

### P2 – későbbi termékfázis, nem blokkolja a belső asszisztenst

- Scheduler és automatikus háttérkutatás.
- SaaS ötletmotor, piaci alternatívaelemzés és tiltó/ütközésnapló.
- Outreach automatizálás.
- Outbound e-mail; továbbra is hard-disabled, amíg külön jogi, biztonsági és termékjóváhagyás nincs.
- AI-assisted termékfejlesztési pipeline.

## 5. Tesztelési szabály a további munkához

Nem futtatjuk újra ugyanazokat a teszteket minden commit után.

- Python változás: csak az érintett modul tesztjei és közvetlen regressziók.
- Dashboard változás: csak az érintett AppTest/browser teszt.
- SQL/migration változás: izolált PostgreSQL/pgTAP és konkurencia tesztek.
- Auth/RLS vagy provider változás: célzott izolált integrációs/smoke teszt.
- Backup–restore: csak akkor ismétlendő, ha a backup/restore kód vagy konfiguráció változik.
- Teljes CI: nagyobb integrációs mérföldkő végén, illetve PR merge/release előtt.

Minden eredményt commit SHA-hoz kötve kell dokumentálni. Egy korábbi commit zöld CI-je nem bizonyítja az azóta módosított kód helyességét.

## 6. Production és biztonsági korlátok

A következő fejlesztési feladatok kizárólag a PR branch-en és izolált tesztkörnyezetben végezhetők. Production Supabase DB-n migration, DDL/DML, GRANT/REVOKE, Auth/RBAC módosítás, secretcsere, deploy vagy e-mailküldés nem történhet külön, konkrét jóváhagyás nélkül. Hosting beállítása nem része a mostani helyi fejlesztési szakasznak.

## 7. Rövid döntési javaslat

A következő lépés a két új SQL tesztcsomag futtatása kizárólag helyi/izolált PostgreSQL-en, a hibaeredmények javítása, majd a futás commit SHA-hoz kötött dokumentálása. Ezután következhet a worker → snapshot E2E. A teljes CI-t csak e nagyobb integrációs csomag lezárása után futtassuk, a korábban már sikeresen ellenőrzött backup–restore lépést pedig ne ismételjük meg változatlan kód mellett.


## 8. Új worker SQL tesztcsomag – 2026-11-26

A PR #28 ágon két új adatbázis-teszt készült:

- `supabase/tests/company_research_jobs.test.sql`: 15 pgTAP ellenőrzés az idempotens job-létrehozásról, napi költségkeretről, óránkénti és domainenkénti kvótáról, aktív lease plafonról, heartbeat jogosultságról, actual-cost settlementről és audit eseményekről.
- `supabase/tests/company_research_jobs_concurrency.test.sql`: 10 pgTAP ellenőrzés két független PostgreSQL `dblink` sessionnel. Két egyidejű, 700/1000 mikro-USD foglalásból pontosan egynek szabad sikerülnie; két párhuzamos worker claim esetén az aktív lease-ek száma nem lépheti túl az 1-et.

**Ellenőrzési státusz: NEM FUTOTT.** A tesztek forrása elkészült, de lokális/izolált PostgreSQL futtatás és eredmény még nincs. Futtatási parancs a helyi Supabase DB elindítása után: `supabase test db`. A concurrency teszthez a `dblink` extension elérhetősége szükséges. Production adatbázison nem szabad futtatni. A következő jelentésben a futás pontos commit SHA-ját, pgTAP eredményét és az esetleges hibákat kell rögzíteni.
