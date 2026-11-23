# JARVIS – teljes projekt- és műszaki dokumentáció

> **Felülvizsgálat:** 2026-11-23  
> **Vizsgált main commit:** `0b1afaf7e18e9a292e0ef3e38ac63953697edff6`  
> **Repository:** `tamaszsolt2005-hub/jarvis-core`

Ez az egyetlen részletes, ember által olvasható projekt-dokumentáció. A forráskód, a Supabase-migrációk és a GitHub Actions workflow-k az elsődleges technikai bizonyítékok. A dokumentum külön választja a kódban létező funkciót, a tesztelt működést és az éles környezetben ténylegesen igazolt állapotot.

## Tartalom

1. [Projektáttekintés](#1-projektáttekintés)
2. [Funkciók és állapotuk](#2-funkciók-és-állapotuk)
3. [Architektúra és modulok](#3-architektúra-és-modulok)
4. [Adatmodell és production Supabase](#4-adatmodell-és-production-supabase)
5. [Automatizmusok](#5-automatizmusok)
6. [Biztonság és jogosultságok](#6-biztonság-és-jogosultságok)
7. [Audit és hibakezelés](#7-audit-és-hibakezelés)
8. [Mentés és visszaállítás](#8-mentés-és-visszaállítás)
9. [Telepítés és konfiguráció](#9-telepítés-és-konfiguráció)
10. [Tesztelés és bizonyítékok](#10-tesztelés-és-bizonyítékok)
11. [Ismert hibák és blokkolók](#11-ismert-hibák-és-blokkolók)
12. [Fejlesztési sorrend](#12-fejlesztési-sorrend)

## 1. Projektáttekintés

A **JARVIS** magyar nyelvű, Streamlit-alapú, chat-központú B2B üzleti intelligencia-asszisztens. Természetes nyelvű kérdésekből üzleti szándékot azonosít, szükséges adatokat tölt be a Supabase-ből, majd Google Gemini modellel készít választ vagy irányít egy dedikált üzleti műveletet.

Célja a céges leadek kutatásának és értékelésének, az üzleti minták elemzésének, a feladatkezelésnek, a memóriának, a vezetői összefoglalóknak és a kontrollált e-mail-folyamatoknak az egy felületen történő támogatása.

| Terület | Technológia |
|---|---|
| Nyelv, runtime | Python 3.11 |
| UI | Streamlit |
| LLM | Google Gemini API |
| Adatbázis | Supabase / PostgreSQL |
| Automatizmusok, CI | GitHub Actions |
| Tesztek | pytest, pytest-cov, Streamlit AppTest, Playwright |

A `jarvis_common.py` alapértelmezett modellje `gemini-3.8-flash`; a `GEMINI_MODEL` felülírhatja. A régi `gemini-2.5-flash` és `gemini-2.5-pro` konfigurációk az alapértelmezett modellre esnek vissza.

### Állapotok értelmezése

- **Implementált:** kód vagy workflow megtalálható a vizsgált commitban.
- **Automatikusan tesztelt:** azonosítható CI-futtatás tesztelte.
- **Integrációsan igazolt:** valós szolgáltatással, kontrollált környezetben ellenőrizték.
- **Élesben igazolt:** valós éles folyamat sikeres futása megfigyelhető.
- **Részleges / blokkolt:** van implementáció, de az egész funkció vagy valamely függősége még nem aktív.
- **Tervezett:** nincs kész implementáció.

A kód jelenléte önmagában nem bizonyít külső integrációt vagy production működést.

## 2. Funkciók és állapotuk

| Funkció | Jelenlegi állapot | Korlát / megjegyzés |
|---|---|---|
| Magyar nyelvű chat, Gemini-válasz | Implementált | API-működés a titkoktól és külső szolgáltatástól függ. |
| Kontextusfüggő Supabase-adatlekérés | Implementált | Fő üzleti kliens service-role jogosultságú, nem user-RBAC. |
| Globális céges leadkutatás | Implementált, ütemezett | 2026-11-23-án auditmező-hiány miatt fail-closed módon leállt. |
| Weboldal-audit | Implementált | Nyilvános URL-ek, SSRF-védett HTTP; nem igazol vásárlási szándékot. |
| Lead scoring / prioritás | Implementált | Kutatási priorizálás, nem hozzájárulás vagy konverziós garancia. |
| Üzleti stratégiai összesítés | Implementált | A tárolt kutatási adatok minőségétől függ. |
| Explicit memória mentése/keresése/törlése | Implementált | Csak kifejezett felhasználói utasításra. |
| Üzleti tanulás | Implementált | Rögzített tapasztalatokból készít óvatos mintákat; nem állít ok-okozatot. |
| Jóváhagyásos feladatkezelés | Implementált | Előnézet és külön jóváhagyás szükséges. |
| Chat-analitika, vezetői riport | Implementált | A hiányzó napló nem automatikusan modulhiba. |
| Napi vezetői briefing | Ütemezett | Workflow-artifactot készít; e-mailes értesítés nem következik belőle. |
| Chatből e-mail-tervezet/küldési kísérlet | Implementált, kapuzott | SMTP-átvétel nem egyenlő a címzett postaládájába érkezéssel. |
| Háttér e-mail és utánkövetés | Kódban implementált, élesben nem igazolt | Hozzájárulás, válasz, leiratkozás és jóváhagyás kötelező. |
| IMAP válasz-/leiratkozás-figyelés | Kódban implementált | Valós IMAP-folyamat végponttól végpontig nem igazolt. |
| Proaktív lead-/feladatfigyelés | Napi workflow-val bekötve | Snapshotot ír; éles sikeres futása nem igazolt. |
| Rendszerdiagnosztika | Implementált | Táblákat, konfigurációt és auditmezőket ellenőriz. |
| Központi hibajelentés | Implementált | Minden külső kivételág éles működése nem igazolt. |
| Strukturált audit + admin auditoldal | Kódban implementált | A production logs-séma és policy-k hiánya miatt éles használat blokkolt. |
| Teljes admin/operator/reader RBAC | Nem aktív | Részleges Auth-alapok PR #13-ban, de nem merge-elt / nem aktivált. |
| Titkosított DB backup | Kódban és workflow-ban előkészítve | AWS/S3 konfiguráció és valós futás nem igazolt. |
| Sandbox restore-próba | Nem történt | Nincs jóváhagyott külön tesztprojekt; ilyet nem hoztunk létre. |

### Működési alapelvek

1. A leadkutatás nem jelent kapcsolatfelvételi vagy marketing-hozzájárulást.
2. A leadpontszám nem bizonyít fizetőképességet, vásárlási szándékot vagy várható ROI-t.
3. Módosító chatművelet csak előnézet és külön jóváhagyás után hajtható végre.
4. Memória csak explicit mentési vagy törlési utasításra módosul.
5. E-mail háttérküldéshez időbélyeges hozzájárulás és jóváhagyott kapcsolatfelvétel kell.
6. Bizonytalan SMTP-átvétel után nincs vak automatikus újraküldés.
7. Ha a kötelező `pending` audit nem menthető, az érzékeny művelet leáll.

## 3. Architektúra és modulok

### Adatfolyam

1. A felhasználó természetes nyelvű üzenetet küld a Streamlit chatben.
2. A dashboard felismeri a kutatási, memória-, feladat-, e-mail-, diagnosztikai vagy analitikai szándékot.
3. A megfelelő modul a Supabase-ből betölti a szükséges üzleti kontextust.
4. A Gemini megkapja a releváns kontextust és előállítja a választ.
5. A válasz megjelenik; a technikai események naplózhatók.
6. Módosító vagy külső hatású művelet csak a jóváhagyási kapun keresztül futhat.

A weboldalak, e-mailek és visszakeresett memóriák tartalma nem megbízható utasítás, hanem adat. A teljes felhasználói kérdést és Gemini-választ nem szabad automatikusan technikai naplóba írni.

### Fő rétegek

- **UI/vezérlés:** Streamlit dashboard és chat-router.
- **Közös szolgáltatás:** konfiguráció, Gemini- és Supabase-kliensek, naplózás, audit.
- **Üzleti modulok:** kutatás, web-audit, scoring, stratégia, memória, feladatok, analitika, e-mail.
- **Adatréteg:** Supabase/PostgreSQL.
- **Háttér:** GitHub Actions workflow-k.
- **Minőség:** pytest, AppTest, Playwright, SQL-tesztek.

### Fő fájlok

| Fájl | Felelősség |
|---|---|
| `dashboard.py` | Streamlit UI, chat-router, session, jóváhagyások, audit- és analitikafelület |
| `jarvis_common.py` | Közös config, Gemini/Supabase kliens, naplózás, audit |
| `jarvis_errors.py` | Központi hibajelentés, titokszűrés, logger fallback |
| `global_lead_research.py`, `global_lead_research_job.py` | Céges kutatás, piacválasztás, ütemezett job |
| `web_auditor.py`, `safe_http.py` | Biztonságos weboldal-lekérés és elemzés |
| `lead_scoring.py`, `intelligent_lead_scoring.py` | Leadprioritás |
| `business_strategy.py`, `business_learning.py` | Üzleti összesítés és explicit tapasztalatokból minták |
| `jarvis_memory.py` | Memória mentése, keresése, inaktiválása |
| `task_actions.py` | Feladatparancsok validálása és végrehajtása |
| `jarvis_analytics.py`, `daily_briefing.py` | Analitika, vezetői riport, napi briefing |
| `proactive_monitor.py`, `proactive_monitor_job.py` | Napi változás-pillanatkép |
| `health_check.py` | Konfiguráció, táblák, auditmezők diagnosztikája |
| `email_sender.py`, `email_inbox.py`, `chat_email.py`, `email_utils.py` | Küldés, inbox, chat e-mail-folyamat |
| `audit_admin.py` | Auth-alapú admin auditnézet, lapozás, export, integritás-ellenőrzés |
| `lead_gen.py`, `decision_support.py` | CSV leadimport, döntéstámogatási prompt |
| `scripts/supabase_backup.py` | Titkosított public-séma backup és sandbox restore |
| `infra/aws-backup-stack.yaml` | Előkészített AWS S3/KMS/OIDC infrastruktúra |

További régebbi vagy külön célú fájlok: `follow_up.py`, `inbox_monitor.py`, `reply_analyzer.py`, `inbox_analyzer.py`, `jarvis_status.py`, `stats.py`. Ezek pontos használatát kód- és teszthivatkozások alapján kell eldönteni. A dokumentációs összevonás Python-fájlokat nem töröl.
