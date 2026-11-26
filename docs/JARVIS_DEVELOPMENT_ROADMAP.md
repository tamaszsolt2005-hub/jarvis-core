# JARVIS – elsődleges fejlesztési útiterv

**Aktuális fejlesztési ág:** docs/pre-feature-readiness-gates  
**Pull request:** [#26 – nyitott, nem merge-ölt](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26)  
**Telepítési állapot:** helyi Streamlit fejlesztés; JARVIS production app nincs deployolva.  
**Aktuális részletes állapot:** [CURRENT_STATE_AND_NEXT_STEPS.md](CURRENT_STATE_AND_NEXT_STEPS.md)  
**Parancsok:** [JARVIS_COMMAND_GUIDE.md](JARVIS_COMMAND_GUIDE.md)  
**Architektúra:** [JARVIS_DOCUMENTATION.md](JARVIS_DOCUMENTATION.md)

Ez a dokumentum a fejlesztési munka elsődleges iránytűje. A státusz mindig a PR aktuális headjéhez és a ténylegesen ellenőrzött tesztekhez kötendő. A régebbi dátumozott bekezdések történeti pillanatképek, nem jelenlegi állítások.

## Alapelv
A JARVIS figyelhet, elemezhet, lehetőséget ismerhet fel és belső műveletet javasolhat. Külső vagy adatbázist módosító végrehajtás csak az adott művelethez tartozó explicit jóváhagyással, megfelelő jogosultsággal és auditálható, idempotens úton történhet. Az automatikus javaslat nem egyenlő végrehajtással.

## Jelenlegi implementáció – PR #26

| Terület | Jelenlegi állapot | Korlát |
|---|---|---|
| Magyar chat és Gemini kontextus | Implementált | API-konfiguráció szükséges |
| Céges leadkutatás és grounding | Implementált | Explicit kutatási kérés és külön jóváhagyás |
| Cégazonosító/deduplikáció | Implementált, SQL concurrency tesztekkel | Production migráció nincs alkalmazva |
| Lead scoring és belső workflow-ajánlás | Implementált | Forrásolt kutatás szükséges |
| Task create/update/close | Approval-gated RPC-vel implementált | Minden művelet külön jóváhagyásos |
| Feladatközpont | Read-only dashboard oldal | A módosítás a chat approval flow-ban történik |
| Consent-aware follow-up queue | Read-only, fail-closed szűrés | Nem küld üzenetet |
| Eredményalapú következő teendő | Implementált | Csak lezárt outcome_measurement task explicit besorolásából |
| Hosszú távú memória | Explicit save/list/forget | Nem teljes tudásgráf; érzékeny adat tiltott |
| Napi briefing/analitika/audit | Implementált modulok | Adatminőség és hozzáférés függvénye |
| Inbound inbox monitor | Kódban/workflow-ban előkészített | Config és futtatási környezet szükséges |
| Outbound email | Hard-disabled | Nincs küldés |
| Auth/RBAC | Kódban/migrációkban előkészített | Production flag OFF, live smoke nincs |
| Általános scheduler/worker | Nincs kész | Külön idempotens claim/worker fejlesztés kell |
| Production JARVIS app | Nincs deployolva | Host nincs kiválasztva |

## Fejlesztési prioritások

### 1. Workflow végponttól végpontig
- Leadkutatás → minősítés → stratégia → belső feladat → jóváhagyás → utánkövetési jogosultság-ellenőrzés → eredménymérés.
- Task státusz és workflow stage teljes konzisztenciája.
- Pozitív/negatív/nincs válasz eredménykódok és újraminősítési ciklus.
- Megszakítás, folytatás, audit és idempotencia E2E tesztjei.
- Külső outreach továbbra is tiltott, amíg külön engedélyezett és biztonságosan igazolt nincs.

### 2. Önálló, idempotens háttérfolyamat
- Worker belépési pont dashboard sessiontől függetlenül.
- DB-alapú claim/lease, heartbeat, retry limit, dead-letter és operation ID.
- Több worker concurrency teszt.
- Elsőként csak read-only monitor/briefing munka; e-mail küldés nélkül.

### 3. Memória és üzleti tudás
- Forrás, dátum, confidence és jogosultság kezelése.
- Döntés/eredmény/tanulság összekapcsolása lead/task rekordokkal.
- Frissesség, inaktiválás, retention és visszakeresési minőség.
- Tények és modellkövetkeztetések elkülönítése.

### 4. Dashboard teljessége
- Analitika, audit, memória és üzleti információ oldalak tényleges funkcióinak ellenőrzése.
- A még dekoratív/hiányos oldalelemeket csak implementáció után dokumentáljuk működőként.
- UI hibajelzések és adatforrás-hibák egyértelmű kezelése.

### 5. Production release – külön fázis
- App-host kiválasztása és app deploy terv.
- Production migration drift és teljes SQL review.
- Auth/JWT/RLS modell és smoke.
- RPC-alapú app telepítése, majd csak utána a service-role közvetlen DML lockdown.
- Backup, rollback, health check, audit és task approval smoke.
- Kimenő e-mail hard-disable csak külön biztonsági review és konkrét jóváhagyás után oldható fel.

## Kötelező biztonsági kapuk
- Production DB DDL/DML, migration push/repair, ledger módosítás, GRANT/REVOKE, RLS/Auth flag, secret, deploy, e-mailküldés és PR merge külön konkrét felhasználói jóváhagyás nélkül tilos.
- Ne olvass vagy jeleníts meg titokértéket.
- CI zöld státuszt csak az adott commit SHA és teljes workflow eredmény ellenőrzése után állíts.
- Korábbi zöld CI nem igazolja az újabb commitot.
- A Supabase production DB létezése nem bizonyít JARVIS app deployt.

## Fejlesztési munkamódszer
Minden funkcióhoz célzott implementáció, unit/AppTest/SQL teszt, releváns dokumentáció és PR CI szükséges. A fejlesztés PR/branch szinten marad; merge csak külön jóváhagyásra.


## Stratégiai cél: önálló kutató és személyre szabott SaaS-ügynök

A hosszú távú termékvízió és részletes fázisok: [JARVIS_AUTONOMOUS_SAAS_VISION.md](JARVIS_AUTONOMOUS_SAAS_VISION.md).

A JARVIS célja, hogy önállóan cégeket fedezzen fel, forrásolt cégdossziét és szakmai döntéshozói kontextust készítsen, a cég valós problémáiból több egyedi SaaS-ötletet generáljon, ezeket magyarázhatóan rangsorolja, majd a globális és cégenkénti termék-tiltó/negatív ajánlási naplóval ütköztesse. A legjobb ötlethez személyre szabott, forrásolt ajánlatot és e-mail-tervezetet készítsen. Érdeklődés esetén igényfelmérés és szerződéses elfogadás után külön belső jóváhagyással indulhat AI-támogatott termékfejlesztési projekt.

### Phase 1 – cégfelderítés és cégdosszié: első implementációs szelet

A meglévő `global_lead_research.py` + `global_lead_research_job.py` és a napi `global-lead-research.yml` workflow már végrehajt Google Search groundinggal támogatott, legfeljebb 15 új cégre korlátozott kutatást. A `feature/company-research-phase-1` ág ezt bővíti:
- strukturált, kategorizált cég-tények (üzleti modell, termékek, ügyfélszegmensek, piacok, növekedési/technológiai/működési jelek és nyilvános hírek);
- nyilvános, szakmai döntéshozói név/szerepkör/háttér, kizárólag groundinggal igazolt forrás esetén;
- `company_dossier.py` validáció: csak engedélyezett üzleti kategória és a Google groundingben szereplő domain maradhat;
- a rövid dosszié a meglévő lead `notes` mezőjébe kerül, séma-/production-migráció nélkül;
- a Gemini-kutatási hívás átmeneti hálózati/szerverhibánál legfeljebb 3 alkalommal, növekvő várakozással újrapróbálkozik; hitelesítési és más nem átmeneti hibánál azonnal leáll;
- személyes e-mail/telefon, érzékeny vagy magánéleti adat nem kerül a dossziéba; kutatás nem ad kapcsolatfelvételi engedélyt.

**A Phase 1 még nincs kész:** külön, újrafuttatható worker claim/lease és retry/dead-letter protokoll, kutatási futások és tények normalizált, verziózott tárolása, adatfrissesség és célzott emberi ellenőrző UI még hátravan. A meglévő napi GitHub Actions workflow léte nem bizonyít production worker futást.

### Új stratégiai fejlesztési sorrend
1. Automatikus, idempotens cégfelderítő worker és kutatási források.
2. Verziózott cégdosszié, szakmai döntéshozó-kutatás, bizonyíték- és problémahipotézis.
3. Egyedi SaaS-termékötlet motor, összehasonlítható pontozással.
4. Globális termék-/ajánlási tiltó napló, elutasítások, ügyfélközi kizárólagosság és hasonlósági ütközésvizsgálat.
5. Forrásolt, személyre szabott ajánlat és e-mail-tervezet, emberi megfelelőségi kapukkal.
6. Válaszkezelés, értékesítési pipeline, szerződéses és fejlesztésindítási gate.
7. AI-támogatott terméképítés, tesztelés, átadás és eredményalapú tanulás.

Ezek célfunkciók, nem a jelenlegi implementáció állapotjelentései. A meglévő leadkutatás, pontozás, task workflow és memória alapot ad, de a teljes automatikus kutatási és személyre szabott SaaS-folyamat még nincs kész. Outbound e-mail hard-disable és production biztonsági kapuk változatlanok.