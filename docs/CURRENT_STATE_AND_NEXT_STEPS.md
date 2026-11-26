# JARVIS – aktuális állapot és következő lépések

**Frissítve:** 2026-11-26  
**Fejlesztési ág:** `docs/pre-feature-readiness-gates`  
**PR:** [#26 – nyitott, nem merge-ölt](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26)  
**PR-állapot:** a PR #26 mindenkori aktuális headje és checkjei a [GitHub PR-oldalon](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26) követhetők.

## 1. Hol tartunk most?

**A JARVIS alkalmazás még nincs telepítve publikus vagy production alkalmazás-hostra.** Jelenleg helyi fejlesztés zajlik, a Streamlit dashboardot helyben indítjuk. Nincs kiválasztott JARVIS app-host, nincs JARVIS app URL, és nincs futó JARVIS production alkalmazás. A korábban vizsgált Railway `VolleyForm` projekt nem JARVIS.

Fontos különbség: létezik egy Supabase production adatbázis-projekt, de ez önmagában nem jelenti azt, hogy a JARVIS Streamlit alkalmazás is telepítve lenne. A Supabase production állapotára vonatkozó adatokat a [production audit dokumentum](PRODUCTION_STATE_AND_MIGRATION_PLAN.md) időbélyeggel és read-only bizonyítékként kezeli.

A következő fejlesztési munka **helyi, funkciófejlesztési szakaszban** történik. A production release kapuk nem akadályozzák a helyi funkciófejlesztést; csak az éles telepítés, adatbázis-módosítás vagy külső mellékhatás engedélyezése előtt kötelezőek.

## 2. Aktuális repo és CI állapot

- PR #26 nyitott, nem merge-ölt; a változtatásokat nem integráltuk a `main` ágba.
- A 2026-11-26-i, kódot is tartalmazó ellenőrzött PR-headen a `test`, `backup-restore-integration`, `CodeQL`, `Analyze Python` és `pip-audit` checkek sikeresek voltak. A későbbi dokumentációs frissítések után az aktuális futások állapotát mindig a [PR checkjein](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26/checks) kell ellenőrizni.
- A branchben implementált és CI-vel tesztelt a cégazonosítási `upsert_company_lead` RPC, a normalizált cégnév/domain aliasok tranzakciós zárolása, a CSV- és global research íróútvonal közös RPC-használata, a kontaktjelöltek consent-aware prioritása, valamint a két PostgreSQL sessionös concurrency teszt.
- A kód/CI állapot nem production telepítési bizonyíték. A PR merge külön jóváhagyást igényel.

## 3. Elkészült fő technikai alapok

- Task approval és műveleti RPC-k: atomikus approval consume, operation ID-alapú replay-védelem és audit fail-closed tesztek.
- E-mail küldés: kódszintű hard-disable aktív; bizonytalan kézbesítési kimenetel nem retry-olható automatikusan. A Resend adapter kódban jelen van, a dokumentált workflow konfiguráció Gmail SMTP-t használ; egyik provider élő küldési útja sincs igazolva. Külső e-mail küldés tiltva marad.
- Lead/cégazonosítás: a korábban nyitott, alkalmazásszintű global-research race kockázatot a PR #26 közös, tranzakciós RPC-íróútja kezeli; az izolált két-session teszt sikeres.
- A PostgreSQL 17 migrációs, pgTAP és backup/restore integrációs tesztek CI-ben sikeresek.

## 3/A. Első workflow-szelet – lead → belső task-javaslat

A PR #26 branchben a `lead_workflow.py` read-only modul a strukturált, forrásolt leadkutatási adatból belső ellenőrzési feladatot javasol. A napi briefing megjeleníti a prioritást, üzleti illeszkedést, bizonyosságot, bizonyítékszámot és indoklást. Ez a javaslat önmagában nem ír adatbázist és nem ad kapcsolatfelvételi engedélyt.

## 3/B. Második workflow-szelet – leadhez kapcsolt, jóváhagyásos task

A PR #26 branchben a napi briefingben megjelenő javaslatból explicit chat-paranccsal előkészíthető a leadhez kapcsolt feladat:

- Parancs: `Hozz létre javasolt feladat: <lead UUID>`.
- A dashboard újraolvassa a lead kutatási forrását, a bizonyítékokat és a leadhez már kapcsolt feladatokat; csak érvényes, forrásolt kutatásból épít taskot.
- A feladat a meglévő egyhasználatos, principal- és payload-kötött approval mechanizmuson keresztül kerül jóváhagyásra; jóváhagyás előtt nincs task-írás.
- A task payload a `tasks.lead_id` mezőben tartósan összekapcsolja a feladatot a lead rekorddal.
- Az atomikus RPC leadenként advisory lockot használ, és nem enged két párhuzamos nyitott első feladatot ugyanahhoz a leadhez. Lezárt feladat után későbbi lépés létrehozható.
- A migrációs SQL teszt lefedi a leadkapcsolatot, a nyitott feladat duplikációjának blokkolását és a lezárt feladat utáni továbblépést. A Python tesztek a parancsot, a forrásellenőrzést és a payload-validációt fedik le.

**Biztonsági határ:** ez továbbra is belső task, nem e-mail vagy outreach. Nem állít be consentet, nem változtat lead státuszt, nem küld üzenetet. A friss PR CI-futásnak kell igazolnia a módosításokat; production migráció vagy deploy nem történt.

A teljes leadkutatás → minősítés → stratégia → feladat → jóváhagyás → utánkövetés → eredménymérés folyamat még nincs kész. Következő fejlesztési szelet: a feladat állapotának és a lead üzleti workflow állapotának összekapcsolása, majd a follow-up és eredménymérés.

## 4. Mi maradt még a funkciófejlesztés előtt?

**Nincs olyan igazolt production-host vagy Supabase release-feladat, amely miatt a helyi funkciófejlesztést meg kellene állítani.** A következőket viszont érdemes a funkciók bővítése közben, megfelelő sorrendben kezelni:

1. **Helyi integrációs ellenőrzés:** a dashboard fő útvonalainak kézi végigpróbálása valós helyi konfigurációval, titkok megosztása nélkül; hibák és hiányzó konfigurációk dokumentálása.
2. **Konfigurációs határok:** egyértelműen váljon szét a helyi fejlesztői konfiguráció, a szerveroldali titkok és a későbbi host-specifikus konfiguráció. Ne legyen titok a repóban vagy a kliensoldalon.
3. **Háttérfolyamatok:** különítsük el a dashboard által indított felhasználói kéréseket a scheduler/worker feladatoktól. A későbbi hosztingnál az ütemezett munkák ne függjenek nyitott böngészőfültől vagy aktív Streamlit sessiontől.
4. **E-mail:** maradjon tiltva a valódi kimenő küldés addig, amíg nincs kiválasztott provider, hitelesített tesztkörnyezet, provider oldali idempotencia-ellenőrzés és külön jóváhagyás.
5. **Lead workflow minősége:** az új cégazonosítási protokollt minden később hozzáadott lead-létrehozó útvonalnak is használnia kell; ne vezessünk be párhuzamos közvetlen INSERT-et.

Ezek nem mindegyike blokkoló egy-egy önálló, helyben tesztelhető funkcióhoz. A roadmapben a legkorábbi valódi funkcionális hiányt kell választani, és csak az adott funkcióhoz szükséges előfeltételeket kell előre venni.

## 5. Külön production/release kapuk – későbbre

A következőket nem kell most végrehajtani, és egyikre sem ad ez a dokumentum engedélyt:

- JARVIS alkalmazás-host kiválasztása és első deploy.
- Friss production Supabase read-only audit, migration drift és teljes SQL review.
- Auth/JWT/RLS modell és élő smoke teszt egy engedélyezett izolált környezetben.
- Az RPC-t használó app telepítése és smoke tesztje; csak ezután a megfelelő privilege-lock migráció.
- Backup/restore, health check, logolás, riasztás, hozzáférés- és rollback-eljárás.
- Production secret, SMTP, Auth/RBAC, GRANT/REVOKE, DDL/DML, deploy vagy PR merge kizárólag külön, konkrét jóváhagyással történhet.

## 6. Döntési szabály a folytatáshoz

Most a helyi funkciófejlesztést folytatjuk. A hosting kiválasztását későbbre hagyjuk, amikor a szükséges always-on worker, ütemezés, hozzáférésvédelem, e-mail provider és üzemeltetési igények már világosak. A dokumentumok közül ez az aktuális összefoglaló; a [roadmap](JARVIS_DEVELOPMENT_ROADMAP.md) határozza meg a funkciófejlesztés sorrendjét, a [release gate dokumentum](REMAINING_WORK_AND_RELEASE_GATES.md) pedig az élesítés feltételeit.


## 2026-11-26 – Feladatközpont a dashboardban

A PR #26 ágban a korábban csak vizuális oldalsávbeli Feladatok menüpont működő, külön Streamlit oldalt kapott.

- A Feladatközpont legfeljebb 500 feladatot olvas be a meglévő feladatmezőkkel; az adatforrás-hibát külön jelzi, nem mutatja üres listaként.
- Összesített számokat mutat az összes, nyitott, lejárt és sürgős feladatokról.
- Szűrés: aktív/lejárt, összes, lezárt, csak lejárt és sürgős; rendezés határidő, prioritás vagy létrehozás szerint.
- Megjeleníti a feladatazonosítót és a kapcsolt lead UUID-t, hogy a már meglévő chat-parancsok használhatók legyenek.
- A feladat létrehozása, módosítása és lezárása továbbra is kizárólag a chat jóváhagyási folyamatán keresztül történhet. Az oldal read-only; e-mailt nem küld és kapcsolatfelvételt nem indít.
- AppTest lefedi az üres állapotot, navigációt, a chat input elrejtését és a lejárt/sürgős feladatok megjelenítését.

**Állapot:** kódban implementálva és célzott AppTest hozzáadva; az új PR-head CI eredménye még ellenőrizendő. Production DB, konfiguráció, Auth/RBAC és deploy nem változott.


### Feladatközpont – utánkövetési sor

A Feladatközpont második funkciószelete egy belső, read-only utánkövetési sort jelenít meg a következő 7 nap esedékes és már lejárt elemeiből.

- Csak sent vagy follow_up_sent státuszú, érvényes e-mail-formátumú, kifejezett consent alappal, időbélyeges hozzájárulással és approved_to_contact=true értékkel rendelkező lead kerülhet be.
- Opt-out, bejövő válasz, reply kategória, hiányzó/hibás hozzájárulás, jövőbeli hozzájárulás és már felhasznált follow-up kizárja a leadet.
- A nézet csak cégnév, esedékesség, státusz és lead UUID mezőt mutat; e-mail-címet nem jelenít meg.
- A sor nem küld e-mailt, nem módosít lead státuszt és nem ad új kapcsolatfelvételi engedélyt. Az outbound email workflow továbbra is letiltott.
- A napi briefing ugyanazt a közös, tesztelt queue-szűrőt használja a lejárt utánkövetések számításához.

**Állapot:** kód és célzott unit tesztek hozzáadva; az új PR-head teljes CI-je még ellenőrizendő.


## 2026-11-26 – dashboard/configuration/háttérfolyamat audit

- A Streamlit dashboard jelenlegi tényleges oldala a Chat, Analitika, Audit és az új Feladatközpont. Az oldalsáv korábbi Emlékezet és Üzleti Infók elemei dekoratívak voltak; ezeket még külön funkcióként kell megépíteni, nem szabad kész menüként kommunikálni.
- A helyi titokkezelés a Streamlit secrets → környezeti változó sorrendet használja. A .gitignore kizárja a .env fájlokat és a .streamlit/secrets.toml fájlt; a titkok értékei nem kerültek lekérésre vagy megjelenítésre.
- A dashboard önmagában nem futtat háttérütemezést. A repóban a .github/workflows/email-automation.yml cron workflow a bejövő e-mail figyelést indíthatja, ha külön konfigurálva van; a kimenő email_sender lépés kifejezetten tiltott (if: false).
- Külön, általános célú JARVIS scheduler/worker folyamat jelenleg nincs. Következő infrastruktúra-funkció: önálló, idempotens worker belépési pont és ütemezési/claim protokoll, úgy hogy ne kapcsolja be az outbound emailt.


---

## 2026-11-26 – dokumentációs konszolidáció és aktuális funkcióleltár

Ez a szakasz a dokumentum korábbi, dátumozott állapot-pillanatképeit egészíti ki; az egymásnak ellentmondó régi CI/head állítások nem írhatók át jelen idejű státusszá. A legfrissebb igazságforrás a PR #26 aktuális headje és annak Checks oldala.

### Jelenlegi, PR #26 branchben implementált felhasználói funkciók

1. **Chat és adatkontextus:** magyar nyelvű Gemini chat; a kérdés témája szerint lead/task/log/analitika/memória kontextus.
2. **Céges leadkutatás:** explicit kutatási szándékra, forrásolt webes groundinggal; célpiac-váltás; legfeljebb 15 új cég kutatási futásonként.
3. **Cégazonosítás:** CSV import és globális kutatás közös tranzakciós cégazonosító RPC-t használ; normalizált cégnév/domain aliasok, párhuzamos írás elleni zár és email-jelöltek prioritása.
4. **Lead scoring és workflow:** forrásolt kutatásból pontozás és belső következőfeladat-ajánlás; gyenge bizonyíték további kutatást kér.
5. **Approval-gated task kezelés:** create/update/close műveletek strukturált chat-paranccsal; DB-ben kezelt egyszer használatos approval, operation ID, audit és replay-védelem; leadhez kötött task létrehozás.
6. **Feladatközpont:** read-only task lista, mutatók, szűrés és rendezés; külön consent-aware, read-only follow-up queue.
7. **Eredményalapú következő teendő:** lezárt outcome_measurement taskban rögzített pozitív/negatív/nincs válasz besorolásból belső következő lépést ajánl; ismeretlen eredménynél kézi besorolást kér.
8. **Hosszú távú memória:** explicit mentés, listázás, inaktiválás; üzleti preferencia/döntés/eredmény/tanulság kategóriák; érzékeny adat tiltása.
9. **Napi briefing és analitika:** meglévő rekordok read-only összesítése, vezetői és üzleti kontextus.
10. **Audit/hibakezelés:** strukturált műveleti audit, redakció, kritikus task műveleti útvonalon fail-closed.
11. **E-mail/inbox komponensek:** inbound monitor kódban és workflow-ban előkészített; outbound küldés hard-disabled.
12. **Auth/RBAC:** opcionális Supabase Auth login és admin/operator/reader permission kódja/migrációja előkészített, productionben nem aktív.

### Parancsdokumentáció

A felhasználói chat-parancsok, a mezők és a jóváhagyási folyamat külön dokumentumba kerültek: [JARVIS_COMMAND_GUIDE.md](JARVIS_COMMAND_GUIDE.md). Ez a parancslista a dashboard.py, task_actions.py, lead_workflow.py és jarvis_memory.py aktuális parser/routing logikáját követi. Nem támogatott vagy csak jövőbeli ötletként szereplő parancs nincs működőként feltüntetve.

### A funkciók biztonsági határai

- A feladatművelet előnézetet és külön jóváhagyást igényel; új kérés érvényteleníti a függő jóváhagyást.
- A follow-up queue nem küld e-mailt és nem módosít leadet.
- A workflow- és outcome-javaslat nem hoz létre taskot automatikusan.
- A leadkutatás nem ad kapcsolatfelvételi engedélyt.
- A kimenő e-mail küldés kódszinten tiltott; az outbound workflow lépés if: false.
- Production DB, Auth/RBAC, secret, deploy és merge nem változott e dokumentációs munkával.

### Háttérfolyamatok
A dashboard nem scheduler. A proactive_monitor_job.py és inbound email workflow belépési pontok léteznek, de általános célú, folyamatos JARVIS worker/scheduler production futása nincs igazolva. Az idempotens worker/claim protokoll későbbi fejlesztési munka.

### CI és ellenőrzés
A dokumentációs commitok a PR headet megváltoztatják. Ezért a korábbi, kódcommiton sikeres CI nem igazolja automatikusan a jelenlegi dokumentációs headet. A legfrissebb CI-t a [PR #26 Checks](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26/checks) oldalon, a pontos aktuális SHA-hoz kötve kell ellenőrizni.


## Phase 1 – cégkutatási dosszié első implementációja

A `feature/company-research-phase-1` ág a meglévő napi Google Search leadkutatást bővíti strukturált cégdossziéval. A kutatási prompt már kér kategorizált, forrás URL-lel ellátott üzleti tényeket és releváns, nyilvános szakmai döntéshozói kontextust. Az új `company_dossier.py` csak a Google grounding domainjeivel egyező forrásokat és engedélyezett üzleti kategóriákat fogadja el; a dosszié a meglévő lead `notes` mezőjébe kerül. Privát elérhetőség, érzékeny adat és kapcsolatfelvételi engedély nem gyűjthető/adható.

Ez a szelet a PR-ben még ellenőrzés alatt áll. A napi GitHub Actions workflow és a max. 15 cég/futás már korábban létezett; az új dossziémezők még nem jelentenek normalizált kutatási adatbázist, automatikus újrakutatási ütemezőt vagy productionben igazolt worker szolgáltatást. A következő technikai lépések: célzott unit/integrációs tesztek és CI; utána idempotens claim/lease, retry/dead-letter, frissességi szabályok és verziózott forrás/tény tárolás külön migrációtervezéssel.

## Hosszú távú termékvízió – kutatásvezérelt, személyre szabott SaaS

A részletes célarchitektúra: [JARVIS_AUTONOMOUS_SAAS_VISION.md](JARVIS_AUTONOMOUS_SAAS_VISION.md).

A JARVIS hosszú távú fő funkciója az legyen, hogy önállóan cégeket kutat, a cégről és releváns szakmai döntéshozóiról forrásolt dossziét épít, a feltárt üzleti problémák alapján egyedi SaaS-termékötleteket állít elő, majd ellenőrzi a korábbi elutasításokat, globális tiltásokat, meglévő ajánlatokat és ügyfélközi kizárólagosságot. Ezután személyre szabott ajánlati és e-mail-tervezetet készít. A pozitív érdeklődés még nem megrendelés: fejlesztési projekt csak tisztázott scope, írásos elfogadás/szerződés és külön belső jóváhagyás után indulhat.

**A célfolyamat új, még nem teljesen implementált elemei:**
- folyamatos automatikus cégfelderítés és idempotens háttérworker;
- részletes, forrás- és confidence-alapú cégdosszié, szakmai döntéshozó-kutatás;
- bizonyítékokkal alátámasztott üzleti problémahipotézisek;
- cégre szabott, több alternatívát összehasonlító SaaS-termékstratégia;
- globális és scope-specifikus „mit ne ajánljunk” napló;
- személyre szabott ajánlat- és e-mail-tervezet, küldés előtti jogi/consent/opt-out ellenőrzés;
- érdeklődés → igényfelmérés → ajánlat → szerződés → jóváhagyott fejlesztési projekt teljes pipeline;
- AI-támogatott fejlesztés, minőségbiztosítás és ügyféleredményből tanulás.

A meglévő leadkutatás, cégazonosítás, scoring, jóváhagyásos task workflow, memória és outcome-logika ennek az alapja, de nem szabad a teljes célfolyamatot már késznek tekinteni. A kimenő e-mail hard-disabled marad; a nyilvános e-mail-cím nem jelent automatikus marketingengedélyt. Személyes kutatás csak a szükséges, releváns szakmai kontextusra korlátozódhat; érzékeny magánadat nem gyűjthető. A termék-tiltó napló ajánlás előtti kötelező gate.