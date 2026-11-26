# JARVIS – aktuális állapot és következő lépések

**Frissítve:** 2026-11-26  
**Aktív fejlesztési ág:** `feature/company-research-phase-1`  
**Aktuális PR:** [#27 – nyitott, nem merge-ölt](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/27)  
**Alap PR:** [#26 – nyitott, nem merge-ölt](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26)  
**Aktuális head és CI:** mindig a [PR #27 aktuális headjén és Checks oldalán](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/27/checks) ellenőrizendő. Csak az aktuális headhez tartozó, befejezett és sikeres futás tekinthető igazolásnak; régebbi futás nem.

A teljes összefüggő leírás: [JARVIS Master Documentation](JARVIS_MASTER_DOCUMENTATION.md).

## 1. Telepítési és környezeti állapot

- A JARVIS Streamlit alkalmazás helyi fejlesztés alatt áll.
- Nincs kiválasztott JARVIS production app-host vagy production alkalmazás URL.
- A létező Supabase production projekt különálló adatbázis; nem jelenti az alkalmazás deployját.
- A jelenlegi feature branch migrációi nem lettek production adatbázisra alkalmazva.
- A Railway `VolleyForm` projekt nem JARVIS.

## 2. Mi van már a kódban?

### Meglévő JARVIS-alapok
- Magyar nyelvű Gemini chat és üzleti kontextus.
- Explicit kérésre indított, grounding-alapú leadkutatás, legfeljebb 15 új cég/futás.
- Cégazonosítás és duplikációszűrés közös íróúttal.
- Lead scoring, kutatási bizonyosság és belső workflow-ajánlások.
- Task létrehozás/módosítás/lezárás jóváhagyásos útvonallal.
- Read-only task center és consent-aware follow-up queue.
- Outcome-alapú belső következő lépések.
- Üzleti memória, napi briefing, analitika és audit.
- Bejövő e-mail/inbox komponensek konfigurációtól függően; outbound küldés hard-disabled.

### PR #27 – cégkutatás első szelete
- Strukturált üzleti tények és nyilvános szakmai döntéshozói kontextus bekérése.
- `company_dossier.py`: forrás URL és grounding domain ellenőrzés, engedélyezett ténykategóriák, privát elérhetőségek kizárása.
- Dosszié snapshot metaadat: UUID, UTC időbélyeg, schema version és SHA-256 fingerprint.
- `company_research_store.py`: validált, append-only snapshot mentés és korlátozott történetlekérdezés.
- `company_research_snapshots` SQL migráció: RLS engedélyezés, anon/authenticated tiltás, service_role SELECT/INSERT.
- Fail-closed dosszié-frissességi szabály.
- `company_research_policy.py`: elutasítás/opt-out kizárása, két válasz nélküli utánkövetés után automatikus refresh szüneteltetése, meg nem keresett leadek megtartása.
- `company_research_refresh_planner.py`: read-only stale candidate kiválasztás, uncontacted prioritás, friss snapshot kihagyása, duplikációszűrés és limit.

## 3. Mi nincs még kész?

- A planner bekötése a DB-ből lapozva beolvasott leadekhez és legfrissebb snapshotokhoz.
- Automatikus cégkutatási scheduler és háttérworker.
- Claim/lease, heartbeat, retry limit, dead-letter és költség/rate limit a kutatási workerhez.
- A refresh policy bekötése a teljes CRM/outreach eseményállapotba.
- A két follow-up limit megbízható érvényesítése ténylegesen elküldött eseményekből.
- Kutatási előzmény és frissítési státusz UI.
- Bizonyítékokra épülő üzleti problémahipotézis motor.
- Egyedi SaaS-termékötlet-generálás és rangsorolás.
- Globális és cégenkénti „mit ne ajánljunk” napló.
- Személyre szabott ajánlati csomag és outbound compliance gate.
- Teljes értékesítési pipeline és szerződéses projektindítás.
- AI-assisted fejlesztési, tesztelési és átadási folyamat.

## 4. Kutatási frissítési szabály – tervezett viselkedés

| Cég állapota | Frissítési döntés |
|---|---|
| Még nem kerestük meg | Kutatható |
| 0–1 válasz nélküli follow-up | Kutatható |
| Legalább 2 válasz nélküli follow-up | Automatikus frissítés szünetel |
| Kifejezett elutasítás | Kizárva |
| Leiratkozás / do-not-contact | Kizárva |
| Érdeklődés / későbbi egyeztetés | Kutatható, felülvizsgálható |
| Nem besorolt bejövő válasz | Nem tekinthető válaszhiánynak |

A policy önmagában nem küld üzenetet, nem módosít lead státuszt, és nincs workerbe kötve. A kutathatóság nem jelent kapcsolatfelvételi engedélyt.

## 5. Következő fejlesztési sorrend

1. A jelenlegi PR #27 CI-jének befejeződése és minden hiba javítása az aktuális headen.
2. A dokumentált snapshot migráció és store kód további ellenőrzése.
3. A read-only planner bekötése lapozott lead- és snapshot-lekérdezéshez, majd tesztelés nagy adathalmazon.
4. Megbízható outreach eseményszámláló és állapotmapping a follow-up policy-hoz.
5. Idempotens, jóváhagyott ütemezésű kutatási worker.
6. Kutatási UI és emberi ellenőrzés.
7. Ezután üzleti problémahipotézis és SaaS-ötletmotor.

## 6. Változtatási és biztonsági határok

- PR #26 és #27 nem merge-ölhető külön explicit jóváhagyás nélkül.
- Production Supabase DDL/DML, migration, GRANT/REVOKE, Auth/RBAC, secret és infrastruktúra módosítása tilos külön engedély nélkül.
- Production deploy és outbound e-mail küldés nincs engedélyezve.
- CI zöld státusza csak az adott SHA-ra és az adott tesztkörnyezetre érvényes.


## 7. Új fejlesztési fókusz – 2026-11-26

A PR #28 a cégkutatási előzmények read-only dashboardját vezeti be. A navigációs routing hiányát a 2fa7b9410d5cbd49140391a633853ad73d81a1b9 commit javítja. Az új CI elindult; a javítás teljes CI-eredménye még nincs igazolva. A felület Auth esetén fail-closed, nem használ service-role megkerülést.

A következő munkacsomag a biztonságos háttérmotor. Első lépésként DB-től független job lifecycle modult készítünk stabil operation ID-val, lease/claim és heartbeat szabályokkal, véges retry-val, dead-letter állapottal és fake repository tesztekkel. Ezt követi a planner DB-adaptere és a scheduler. A scheduler nem aktiválható automatikusan; production DB, migráció, deploy és outbound e-mail változatlanul tiltott külön jóváhagyásig.

A felhasználó kérése szerint a kisebb módosítások után nem állunk meg külön ellenőrzési körre: több összefüggő funkció elkészülte után futtatunk átfogó ellenőrzést.
