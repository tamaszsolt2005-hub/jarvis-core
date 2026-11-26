# JARVIS

Magyar nyelvű, Streamlit-alapú üzleti asszisztens, jelenleg helyi fejlesztés alatt.

**Központi dokumentáció:** [JARVIS Master Documentation](docs/JARVIS_MASTER_DOCUMENTATION.md)  
**Aktuális fejlesztési PR:** [#28 – company research dashboard and worker](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/28) – nyitott, nem merge-ölt.  
**Alap PR:** [#26 – readiness gates és termékvízió](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26) – nyitott, nem merge-ölt.

## Mi a JARVIS?

A JARVIS jelenlegi funkciói közé tartozik a magyar nyelvű Gemini chat, a nyilvános forrásokra támaszkodó leadkutatás, a lead scoring, a jóváhagyásos task-kezelés, az üzleti memória, a napi briefing, az analitika és az audit.

A hosszú távú cél egy kutatásvezérelt üzleti ügynök: minden cég valós helyzetét elemzi, egyedi SaaS-terméklehetőséget keres, figyelembe veszi a korábbi elutasításokat és tiltásokat, majd személyre szabott ajánlatot készít. A teljes autonóm pipeline még nincs megvalósítva.

## Jelenlegi cégkutatási fejlesztés

A `feature/company-research-phase-1` ág a következőket tartalmazza:
- grounding-alapú üzleti tények és nyilvános szakmai döntéshozói kontextus;
- forrás/domain ellenőrzés és kompakt cégdosszié;
- snapshot UUID, időbélyeg és SHA-256 tartalomlenyomat;
- append-only kutatási előzménytároló és repository migráció;
- fail-closed dosszié-frissességi szabály;
- read-only refresh candidate planner: stale dossziék kiválasztása, meg nem keresett cégek előresorolása, elutasítások és opt-out kizárása;
- kutatási frissítési jogosultsági policy: elutasítás/opt-out kizárása, két válasz nélküli follow-up utáni szüneteltetés, meg nem keresett leadek megtartása.

A snapshot tároló migrációja csak a feature branchben és a CI izolált adatbázisában szerepel. A refresh policy és a read-only candidate planner még nincs schedulerbe, DB-lekérdező folyamatba vagy workerbe kötve. A teljes SaaS-ötletmotor, globális termék-tiltó napló és automatikus outreach célfunkció, nem kész rendszer.

## Helyi indítás

```bash
python -m pip install -r requirements.txt
streamlit run dashboard.py --server.port 8501
```

Tesztelés:

```bash
python -m pip install -r requirements-test.txt
python -m compileall -q .
python -m pytest -q
```

## Dokumentumtérkép

| Dokumentum | Tartalom |
|---|---|
| [Master dokumentáció](docs/JARVIS_MASTER_DOCUMENTATION.md) | A projekt teljes, összevont áttekintése és az aktuális státusz |
| [Aktuális állapot](docs/CURRENT_STATE_AND_NEXT_STEPS.md) | Kész, folyamatban lévő és hátralévő munka |
| [Fejlesztési útiterv](docs/JARVIS_DEVELOPMENT_ROADMAP.md) | Fázisok, prioritások, elfogadási feltételek |
| [Architektúra](docs/JARVIS_DOCUMENTATION.md) | Modulok, adatfolyamok, adatbiztonság |
| [SaaS-vízió](docs/JARVIS_AUTONOMOUS_SAAS_VISION.md) | Cégkutatásból egyedi SaaS-ajánlat és fejlesztés |
| [Parancs kalauz](docs/JARVIS_COMMAND_GUIDE.md) | Ténylegesen támogatott chat-parancsok |
| [Fejlesztési backlog](docs/DEVELOPMENT_REVIEW_AND_RECOMMENDATIONS.md) | Technikai hiányok és következő feladatok |
| [Release gate-ek](docs/REMAINING_WORK_AND_RELEASE_GATES.md) | Production előtti kötelező ellenőrzések |
| [Production állapot](docs/PRODUCTION_STATE_AND_MIGRATION_PLAN.md) | Időbélyegzett, read-only production megfigyelések |
| [Főrendszer-készültségi felmérés](docs/JARVIS_MAIN_SYSTEM_READINESS.md) | Core funkciók, készre jelentési kritériumok, hátralévő P0/P1/P2 feladatok |
| [E-mail idempotencia](docs/EMAIL_PROVIDER_IDEMPOTENCY.md) | E-mail provider és retry-korlátok |

## Biztonsági és release szabályok

- A JARVIS alkalmazás nincs production hostra deployolva. A létező Supabase production projekt ettől különálló.
- A kimenő e-mail küldés kódszinten hard-disabled.
- A nyilvános e-mail-cím nem jelent automatikus marketingengedélyt.
- Production Supabase módosítás, migration futtatás, Auth/RBAC, secret, deploy és külső küldés külön, konkrét jóváhagyás nélkül tilos.
- PR merge külön jóváhagyást igényel.
- CI státuszt mindig az aktuális PR head SHA alapján kell ellenőrizni.
- A `.env*` és `.streamlit/secrets.toml` fájlok titkokat tartalmazhatnak; ezeket ne commitold és ne másold chatbe.


## README státuszfrissítés – 2026-11-26

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
