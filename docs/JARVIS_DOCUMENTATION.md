# JARVIS – képességek és műszaki áttekintés

> **Aktuális állapot – 2026-11-26:** a JARVIS alkalmazás még nincs telepítve; helyi Streamlit dashboardból fejlesztjük. A PR #26 nyitott, nem merge-ölt; a cégazonosítás tranzakciós `upsert_company_lead` RPC-je és két-session concurrency tesztje elkészült. A production release kapuk nem blokkolják a helyi funkciófejlesztést. Az aktuális összefoglaló: [CURRENT_STATE_AND_NEXT_STEPS.md](CURRENT_STATE_AND_NEXT_STEPS.md).


**Történeti main-alap:** `main` – PR #20 squash merge: `2e2a97e182687c9b9d018da99b87095b75a21054` (2026-11-25). A jelenlegi fejlesztési változások a nyitott PR #26 branchben vannak; ez még nincs merge-ölve.
**Célközönség:** fejlesztők és AI-kódoló ügynökök. Ez a dokumentum a jelenlegi kódszerkezetet és a funkciók tényleges korlátait írja le.

## 1. Mi a JARVIS?

A JARVIS magyar nyelvű, Streamlit-alapú B2B üzleti asszisztens. A felhasználó chat- és dashboardfelületen keresztül kérhet kutatást, elemzést, feladatkezelést és üzleti összefoglalót. A rendszer Python modulokból, Supabase/PostgreSQL adattárolásból, Gemini-alapú nyelvi feldolgozásból és ütemezhető háttérfeladatokból áll.

## 2. Képességek és állapot

| Képesség | Mit csinál | Fontos korlát |
|---|---|---|
| Chat és válaszgenerálás | Magyar nyelvű chat, Gemini-alapú válaszok és dashboard műveletek | Külső Gemini eléréshez érvényes konfiguráció kell |
| Leadkutatás | Cégek keresése, webes források gyűjtése, weboldal-audit | A források minősége és a webelérés befolyásolja az eredményt |
| Leadértékelés | Lead scoring, prioritás és utánkövetési javaslat | Üzleti döntést támogató becslés, nem garantált eredmény |
| Üzleti memória | Explicit üzleti információk tárolása és későbbi felhasználása | Nem korlátlan vagy automatikusan teljes tudásbázis |
| Stratégia és döntéstámogatás | Üzleti tanulságok, stratégiai összefoglalók, analitika | A kimenet a rendelkezésre álló adatok minőségétől függ |
| Feladatkezelés | Task létrehozás, módosítás, lezárás és DB-szintű jóváhagyásos végrehajtás | Az approval consume és task+audit+operation RPC atomikus; az összes update/close és külső mellékhatás teljes idempotenciája még nem bizonyított |
| Audit és hibakezelés | Műveleti napló, auditállapotok, hibák redakciója | A hash chain nem WORM, és nem véd adatbázis-tulajdonossal szemben |
| Napi briefing és utánkövetés | Vezetői összefoglaló, lejárt feladatok, follow-up jelzések és leadhez kötött belső következőlépés-javaslatok | A javaslat read-only; a task tényleges létrehozása külön jóváhagyott művelet, a follow-up küldés tiltott |
| Proaktív monitor | Lead- és feladatváltozások figyelése, állapotfrissítés | A monitor kód megléte nem bizonyítja, hogy production scheduler fut |
| E-mail | Tervezetkészítés, inbox feldolgozás és SMTP adapter | A kimenő SMTP-küldés biztonsági kapcsolóval tiltott; tartós provider-idempotencia nincs igazolva |
| Auth/RBAC | Opcionális Supabase Auth login és shared-workspace admin/operator/reader jogosultság | Kódban és migrációkban előkészített; production flag OFF, migráció nem alkalmazott |

**Státuszszabály:** a „kódban implementált”, „tesztelt”, „külső integrációval élőben igazolt” és „productionben aktív” négy külön állítás. Mindig nevezd meg, melyikről van szó.

## 3. Fő modulok

| Fájl | Felelősség |
|---|---|
| `dashboard.py` | Streamlit UI, chat, dashboard folyamatok és felhasználói belépési pontok |
| `jarvis_common.py` | Közös konfiguráció, Supabase kliensgyárak és segédfüggvények |
| `jarvis_auth.py` | Supabase Auth session-ellenőrzés, role claim és user-JWT kliens |
| `global_lead_research.py`, `web_auditor.py` | Leadkutatás és weboldal-vizsgálat |
| `lead_scoring.py`, `intelligent_lead_scoring.py` | Leadpontozás |
| `lead_workflow.py` | Kutatási bizonyítékokból belső következő feladat javaslata, duplikációszűréssel; csak read-only |
| `business_learning.py`, `business_strategy.py`, `decision_support.py` | Üzleti tanulás, stratégia és döntéstámogatás |
| `jarvis_memory.py`, `jarvis_analytics.py`, `stats.py` | Memória, analitika és statisztika |
| `task_actions.py` | Feladatműveletek és műveleti szabályok |
| `audit_admin.py` | Audit-admin funkciók |
| `daily_briefing.py`, `follow_up.py` | Vezetői briefing és utánkövetés |
| `proactive_monitor.py`, `proactive_monitor_job.py` | Proaktív figyelés és háttérjob |
| `email_sender.py`, `chat_email.py`, `email_inbox.py`, `inbox_monitor.py` | E-mail küldési, chat és inbox folyamatok |
| `safe_http.py`, `jarvis_errors.py` | HTTP biztonsági segédek és központi hibakezelés |
| `scripts/supabase_backup.py` | Supabase logikai backup/restore segédprogram |
| `supabase/migrations/` | Verziókezelt SQL migrációk |
| `supabase/tests/` | SQL/pgTAP biztonsági és sémapostcondition tesztek |

## 4. Adat- és jogosultsági modell

- A JARVIS jelenlegi célmodellje egyetlen közös workspace; nem tenant-izolált SaaS.
- Az Auth/RBAC szerepek: `admin`, `operator`, `reader`.
- A szerepkör megbízható forrása a szerver által kezelt Supabase `app_metadata.role`; a kliens által írható user metadata nem jogosultsági forrás.
- Auth módban a dashboard user JWT-t és publikus kulcsot használ, service-role fallback nélkül.
- A háttérfolyamatok külön, szerveroldali service-role hozzáférést használnak.
- Az Auth login szerveroldali kapcsolója: `JARVIS_SUPABASE_AUTH_LOGIN_ENABLED`; alapértelmezésben OFF.
- A shared-workspace RLS/GRANT SQL verziókezelt, de productionben még nem alkalmazott. Részletek: [production állapot](PRODUCTION_STATE_AND_MIGRATION_PLAN.md).

## 5. Működési és biztonsági invariánsok

1. Feladat végrehajtása csak explicit jóváhagyással történhet.
2. Kritikus művelet előtt auditbejegyzés készül; auditírási hiba esetén az érintett fail-closed útvonal álljon le.
3. Ne tekints egy UI-sessionben tárolt approvalt több processz között atomikus one-use tokennek.
4. Ismeretlen SMTP-kimenetel után az automatikus retry duplikált e-mailt okozhat; ne állítsd, hogy a küldés idempotens.
5. Külső HTTP-kéréseknél a közös biztonságos kliens- és validációs szabályokat használd.
6. Titkot, access tokent, teljes e-mail tartalmat vagy érzékeny személyes adatot ne írj auditba vagy logba.
7. Ne kapcsold be productionben az Auth/RBAC-ot, amíg a migration drift és az éles tesztelés nincs rendezve.

## 6. Fejlesztés és tesztelés

**Aktuális ellenőrzés (2026-11-25):** main commit `2e2a97e`; main CI `45655131500` sikeres. A production backup workflow `45655512387` sikeresen végrehajtotta a titkosított dumpot, S3 SSE-KMS ellenőrzést, letöltés/visszafejtés/hash ellenőrzést és külön PostgreSQL 17 restore-t. Ez nem jelent production migrációt vagy deployt. [Backup/restore futás](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45655512387).



```bash
python -m pip install -r requirements-test.txt
python -m compileall -q .
python -m pytest -q
```

A CI PostgreSQL 17 izolált környezetben migrációs replayt, pgTAP teszteket, katalógus-postcondition ellenőrzést és titkosított backup/restore integrációt is futtat. A sikeres fixture-teszt nem bizonyítja a production Supabase Auth/JWT/RLS viselkedést.

## 7. Következő fejlesztési irány

A jelenlegi szakaszban a helyi funkciófejlesztés folytatható. A task approval/idempotencia és a cégazonosítás tranzakciós alapjai a PR #26 branchben CI-vel igazoltak. Továbbra is nyitott a külső e-mail provider live E2E (a küldés hard-disabled marad), a teljes üzleti workflow E2E és mérés, valamint a forrásolt/jogosultságkezelt memória lifecycle. A migration drift, Auth/RLS smoke és app-host kiválasztás későbbi production release feladat, nem a helyi funkciófejlesztés előfeltétele.

A leadkutatásból a napi briefing már képes bizonyíték-alapú belső következőlépés-javaslatot készíteni a `lead_workflow.py` segítségével. Ez read-only: a javaslat nem hoz létre taskot, nem módosít leadet és nem engedélyez kapcsolatfelvételt. A következő fejlesztési lépés a leadhez kötött task jóváhagyásos létrehozása, majd a follow-up és eredménymérés összekapcsolása. A részletes, aktuális teendőket a [fejlesztési backlog](DEVELOPMENT_REVIEW_AND_RECOMMENDATIONS.md) és a [release gate-ek](REMAINING_WORK_AND_RELEASE_GATES.md) tartalmazzák.


## Aktuális implementációs állapot – PR #26, 2026-11-25

A dokumentum korábbi main/PR #20 hivatkozásai történeti állapotot rögzítenek; az aktuális státuszt a fenti összefoglaló és a [PR #26](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26) tartalmazza. A jelenlegi fejlesztési változásokat a [PR #26](https://github.com/tamaszsolt2005-hub/jarvis-core/pull/26) tartalmazza; aktuális PR-head `a PR oldalon látható aktuális head`; a kód- és tesztváltozások CI-vel igazolt commitja `38693f2f93b790608aef37a33f190a86e611ff0d`. A PR nincs merge-ölve.

- **Approval:** a DB tárolja a token hashét, a principal/payload kötést és lejáratot; az egyszeri fogyasztás a végrehajtó tranzakció része. A replay/revoke SQL-tesztek hozzáadva.
- **Task műveletek:** az `execute_approved_task_action` RPC operation ID alapján sorosítja az azonos műveletet; a már lezárt művelet eredményét adja vissza. A párhuzamos kettős végrehajtás ellenőrzésére két-session CI teszt van.
- **Audit:** a kritikus task művelet auditírási hibájára rollback-teszt került be, amely ellenőrzi a task, operation ledger és approval állapotát is.
- **SMTP:** `EMAIL_DELIVERY_ENABLED = False` marad. A DATA-küldés utáni bizonytalan eredmény `EmailDeliveryOutcomeUnknown` / `send_unknown`; automatikus retry tiltott. A csatlakozási/auth/preflight hiba ismert, nem-kézbesített hibaként kezelendő. Belső stabil operation ID a Resend adapterben Idempotency-Key fejlécben továbbítódik; SMTP-nél nincs provider-oldali deduplikáció.
- **Service role:** a végső közvetlen task DML revoke migráció csak az RPC write path deployja és élő smoke-ja után alkalmazható. A CI fixture-ben való lefutása nem jogosít production módosításra.

A `38693f2` kódcommiton a `45689264377` mindkét CI jobja sikeres; a párhuzamos `45689247826` futás megszakadt. A dokumentációs commitok utáni PR-head (`eaad542`) külön CI-je még nem zárult le sikeresen. Production Auth/RLS, migration, deploy és provider integráció nincs igazolva.


## Resend provider adapter – 2026-11-25

A Resend HTTPS API adapter elkészült. A stabil lead + sequence operation ID az API Idempotency-Key fejlécébe kerül; a legacy follow_up.py útvonal is ugyanazt a kulcsot használja. A workflow EMAIL_PROVIDER=resend és RESEND_API_KEY secret bindinggal elő van készítve. A globális EMAIL_DELIVERY_ENABLED=False és az outbound workflow if: false változatlan, tehát a provider nem küldhet levelet.

A Resend 24 órán át őrzi az idempotenciakulcsot. A hálózati hiba, 409, 429 és 5xx bizonytalan eredmény; automatikus retry nincs. A send_unknown / followup_unknown állapotot tilos automatikusan visszaállítani küldhető állapotba. Live API-kulcs, ellenőrzött feladói domain és provider E2E még nincs igazolva. Részletek: [Email provider idempotency](EMAIL_PROVIDER_IDEMPOTENCY.md).



## 2026-11-26 – PR #26 frissített implementációs és ellenőrzési állapot

A korábbi, PR #20/21/23 és régebbi PR #26 CI-headre hivatkozó bekezdések történeti pillanatképek. Az ellenőrzött PR #26 head `6ef4020bba3949e02440e97583fc907b6bcb1f00` CI-eredménye:

- Python/AppTest/browser: **838 passed, 3 skipped, 0 failed**, 91.29% coverage.
- PostgreSQL 17 izolált migrációs, pgTAP, audit/RBAC catalog, encrypted backup/restore: sikeres.
- CodeQL: sikeres.
- pip-audit: sikeres.

A korábban alkalmazásszintű global lead research deduplikációt a PR #26 közös, tranzakciós `upsert_company_lead` RPC-je váltotta fel. Mindkét lead writer ugyanazt a protokollt használja; a PostgreSQL két-session concurrency teszt sikeres. A cégclaim race fejlesztési kockázat lezárt a branchben; production migráció még nem történt.

A CSV import normalizált email unique indexe ettől külön védelmi réteg. Az email-egyediség migráció izolált PostgreSQL CI-ben tesztelt, de production alkalmazása nem történt.

**Production állapot:** a PR #26 továbbra is nyitott és nem merge-ölt. A CI nem bizonyítja a production Supabase séma/Auth/RLS állapotát, az alkalmazás hostját, az SMTP hitelesítést vagy a deployt. A kimenő e-mail hard-disabled. Production DB, deploy, jogosultságok, secret-ek és e-mailküldés változatlan.
