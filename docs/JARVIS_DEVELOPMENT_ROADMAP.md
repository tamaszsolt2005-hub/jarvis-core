# JARVIS – elsődleges fejlesztési útiterv

**Aktuális ág:** `feature/company-research-phase-1`  
**Aktuális PR:** [#27 – nyitott, nem merge-ölt](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/27)  
**Alap PR:** [#26 – nyitott, nem merge-ölt](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26)  
**Központi dokumentáció:** [JARVIS Master Documentation](JARVIS_MASTER_DOCUMENTATION.md)  
**Aktuális állapot:** [CURRENT_STATE_AND_NEXT_STEPS.md](CURRENT_STATE_AND_NEXT_STEPS.md)

A roadmap a fejlesztési sorrendet határozza meg. A kódban lévő funkciót, a CI-vel tesztelt viselkedést, a külső integrációt és a productionben aktív működést külön kell kezelni.

## Alapelv

A JARVIS először kutat és elemez, utána javasol. Adatbázis-írás, külső kapcsolatfelvétel, szerződés vagy fejlesztésindítás csak külön jogosultság- és jóváhagyási kapun keresztül történhet.

## Jelenlegi funkcionális alap

| Terület | Állapot | Korlát |
|---|---|---|
| Magyar Gemini chat | Implementált | API és helyi konfiguráció szükséges |
| Explicit céges leadkutatás | Implementált | Nem autonóm folyamatos worker |
| Cégazonosítás/deduplikáció | Implementált | Migrációs release kapuk külön kezelendők |
| Lead scoring/workflow ajánlás | Implementált | Belső javaslat, nem külső végrehajtás |
| Task CRUD | Jóváhagyásos | Külön approval szükséges |
| Task center/follow-up queue | Read-only | Nem küld üzenetet |
| Üzleti memória, briefing, analitika, audit | Implementált modulok | Konfiguráció és hozzáférés függő |
| Outbound email | Hard-disabled | Nincs küldési engedély |

## Phase 1 – cégkutatás és dosszié-előzmények

**Implementált kódszeletek a PR #27-ben:**
- Grounding-alapú strukturált cégkutatás.
- Forrásdomainhez kötött tényvalidálás.
- Nyilvános szakmai döntéshozói kontextus; privát elérhetőségek kizárása.
- Dosszié snapshot UUID, időbélyeg, schema version és hash.
- Append-only snapshot store és repository migráció.
- Fail-closed dosszié-frissességi függvény.
- Refresh eligibility policy: explicit elutasítás/opt-out kizárása, két válasz nélküli follow-up után szüneteltetés, meg nem keresett lead kutatható marad.

**Hátralévő munka:**
1. CI sikeresség igazolása a végleges PR head SHA-n.
2. Refresh candidate planner, amely a frissesség és a kizárási policy metszetét használja.
3. A lead státusz és follow-up számláló megbízható integrációja ténylegesen elküldött eseményekkel.
4. Idempotens worker: claim/lease, heartbeat, bounded retry, dead-letter, operation ID.
5. Rate limit, költségkeret és futási limitek.
6. Kutatási előzmények UI és változásösszefoglaló.
7. Emberi felülvizsgálat és audit.

**Elfogadási feltételek:**
- Nincs duplikált lead vagy snapshot felülírás.
- Minden megtartott üzleti tény visszavezethető grounding forráshoz.
- Elutasított és opt-out lead automatikus frissítése blokkolt.
- Két tényleges, válasz nélküli follow-up után frissítés szünetel.
- Meg nem keresett lead kutatható, de kapcsolatfelvételre nem válik automatikusan jogosulttá.
- Worker hiba/retry nem okozhat duplikált kutatási műveletet.
- Nincs automatikus outbound kommunikáció.

## Phase 2 – üzleti problémahipotézis

- A dosszié tényekből különítse el a bizonyítékot, következtetést és hipotézist.
- A problémákhoz confidence, forrás és ellenőrizendő kérdés tartozzon.
- Bizonyítékhiány esetén további kutatás legyen a kimenet, ne kitalált probléma.

## Phase 3 – egyedi SaaS-termékötlet motor

- Cégenként több termékkoncepció generálása.
- Értékelés üzleti érték, illeszkedés, bizonyítottság, megvalósíthatóság, kockázat, költség és differenciálás alapján.
- Alternatívák és meglévő piaci megoldások vizsgálata.
- Indokolt esetben a rendszer tartózkodjon az ajánlástól.

## Phase 4 – globális és cégenkénti termék-tiltó napló

- Globális, iparági és cégenkénti kizárások.
- Elutasított ajánlatok és korábbi sikertelen ötletek megőrzése.
- Determinisztikus fingerprint és szemantikus hasonlóságvizsgálat.
- Aktív projektek és ügyfélközi kizárólagosság ellenőrzése.
- Auditált feloldás és emberi jóváhagyás.

## Phase 5 – személyre szabott ajánlat és outreach előkészítés

- Forrásolt üzleti megfigyelés és problémahipotézis.
- Vezető szakmai szerepéhez illeszkedő ajánlati tervezet.
- Marketingjogalap, országonkénti szabályok, suppression és opt-out ellenőrzés.
- Emberi jóváhagyás.
- Outbound email külön fejlesztési és engedélyezési döntésig hard-disabled marad.

## Phase 6 – válaszkezelés és értékesítési pipeline

Külön állapot az érdeklődés, kérdés, elutasítás, későbbi kapcsolatfelvétel, leiratkozás, besorolásra váró válasz és válasz nélküli állapot. A „nincs válasz” nem egyenlő elutasítással.

## Phase 7 – szerződött AI-assisted termékfejlesztés

- Elfogadott és verziózott scope.
- Írásos szerződés/megrendelés és kereskedelmi feltételek.
- Adatkezelés, tulajdonjog, licencek és felelősség tisztázása.
- Külön belső projektindítási jóváhagyás.
- Specifikáció, architektúra, kód, teszt, security review, ügyfél-elfogadás és átadás.

## Phase 8 – mérés és tanulás

Az ajánlások, elutasítások, ügyfélhasználat, fejlesztési költség és eredmény visszacsatolása a kutatás és rangsorolás javításához.

## Release és biztonsági szabály

A roadmap nem jogosít production DB-módosításra, migrációfuttatásra, Auth/RBAC aktiválásra, secret-változtatásra, deployra, e-mailküldésre vagy PR merge-re. Ezek külön, konkrét jóváhagyást igényelnek.
