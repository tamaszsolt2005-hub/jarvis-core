# JARVIS – fejlesztési áttekintés, ellenőrzött állapot és javaslatok

**Felülvizsgálat:** 2026-11-25  
**Tartós fejlesztési ág:** `main`  
**Repository:** https://github.com/tamaszsolt2005-hub/jarvis-core

> **Dokumentumhasználat:** ez az egyetlen dokumentum, amely a fejlesztési javaslatok teljes listáját és azok ellenőrzött státuszát tartalmazza. A [Hátralévő feladatok és release gate-ek](REMAINING_WORK_AND_RELEASE_GATES.md) kizárólag a merge és production kiadás kapuit tartalmazza; nem ismétli meg a fejlesztési javaslatokat.

## 1. Aktuális repository-állapot

| Elem | Ellenőrzött érték |
|---|---|
| `main` HEAD | `f49eda731dbfc5792744d128ce2ee6f34fc55465` |
| PR #13 HEAD | `32aef539c0128c1fedaa9e03768477433e93abe1` |
| PR #13 | draft, open, nincs merge-elve |
| PR és main viszonya | 282 commit ahead, 6 commit behind |
| PR CI | [#45620672894](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45620672894) – sikeres |
| PR push CI | [#45620664359](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45620664359) – sikeres |
| Main dokumentációs CI | [#45621572548](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45621572548) – sikeres |

A PR CI a PR saját headjén zöld, de a PR 6 commitnyira lemaradt a jelenlegi main-től. A 282 commitnyi előrehaladás nagy változáscsomagot jelent, ezért a mainbe integrálás előtt a teljes diff és a migrációs történet review-ja szükséges. A CI zöld állapota nem helyettesíti ezt a review-t.

## 2. Kódellenőrzés: mi van már implementálva?

Az alábbi státuszok különválasztják a jelenlegi `main` állapotát és a PR #13-ban lévő, de még be nem olvasztott megvalósítást.

| Terület / javaslat | Ellenőrzött megvalósítás | Státusz |
|---|---|---|
| Explicit task approval | A dashboard csak explicit jóváhagyás után hívja a task műveletet; az approval paraméter szigorúan boolean. Tesztek ellenőrzik a tiltást. | **Implementálva** |
| Pending audit a task művelet előtt | A task végrehajtás előtt pending auditot ír; sikertelen auditnál megáll. | **Implementálva** |
| Task create idempotencia | A PR tartalmaz stabil `operation_id` mezőt, unique partial indexet, konfliktus utáni rekord-visszakeresést és replay tesztet. | **PR-ben implementálva; mainbe még nem került** |
| Minden műveletre kiterjedő idempotencia | A task create kapott deduplikációt, de ez nem terjed ki minden task update/close, e-mail és egyéb külső mellékhatásra. | **Részleges; fejlesztendő** |
| Több processz közötti egyszer használatos approval | A dashboard sessionből eltávolítja a pending approvalt a végrehajtás előtt, de ez nem közös, adatbázis-szintű atomikus consume. | **Hiányzik; fejlesztendő** |
| Task konkurens módosítás elleni védelem | Update/close útvonal ellenőrzi az állapotot és az üres update eredményt konfliktusként kezeli; tesztek fedik a konkurens változás szimulációját. | **Részben implementálva; nem oldja meg az approval race-t** |
| Audit fail-closed | Több érzékeny útvonal pending audit hibánál leáll; központi audit tesztek ellenőrzik például a lead importot, kutatást és inbound email feldolgozást. | **Részben implementálva; teljes útvonal-lefedettség review szükséges** |
| SMTP küldési biztonság | SMTP-kód és mockolt siker/hiba tesztek léteznek; a kimenő küldés jelenleg biztonsági kapcsolóval tiltott. A küldési folyamat pending/success/failed/unknown auditállapotokat kezel. | **Alapok implementálva; éles küldés tiltott** |
| E-mail idempotencia és bizonytalan retry | Van operation ID audit célra és az unknown SMTP-kimenetel naplózása, de nincs bizonyított, tartós, szolgáltatói idempotencia a duplikált küldés ellen. | **Hiányos; fejlesztendő az e-mail engedélyezése előtt** |
| SMTP integrációs tesztek | Mockolt tesztek fedik a konfigurációt, hibákat, STARTTLS sikerutat és header injectiont. | **Implementálva mock szinten** |
| Gemini retry | Korlátozott retry konfiguráció szerepel a közös kliensben. | **Implementálva; további rate-limit/timeout mátrix ellenőrzése szükséges** |
| IMAP/Gemini/SMTP teljes integrációs mátrix | A külső szolgáltatások egyes hibái mockolva teszteltek; ez nem azonos a teljes, dedikált integrációs tesztcsomaggal. | **Részleges** |
| Titokredakció az auditban | A közös auditkód érzékeny mezőket redaktál. | **Implementálva; regressziós lefedettséget fenn kell tartani** |
| Auth szerepkör-ellenőrzés | A PR-ban külön Auth helper és ellenőrzött user-JWT kliensút van; szerepkör a megbízható `app_metadata`-ből származik, fail-closed módon. | **PR-ben implementálva; mainbe még nem került** |
| RLS/GRANT szerepkörmátrix | A PR migráció shared-workspace admin/operator/reader policy-kat, grantokat és audit korlátozásokat tartalmaz; SQL postcondition teszt ellenőrzi a katalógust. | **PR-ben implementálva; mainbe még nem került** |
| Valós Auth/JWT/RLS smoke | Kézi live smoke script létezik Auth-issued JWT, role claim refresh, invalid JWT és PostgREST hozzáférés ellenőrzésére. | **Tesztkód implementálva; élő futás nincs igazolva** |
| Migrációs katalógus-ellenőrzés | A PR SQL teszt ellenőrzi a táblatulajdonost, RLS policy-kat, grantokat, function ACL-t, triggereket, indexeket és default ACL-t izolált PostgreSQL fixture-ben. | **PR-ben implementálva; mainbe még nem került** |
| Migration ledger eltérés | A PR dokumentálja a két 20261117 migráció eltérését és a reconciliation vizsgálatot; production javítás nem történt. | **Dokumentált; tényleges reconciliation nyitott** |
| Production backup CI restore | Titkosított backup útvonal és izolált PostgreSQL 17 restore teszt létezik; a CI futások sikeresek. | **CI-ben igazolt** |
| Konkrét production archívum külön adatbázisba restore-ja | A CI fixture restore nem bizonyítja a tényleges production archívum teljes helyreállíthatóságát. | **Hiányzik** |
| RPO/RTO, retention, incidenskezelés | A release/üzemeltetési dokumentáció említi, de teljes, jóváhagyott célértékek és runbook még nem igazoltak. | **Hiányzik / tisztázandó** |
| Supabase teljes platform- és Storage mentés | A public-schema logikai backup nem bizonyít Auth, Storage bináris objektumok és projektkonfiguráció teljes helyreállítását. | **Nyitott tervezési feladat** |
| Multi-tenant izoláció | A jelenlegi RLS shared-workspace modell; nem tenantonkénti izoláció. | **Nincs implementálva; csak több ügyfél kiszolgálásakor szükséges** |
| WORM / külső audit hash anchor | A hash chain nem véd a teljes adatbázis-tulajdonosi jogosultsággal szemben. | **Nincs implementálva; követelményfüggő** |

## 3. Ténylegesen hátralévő fejlesztési javaslatok

Az alábbi lista kizárólag azokat a tételeket tartalmazza, amelyek a fenti kódellenőrzés alapján még nem teljesek. A már implementált tételek nem szerepelnek újra.

### P0 – merge előtt

1. A PR-t frissíteni kell a jelenlegi `main`-hez; jelenleg 6 commit behind.
2. A 282 commitnyi teljes változáscsomag diff- és commit-review-ja szükséges, különösen az Auth/JWT/RLS, SQL migrációk, backup workflow és dashboard approval útvonalak tekintetében.
3. A frissített PR-head teljes kötelező CI-jét újra ellenőrizni kell.
4. A main és PR eltérő fájlállapotait felül kell vizsgálni; ne kerüljön vissza a mainre már bekerült dokumentációs vagy kódváltozás.
5. A merge stratégia csak a teljes review után választható ki.

### P1 – biztonság és üzleti logika

1. **Atomikus approval consumption:** közös, adatbázis-szintű one-use token/approval consume, amely több worker/process között is atomi; race teszt bizonyítsa, hogy egy approval legfeljebb egyszer használható fel.
2. **Idempotencia kiterjesztése:** a task create-on túl a releváns task műveletek és külső mellékhatások kapjanak stabil, tartós idempotencia-azonosítót.
3. **E-mail küldési garanciák:** SMTP unknown kimenetel, újrapróbálás, szolgáltatói elfogadás és duplikált küldés kockázatának kezelése. A küldés maradjon tiltva, amíg ez nincs lezárva.
4. **Audit teljesség:** a pending audit fail-closed ellenőrzését minden érzékeny műveleti útvonalra ki kell terjeszteni, és hiányzó regressziós tesztekkel alátámasztani.
5. **Integrációs tesztmátrix:** Gemini/SMTP/IMAP timeout, retry, rate limit, részleges hiba és titokredakció lefedése; a mockolt teszteket ne nevezzük élő integrációs validációnak.

### P1 – Supabase / migráció

1. A két 20261117 migrációs fájlnév és remote migration ledger eltérésének CLI-kompatibilis reconciliation terve, majd független review.
2. A live Auth/JWT/RLS smoke futtatása kizárólag már létező, kifejezetten engedélyezett izolált Supabase környezetben; a futás bizonyítékának archiválása.
3. A migrációk, RLS, GRANT, SECURITY DEFINER függvények és function ACL-ek független SQL review-ja.
4. A PR-ban lévő SQL fixture teszteket a frissített main-alapú PR headen újra kell futtatni.

### P2 – üzemeltetés és jövőbeni architektúra

1. A konkrét production backup külön adatbázisba restore-ja és post-restore jegyzőkönyv.
2. RPO/RTO, retention, riasztás, kulcsrotáció, incidenskezelés és restore runbook meghatározása.
3. A Supabase Auth, Storage és projektkonfiguráció mentési/helyreállítási igényeinek tisztázása.
4. Multi-tenant adatmodell és tenant RLS csak akkor, ha a termék több ügyfélre bővül.
5. Külső hash anchor/WORM csak akkor, ha adatbázis-tulajdonossal szembeni manipulációvédelem formális követelmény.

## 4. Egyetlen main ág – fejlesztési szabály

- A `main` az egyetlen tartós fejlesztési ág.
- Rövid életű PR ág csak technikai integrációs eszköz; a PR célága mindig `main`.
- Merge után az átmeneti ág lezárható/törölhető; minden új munka a friss `main`-ből indul.
- A `main` CI minden módosítás után kötelező.
- Production adatbázis-, Auth-, migrációs vagy infrastruktúra-módosítás külön, konkrét jóváhagyás nélkül nem végezhető.

## 5. Biztonsági korlátozások

- Production Supabase read-only.
- Auth/RBAC production flag OFF.
- Nincs jóváhagyás nélküli production DDL/DML, `supabase db push`, `supabase migration repair`, ledger edit, GRANT/REVOKE, RLS módosítás vagy Auth-user provisioning.
- Új Supabase account/projekt/branch nem hozható létre.
- AWS production deploy és PR merge külön jóváhagyást igényel.
