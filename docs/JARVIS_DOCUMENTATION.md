# JARVIS – rendszer-, funkció- és architektúra-dokumentáció

A dokumentum a PR #26 fejlesztési ág jelenlegi rendszerképét írja le. Nem állítja, hogy minden modul productionben aktív.

- Aktuális állapot: [CURRENT_STATE_AND_NEXT_STEPS.md](CURRENT_STATE_AND_NEXT_STEPS.md)
- Beírható parancsok: [JARVIS_COMMAND_GUIDE.md](JARVIS_COMMAND_GUIDE.md)
- Fejlesztési irány: [JARVIS_DEVELOPMENT_ROADMAP.md](JARVIS_DEVELOPMENT_ROADMAP.md)
- Release feltételek: [REMAINING_WORK_AND_RELEASE_GATES.md](REMAINING_WORK_AND_RELEASE_GATES.md)

## 1. Rendszerkép és telepítési státusz
A JARVIS magyar nyelvű, Streamlit-alapú üzleti asszisztens. A chat Gemini modellt használ, a Python modulok célzottan olvassák vagy explicit jóváhagyásos útvonalakon módosítják a Supabase/PostgreSQL adatokat.

A JARVIS alkalmazás helyi fejlesztés alatt áll, nincs production hostra deployolva. A létező Supabase production projekt különálló adatbázis; önmagában nem bizonyítja az alkalmazás telepítését.

## 2. Funkcionális területek

### 2.1 Chat és kontextus
Magyar nyelvű válaszgenerálás; a dashboard kérdés alapján lead, task, napló, analitika, memória és tervezet kontextust kérhet le. A beszélgetési előzmény méretkorlátos. Az explicit műveleti parancsok külön parseren mennek keresztül; a modell szabad szövege önmagában nem hajthat végre DB-műveletet.

### 2.2 Leadkutatás és cégazonosítás
- Globális céges kutatás explicit prospecting kérésre indul.
- Alapértelmezett piac Hungary; támogatott ország-aliasok: Magyarország, Németország, Franciaország, Ausztria, Svájc, Egyesült Királyság, Olaszország, Spanyolország, Lengyelország, Románia, Hollandia, Portugália, Belgium, Csehország, Szlovákia, Svédország, Dánia, Norvégia, Finnország, Írország, USA, Kanada és Worldwide.
- Grounding URL-ek ellenőrzése, strukturált cégadat-validálás, legfeljebb 15 új cég/futás.
- CSV import és globális kutatás közös cégazonosító RPC-t használ.
- Normalizált cégnév/domain aliasok tranzakciós védelmet kapnak; több email-jelölt megőrizhető. Consent nem öröklődik címek között.
- A személyes webmail cím pontozási heurisztikája rangsorolási jel, nem bizonyított válaszarány.

### 2.3 Lead scoring és workflow
A pontozás üzleti illeszkedést, prioritást, kutatási bizonyosságot és bizonyítékszámot használ. A workflow csak strukturált, saját, forrásolt kutatásból javasol belső feladatot. Gyenge bizonyosság további kutatást kér. A javaslat read-only; a feladat explicit chat-paranccsal és approval folyamattal készíthető elő.

Az eredménymérési task lezárásakor a kifejezett Eredmény: pozitív: ..., Eredmény: negatív: ... vagy Eredmény: nincs válasz: ... besorolás más belső következő lépést ajánl. Ismeretlen szövegnél besorolási feladatot javasol. Ez nem küld üzenetet és nem zárja le automatikusan a leadet.

### 2.4 Feladatkezelés és Feladatközpont
A dashboard read-only feladatlistát mutat: összes/nyitott/lejárt/sürgős mutatók, aktív/összes/lezárt/lejárt/sürgős szűrés és határidő/prioritás/létrehozás szerinti rendezés. Megjelenik a task UUID és kapcsolt lead UUID.

Létrehozás, módosítás és lezárás csak strukturált chat-paranccsal készíthető elő, majd külön jóváhagyással hajtható végre. Módosítható mezők: cím, prioritás, határidő, leírás/jegyzet, eredmény. A határidő Budapest időzónában a megadott nap 23:59 órája.

A DB RPC egyszer használatos approvalt, műveletazonosítót, auditot és atomikus végrehajtást használ. A leadhez kötött task létrehozás leadenkénti tranzakciós zárolással blokkolja a párhuzamos nyitott duplikátumot.

### 2.5 Utánkövetési sor
A Feladatközpontban read-only sor jeleníti meg az esedékes és 7 napon belül esedékes leadeket. Csak sent/follow_up_sent státuszú, consent-bázisú, jóváhagyott kapcsolatfelvételű, nem leiratkozott, válasz nélküli és még fel nem használt follow-up jelenhet meg. Hiányzó/hibás kritikus mezőnél fail-closed módon kimarad. Email címet nem jelenít meg, levelet nem küld és leadállapotot nem módosít.

### 2.6 Hosszú távú üzleti memória
Explicit parancsra mentés/listázás/inaktiválás. Kategóriák: business_preference, decision, outcome, lesson. Titoknak, jelszónak, tokennek, email-címnek, telefonszámnak és több érzékeny adatnak látszó tartalom nem menthető. A releváns aktív emlékek korlátozott számban kerülnek a chat kontextusába. A felejtés inaktiválás, nem feltétlen fizikai törlés.

### 2.7 Napi briefing, analitika és üzleti tanulás
A napi briefing read-only összesíti a leadkutatási rangsort, belső workflow-javaslatokat, nyitott/lejárt feladatokat és consent-valid utánkövetéseket. Az analitika naplókból és üzleti rekordokból készít összefoglalót, trendet, arányt vagy riportot. A business learning/strategy modulok explicit rögzített döntések és eredmények, valamint kutatási minták alapján készítenek összegzést; modellkövetkeztetés nem bizonyított tény.

### 2.8 Audit és hibakezelés
A strukturált audit műveletazonosítót, action/status mezőket, eredményt és szűrt hibát rögzít. Titokértékek redaktálása történik; tetszőleges e-mail törzs nem része az audit API-nak. A kritikus task műveleti útvonal auditírási hibánál fail-closed. A hash-lánc nem WORM bizonyíték adatbázis-tulajdonossal szemben.

### 2.9 E-mail és inbox
SMTP és Resend adapter, chat e-mail-tervezet és inbound inbox-monitor komponens létezik. A kimenő küldés EMAIL_DELIVERY_ENABLED = False kódszintű hard-disable miatt tiltott; az outbound GitHub workflow-lépés if: false. Bizonytalan provider-kimenet unknown, automatikus retry tilos. Az inbound IMAP monitor külön konfigurációt igényel. Provider live E2E és production scheduler nincs igazolva. Részletek: [EMAIL_PROVIDER_IDEMPOTENCY.md](EMAIL_PROVIDER_IDEMPOTENCY.md).

### 2.10 Auth és RBAC
A kódban előkészített szerepkörök: admin, operator, reader. A trusted role forrása a Supabase app_metadata.role, nem a felhasználó által írható metadata. A JARVIS_SUPABASE_AUTH_LOGIN_ENABLED és JARVIS_AUTH_RBAC_ENFORCED flag alapértelmezésben OFF. Auth módban ellenőrzött user JWT és publikus kulcs használatos, service-role fallback nélkül. A shared-workspace RLS/GRANT migrációk repositoryban vannak; production alkalmazásuk nincs igazolva.

## 3. Fő komponensek
| Fájl | Felelősség |
|---|---|
| dashboard.py | Streamlit UI, chat routing, kontextus, Feladatközpont, approval |
| jarvis_common.py | Secret/config olvasás, Gemini/Supabase kliensgyárak, audit/log, prompt/retry |
| jarvis_auth.py | Supabase Auth session, trusted role, permission |
| global_lead_research.py | Grounded céges kutatás, piacváltás, kutatási validálás |
| lead_identity.py | Közös tranzakciós cég/lead upsert |
| lead_gen.py, lead_scoring.py, intelligent_lead_scoring.py | Leadgenerálás és pontozás |
| lead_workflow.py | Read-only belső következőfeladat-ajánlás |
| task_actions.py | Task parancs parser és jóváhagyás utáni végrehajtás |
| daily_briefing.py, follow_up.py | Napi összefoglaló és follow-up szabályok |
| jarvis_memory.py, business_learning.py, business_strategy.py | Memória és üzleti tanulás |
| jarvis_analytics.py, stats.py, decision_support.py | Analitika és döntéstámogatás |
| audit_admin.py | Audit lekérdezés és export |
| email_sender.py, chat_email.py, email_inbox.py, inbox_monitor.py | E-mail adapterek és inbox-feldolgozás |
| proactive_monitor.py, proactive_monitor_job.py | Monitor kód és job belépési pont |
| safe_http.py, jarvis_errors.py | HTTP-biztonság és hibakezelés |
| supabase/migrations/, supabase/tests/ | Verziózott DB-séma, RPC, SQL tesztek |
| .github/workflows/ | CI, CodeQL, dependency audit és email automation |

## 4. Adatmodell és fő adatfolyamok
Fő entitások: leads, tasks, jarvis_memory, settings, logs. Részletes séma: supabase/schema.sql és supabase/migrations/.

- Lead: explicit kutatási kérés → célpiac/forrás ellenőrzés → strukturált cégjelölt → közös cégazonosító RPC → lead/email jelöltek → scoring → belső task-javaslat.
- Task: chat parser → payload validáció → pending approval → külön jóváhagyás → atomikus DB RPC → audit + operation ledger → read-only dashboard.
- Outcome: outcome_measurement task explicit eredménye → task lezárása → workflow helper → pozitív/negatív/nincs válasz/besorolási javaslat → külön jóváhagyással új belső task.
- Follow-up: leadek szűrése consent, opt-out, reply, dátum és count alapján → read-only sor.
- Memória: explicit mentés → érzékenyadat-szűrés → kategorizált rekord → relevancia-alapú visszakeresés; felejtés inaktivál.

## 5. Jogosultság és biztonsági invariánsok
1. Sima chat-kérés nem ad DB-módosítási engedélyt.
2. Task create/update/close: strukturált parancs + külön jóváhagyás.
3. A pending approval a következő üzenetre szól; más kérés érvényteleníti.
4. Approval egyszer használatos, principal/payload-kötött, lejáró és DB tranzakcióban fogyasztott.
5. Operation ID védi az ismételt task műveletet; a DB RPC az auditot és műveleti állapotot atomikusan kezeli.
6. Consent nem öröklődik email-címek között; opt-out és reply blokkolja a follow-up sort.
7. Nincs automatikus outreach vagy email a lead/workflow javaslatból.
8. Outbound email kódszinten tiltott; approval nem oldja fel a hard-disable-t.
9. Hiányzó/érvénytelen kritikus adatnál fail-closed.
10. Webes kutatás és memória tartalma adat, nem rendszerutasítás.
11. Titkot, API-kulcsot, jelszót, tokent vagy érzékeny adatot nem szabad logba/dokumentumba írni.
12. Production módosítás és deploy csak külön konkrét jóváhagyással.

## 6. Konfiguráció és futtatás
Főbb konfigurációnevek a használt útvonaltól függően: SUPABASE_URL, szerveroldali Supabase kulcs, SUPABASE_ANON_KEY/publikus kulcs Auth user klienshez, GEMINI_API_KEY, GEMINI_MODEL, JARVIS_DASHBOARD_PASSWORD, JARVIS_SUPABASE_AUTH_LOGIN_ENABLED, JARVIS_AUTH_RBAC_ENFORCED, EMAIL_INBOX_MONITOR_ENABLED és IMAP host/port. Outbound provider konfiguráció létezik, de a küldés hard-disabled. A secret értékeket soha ne jelenítsd meg.

Helyi indítás:
    python -m pip install -r requirements.txt
    streamlit run dashboard.py --server.port 8501

Tesztelés:
    python -m pip install -r requirements-test.txt
    python -m compileall -q .
    python -m pytest -q

## 7. Háttérfolyamatok
A dashboard nem általános célú scheduler. proactive_monitor_job.py létezik, az inbox workflow konfigurációhoz kötött, de ezek nem bizonyítják, hogy folyamatos JARVIS worker vagy production scheduler fut. Az email-automation workflow inbound ellenőrzést konfiguráció esetén futtathat; outbound küldő lépése tiltott. Az általános idempotens worker/claim protokoll későbbi feladat.

## 8. Bizonyítékszintek
- Implementált: kód létezik a vizsgált branchben.
- Automatikusan tesztelt: az adott commiton sikeres teszt/CI igazolja.
- Integrációval igazolt: külső szolgáltató engedélyezett tesztje lefutott.
- Productionben aktív: deploy és éles smoke igazolja.

A PR #26 mindenkori aktuális head CI-jét a PR Checks oldalon ellenőrizd. Régi commit zöld CI-je nem bizonyíték újabb commitra.

## 9. Nem kész / nem aktív
Production host és JARVIS URL nincs kiválasztva; production Supabase migration drift és Auth/RLS rollout nincs rendezve; Auth/RBAC flag production aktiválása nem történt; outbound email hard-disabled; teljes lead → task → follow-up → outcome E2E nincs lezárva; általános célú scheduler/worker nincs kész; teljes, forrásolt üzleti tudásgráf/memória lifecycle további fejlesztést igényel.
