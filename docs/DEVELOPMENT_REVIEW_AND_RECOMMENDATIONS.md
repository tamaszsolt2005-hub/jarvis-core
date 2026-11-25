# JARVIS – fejlesztési áttekintés és javaslatok

**Felülvizsgálat időpontja:** 2026-11-25 14:11 CET  
**Cél:** egyetlen hosszú távú fejlesztési ág: `main`  
**Repository:** https://github.com/tamaszsolt2005-hub/jarvis-core

## Vezetői összefoglaló

A fejlesztés célállapota egyetlen tartós `main` ág. A PR/feature ágak csak átmeneti integrációs eszközök; a feladatok lezárása után a változások a `main`-be kerülnek, és a további munka ott folytatódik. Nem cél párhuzamos, tartós fejlesztési ágak fenntartása.

A jelenlegi nyitott integráció a [PR #13](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/13), amely Supabase Auth/RBAC, migrációs, audit-, backup/restore- és tesztelési változásokat tartalmaz.

### Ellenőrzött GitHub-állapot

| Elem | Ellenőrzéskori állapot |
|---|---|
| `main` HEAD | `2fb9081f80741692a05d08f805c04d0a23ad1350` |
| PR #13 HEAD | `32aef539c0128c1fedaa9e03768477433e93abe1` |
| PR base | `main` |
| PR draft / merged | draft / nincs merge-elve |
| PR mergeability | Az API friss mergeability értéke ebben az ellenőrzésben nem volt külön lekérve |
| Branch összehasonlítás | 282 commit ahead, 0 commit behind |
| Legfrissebb PR workflow | [45620672894](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45620672894): fut |
| PR workflow jobok | `backup-restore-integration` sikeres; `test` fut |
| Ugyanezen HEAD push workflow | [45620664359](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45620664359): sikeres |

A korábbi `09bde885...` headhez tartozó sikeres CI nem helyettesíti a frissebb `32aef539...` head teljes ellenőrzését. A PR jelenlegi teljes CI-eredménye ezért még **nem tekinthető lezártnak**.

**Fontos integrációs kockázat:** a PR 282 commitot tartalmaz a `main`-hez képest. Ez lényegesen több, mint egy kis, izolált PR; a változáscsomag méretét, commit-történetét és teljes diffjét merge előtt külön review-zni kell. A 0 behind csak azt jelenti, hogy a PR a jelenlegi `main`-ből indul, nem azt, hogy a PR változásai már a `main` részei.

## Mi készült el / mi van bizonyítva

- A main ágon lévő korábbi CI és a PR korábbi headjein futó CI sikeres volt; a konkrét head és run azonosítóját mindig ellenőrizni kell.
- A PR-ban elkészült az Auth/RBAC alap, az app_metadata szerepkör-ellenőrzés, a user-JWT kliensút, a shared-workspace RLS/GRANT migráció és az ehhez tartozó regressziós tesztkészlet.
- A migrációs replay, CLI repair szemantika és katalógus-postcondition ellenőrzések izolált PostgreSQL 17 CI fixture-re készültek.
- A titkosított production logikai backup S3 feltöltése, letöltése, visszafejtése és hash ellenőrzése korábbi futásban sikeres volt.
- Az izolált PostgreSQL 17 CI restore-round-trip sikeres volt.
- A production adatbázis nem módosult; Auth/RBAC éles flag kikapcsolva maradt.

Ezek nem bizonyítják automatikusan a production Auth/RLS működését, a konkrét production archívum külön adatbázisba történő visszaállítását vagy a teljes Supabase platform és Storage menthetőségét.

## Fejlesztési javaslatok – prioritási sorrendben

### P0 – PR merge-biztonság

1. A legfrissebb PR-head teljes CI-jének megvárása; minden kötelező job legyen zöld.
2. A PR teljes diffjének és a 282 commitból álló történetnek a review-ja; különösen migrációk, jogosultságok, backup workflow, Auth klienshatár és jóváhagyási műveletek.
3. A README, központi műszaki dokumentáció, release gate és CI napló státuszainak egyetlen, egymással összhangban álló állapotra hozása.
4. A PR merge stratégiájának és a branch-történetnek a felülvizsgálata. Squash merge csak akkor, ha a teljes változáscsomag review-zott és a repository szabályai engedik.
5. A merge után a PR/feature ág lezárása, és a további fejlesztés kizárólag `main`-en.

### P1 – Kód- és üzleti biztonság

1. **Atomikus approval consumption:** a pending jóváhagyás egyszeri felhasználását adatbázis-szintű atomikus művelet védje több worker/process esetén is. Versenyhelyzetes teszt bizonyítsa, hogy ugyanaz az approval legfeljebb egyszer hajtható végre.
2. **Replay/idempotencia:** az érzékeny task- és e-mail-műveletek stabil operation ID-val és tartós idempotencia-nyilvántartással legyenek védve; retry és bizonytalan hálózati kimenet ne okozzon duplikált mellékhatást.
3. **E-mail delivery idempotencia:** külön kell kezelni az SMTP szerver általi átvételt, a tényleges kézbesítést és az ismeretlen kimenetelű küldést. Bizonytalan állapot után ne legyen vak automatikus újraküldés.
4. **Audit fail-closed:** minden érzékeny művelet előtt a pending audit esemény tartós rögzítése legyen kötelező; audit hiba esetén a művelet álljon le.
5. **Külső integrációs tesztek:** Gemini, SMTP és IMAP kontrollált, mockolt és ahol engedélyezett, dedikált integrációs tesztekkel; timeout, retry, rate limit, részleges hiba és titokredakció lefedésével.

### P1 – Supabase és migrációk

1. A két 20261117 migrációs verzió és a remote migration ledger eltérésének pontos, CLI-kompatibilis reconciliation terve.
2. A productionnel egyező owner, grant, policy, function ACL, trigger, index és default privilege postconditionök bizonyítása.
3. Független SQL review a migrációkhoz, RLS-hez, SECURITY DEFINER függvényekhez és jogosultságokhoz.
4. Valós Auth-issued JWT/PostgREST teszt kizárólag már létező, kifejezetten engedélyezett izolált Supabase környezetben. Új projekt/branch létrehozása és production célzása nem megengedett.

### P2 – Üzemeltetés

1. A production archívum külön adatbázisba történő restore-ja és részletes post-restore jegyzőkönyv.
2. RPO/RTO célok, retention, riasztások, kulcsrotáció, incidenskezelés és helyreállítási runbook.
3. A public-schema logikai backup határainak egyértelmű kezelése: ez önmagában nem teljes Supabase platform-, Auth-, Storage bináris objektum- és projektkonfiguráció-mentés.
4. Több-tenant adatmodell és tenant-szintű RLS csak akkor, ha a termék ténylegesen több ügyfelet szolgál ki.
5. Audit hash-chain külső hash-ankorral vagy WORM tárolással, ha adatbázis-tulajdonossal szembeni manipulációvédelem követelmény.

## Merge-kritériumok

A PR csak akkor tekinthető merge-ready állapotúnak, ha:

- [ ] a legfrissebb PR-head minden kötelező CI-jobja sikeres;
- [ ] nincs merge conflict és a PR a legfrissebb main-ből indul;
- [ ] a teljes diff és a migrációk review-ja lezárult;
- [ ] nincs nyitott P0 kód- vagy CI-blokkoló;
- [ ] az ismert P1 hiányosságok vagy javítva vannak, vagy kifejezetten elfogadott, dokumentált, nem blokkoló follow-upként szerepelnek;
- [ ] a dokumentáció pontosan tükrözi a kód és a tesztek tényleges állapotát;
- [ ] a merge-re külön, kifejezett döntés születik.

A production aktiválás külön kapu: a repository CI zöld állapota önmagában nem engedélyez production migrációt, Auth/RBAC bekapcsolást vagy adatbázis-írást.

## Egyetlen main ág – munkafolyamat

1. A `main` az egyetlen tartós fejlesztési és integrációs alap.
2. Rövid életű PR ág csak akkor használható, ha a GitHub folyamat megköveteli; a PR-t a `main`-be kell irányítani.
3. Merge után a PR ág megszüntethető; új feladatnál ismét a `main` az alap.
4. A main CI minden módosítás után kötelező.
5. Production módosítás, migráció, Auth provisioning vagy deploy külön jóváhagyás nélkül nem végezhető.

## Biztonsági korlátozások

- Production Supabase marad read-only, amíg külön, konkrét változtatási terv nincs jóváhagyva.
- Auth/RBAC production flag OFF.
- Nincs production `db push`, `migration repair`, ledger edit, DDL/DML, GRANT/REVOKE, RLS módosítás vagy Auth-user provisioning.
- Nem hozunk létre új Supabase accountot, projektet vagy branch-et.
- AWS production deploy és PR merge külön jóváhagyást igényel.
