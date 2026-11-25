# JARVIS – képességek és műszaki áttekintés

**Aktuális alap:** `main` – PR #20 squash merge: `2e2a97e182687c9b9d018da99b87095b75a21054` (2026-11-25).
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
| Napi briefing és utánkövetés | Vezetői összefoglaló, lejárt feladatok és follow-up jelzések | A tényleges futtatás ütemező- és környezetfüggő |
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

A következő legfontosabb lépés nem újabb funkció, hanem megbízható működés: task approval race és idempotencia, külső szolgáltatások hibatűrése, e-mail-küldés biztonsága, migration drift rendezése, Auth/RLS izolált élő validációja, majd production release csak külön engedélyezett terv alapján.

A részletes, aktuális teendőket a [fejlesztési backlog](DEVELOPMENT_REVIEW_AND_RECOMMENDATIONS.md) és a [release gate-ek](REMAINING_WORK_AND_RELEASE_GATES.md) tartalmazzák.
