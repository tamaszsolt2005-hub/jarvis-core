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
- `supabase/tests/company_research_jobs_concurrency.test.sql`: 14 pgTAP ellenőrzés két független PostgreSQL `dblink` sessionnel. Két egyidejű, 700/1000 mikro-USD foglalásból pontosan egynek szabad sikerülnie; két párhuzamos worker claim esetén az aktív lease-ek száma nem lépheti túl az 1-et.

**Költségkeret-korlát:** a jelenlegi SQL szerződés a becsült költséget foglalja le, majd a tényleges költséget elszámolja. A szolgáltatói tényleges költség az alulbecslés miatt meghaladhatja a becsült foglalást; a mostani RPC nem érvényesít utólagos, visszamenőleges hard capet. Ezt a teszt és a későbbi költségpolitika külön kockázatként kezeli.

**Ellenőrzési státusz: NEM FUTOTT.** A tesztek forrása elkészült, de lokális/izolált PostgreSQL futtatás és eredmény még nincs. A futtatás tervezett parancsa a helyi Supabase DB elindítása után: `supabase test db`. A vizsgált branch-en nem találtam verziózott `supabase/config.toml` fájlt, ezért a CLI-futtatás előtt a helyi Supabase projektkonfiguráció meglétét is ellenőrizni/pótolni kell. A concurrency teszthez a `dblink` extension elérhetősége szükséges. Production adatbázison nem szabad futtatni. A következő jelentésben a futás pontos commit SHA-ját, pgTAP eredményét és az esetleges hibákat kell rögzíteni.

## 9. P0 – Gemini és külső szolgáltatások hibakezelési keményítése (2026-11-26)

A PR #28 fejlesztési ágán az alábbi kód- és tesztmódosítások készültek:

- A központi classify_error() kezeli a Google GenAI SDK által használt numerikus HTTP-kódokat és szimbolikus státuszokat is: RESOURCE_EXHAUSTED/429, UNAVAILABLE/503, DEADLINE_EXCEEDED/504, INTERNAL/500, PERMISSION_DENIED/403, valamint az API_KEY_INVALID/INVALID_ARGUMENT kombinációt. A hibás API-kulcs hitelesítési hiba, nem újrapróbálható általános kérés.
- A Gemini generálási retry kizárólag a központi osztályozó által átmenetinek jelölt hibákra indul. A próbálkozások száma konfigurálható, 1–5 közé korlátozott; a várakozás exponenciális és legfeljebb 8 másodperc. A 429/503 túlterhelésnél tartalék modell is próbálható; auth-, konfigurációs és érvénytelen kérés hibánál nincs retry vagy fallback.
- A generate_text() kizárólag modell-inferenciát végez. E-mail-küldés, adatbázis-módosítás és más üzleti mellékhatás nem kerülhet a generálási retry útvonalba. Az SMTP bizonytalan kimenetelét a chat jóváhagyási folyamat unknown auditállapottal kezeli, automatikus újraküldés nélkül; ezt AppTest is ellenőrzi.
- A provider státuszkód csak korlátozott, biztonságos formátumban jelenhet meg; tetszőleges SDK mező nem kerül vissza a felhasználói hibaüzenetbe. A központi naplózás továbbra is redaktálja az API-kulcsokat, Bearer tokeneket és credential mezőket.
- A hiányzó/hibás konfiguráció a required_secret() és required_http_url() útvonalon még külső művelet előtt kivételt vált ki; a Gemini-kulcs hiánya nem indít klienskérést. A külső hálózati és timeout hibák elkülönített, felhasználó számára érthető kategóriát kapnak.

**Célzott regressziós lefedés hozzáadva:** tests/test_jarvis_errors.py, tests/test_jarvis_common.py, valamint a chat e-mail AppTest. A Settings AppTest hibás len(Button) lekérdezését kulcsalapú gombellenőrzésre cseréltük.

**CI-státusz:** a legutóbbi teljes futás (#3102, commit 570349c1556995db1ca664f503f8ebbaa8b465f5) 1126 sikeres, 3 kihagyott és 1 sikertelen tesztet jelzett; a fennmaradó bukás a Settings AppTest gombobjektumának hibás len() használata volt. Ezt a tesztet javítottuk, és azóta Gemini hibakategorizálási, retry, titokmentesítési és SMTP-duplikációs tesztek is kerültek a branch-re. **A jelenlegi branch HEAD-re még nincs igazolt CI-eredmény**, ezért a teljes P0 csomag csak az új commiton futó tesztek sikeres lezárása után tekinthető késznek.

Production adatbázis, secret, SMTP-konfiguráció és deploy nem módosult; valódi külső Gemini API-kérés nem futott.


## Aktuális státuszfelülírás – 2026-11-26 (PR #28 HEAD)

**Aktuális PR #28 HEAD:** `39fa60c1b448036665a475106dc97bbdd95e7150`. **CI:** [Run #3121](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45880962637) – mindkét job sikeres (test: `140120013677`, backup/restore integration: `140120014052`). A tesztösszesítő: **1140 passed, 3 skipped, 0 failed**, teljes coverage **90,29%** (80% minimum); `python -m compileall -q .` sikeres. Ez az eredmény az itt megadott HEAD-hez kötött, a korábbi dokumentumban szereplő 1126/1 failed és korábbi CI-megjegyzések elavultak.

### P0 – fejlesztési csomag állapota

A Gemini és külső szolgáltatások hibakezelési P0 kódcsomag **elkészült és a fenti teljes CI zölden ellenőrizte**. Ide tartozik a Google GenAI státuszkódok normalizálása, központi retry-besorolás, korlátozott exponenciális retry, 429/503 fallback, auth/config/invalid-request no-retry, biztonságos provider-kód allowlist, titokmentesített hibajelzés és az SMTP duplikált újraküldésének kizárása. A Settings AppTest korábbi hibája is javítva van.

**Korlát:** valódi Google Gemini API-val végzett élő/staging smoke nem történt. A CI a mockolt/tesztelt viselkedést igazolja, nem a szolgáltató élő válaszát. Ez a külső integrációs ellenőrzés továbbra is hátralévő feladat.

### Jelenlegi termékképességek – mi van ma a JARVIS-ban?

- Magyar nyelvű, Gemini-alapú üzleti chat (működéséhez helyi API-konfiguráció szükséges).
- Kifejezett felhasználói kérésre indított, Google Search groundingre épülő lead/cégkutatás; dokumentált korlátja legfeljebb 15 új cég egy futásban.
- Cégazonosítás és duplikációszűrés; lead scoring, kutatási bizonyosság és belső workflow-ajánlások.
- Jóváhagyáshoz kötött task létrehozás/módosítás/lezárás; read-only Feladatok központ és utánkövetési sor.
- Üzleti memória, napi briefing, analitika és audit funkciók.
- Cégdosszié/snapshot és read-only kutatási előzmény UI kódban; a teljes worker→provider→snapshot→lead→audit tartós E2E út még nincs igazolva. Auth módban a snapshot oldal fail-closed, amíg az RLS olvasási jogosultság nincs megfelelően kiépítve.
- Read-only Beállítások oldal, konfigurációs státuszok és kézi diagnosztika; titokértékek nem jelennek meg és nem szerkeszthetők.
- Bejövő inbox/e-mail komponensek konfigurációtól függően rendelkezésre állhatnak; **kimenő e-mail küldés hard-disabled**.

### Ami még NINCS kész – a SaaS-vízió és a tényleges termék közötti különbség

A JARVIS jelenleg nem autonóm SaaS-értékesítő vagy önálló SaaS-gyár. Nincs kész automatikus piacfigyelő/cégfelderítő scheduler, folyamatos háttérkutatás, teljesen bekötött és bizonyított worker adatút, automatikus SaaS-termékötlet- és versenytárselemző motor, globális/cégenkénti termék-tiltó és ütközésnapló, automatikus személyre szabott outreach, outbound e-mail, illetve AI-alapú teljes termékfejlesztési/build/release pipeline. Ezek célfunkciók, nem jelenlegi kész képességek.

### Következő javítások és lezárási sorrend

**P1 – következő fő fejlesztési szakasz:**
1. A cégkutatási adatút E2E bekötése és igazolása: queue → claim → grounded Gemini provider → dossier validáció → snapshot mentés → lead-kapcsolat → audit; hiba/retry, lease-loss, duplicate operation ID és rollback viselkedéssel.
2. A két előkészített SQL tesztcsomag futtatása izolált PostgreSQL/Supabase környezetben: `company_research_jobs.test.sql` (15 pgTAP assertion) és `company_research_jobs_concurrency.test.sql` (14 pgTAP assertion, `dblink`). A futtatás jelenleg NEM igazolt; lokális Supabase konfiguráció és `dblink` elérhetőség szükséges.
3. Worker lifecycle teljesítése/tesztelése: lease expiry és reclaim, heartbeat, párhuzamos claim és concurrency plafon, retry/dead-letter, idempotencia, óránkénti/napi/domain kvóták, actual-cost settlement és audit tranzakció.
4. Auth/RLS izolált szerepkörtesztek: reader/admin, valós JWT, RPC, service-role kizárólag trusted server oldalon; fail-closed és nincs jogosultsági fallback.
5. Valódi Google GenAI SDK/izolált staging integrációs próba: 429, 503, timeout, auth, grounding metadata, usage/cost és retry/heartbeat; production kulcs és production DB nélkül.
6. Teljes helyi manuális dashboard smoke: Chat, Feladatok, Analitika, Cégkutatás, Audit, Beállítások; üres adat, hiányzó/hibás konfiguráció, hálózat, kvóta és permission állapotok.
7. Chat gyorsműveletek valódi kattintható műveletté alakítása; user preference mentés csak jóváhagyott adattárolási modell alapján, a titkok és biztonsági zárak változtathatatlanul hagyásával.

**P2 – későbbi terméképítési szakasz:** scheduler/automatikus háttérkutatás; SaaS-ötletmotor és piaci alternatívaelemzés; globális és cégenkénti tiltó/ütközésnapló; ajánlatgenerálás és outreach workflow; jogszerű marketing-hozzájárulás/suppression modell; outbound e-mail külön engedélyezés után; AI-assisted termékfejlesztés és build/test/release pipeline.

### PR és környezeti állapot

PR #28 nyitott, nem merge-ölt, a base a `feature/company-research-phase-1` (stacked PR-lánc: #26 → #27 → #28; a merge sorrend kötelező). A JARVIS app helyi fejlesztés alatt van, nincs production app-host/deploy. A production DB-n nem történt módosítás; nincs production migration, deploy, secret-változtatás vagy e-mailküldés. A dokumentált CI nem jelent production readiness-t.
