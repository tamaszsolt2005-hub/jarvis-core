# Supabase klienshozzáférési leltár

**Vizsgált ref:** `feat/supabase-auth-rbac-foundation` – `f8977ecb25bde27702d732afe0d50b6bdb3f4e9f`  
**Állapot:** csak kód- és híváshely-leltár; sem production DB, sem Auth-felhasználó, sem migráció nem módosult.

## Összefoglaló

A vizsgált Python-forrásokban 17 közvetlen `get_supabase()` hívás található 12 hívómodulban. A kliensgyár a `jarvis_common.py` fájlban található, és jelenleg a `SUPABASE_SERVICE_ROLE_KEY` kulcsot használja (régi `SUPABASE_KEY` fallbackkel). Ez a kulcs RLS-t megkerülő, privilegizált hozzáférést ad, ezért a jelenlegi hívások nem tekinthetők felhasználói JWT-alapú hozzáférésnek.

## Híváshelyek és besorolás

| Modul | Közvetlen hívás | Folyamat / hozzáférési osztály | Megjegyzés |
|---|---:|---|---|
| `dashboard.py` | 5 | Interaktív dashboard – átmeneti legacy | Audit események, analitika és chat műveletek; jelenleg service-role klienssel. |
| `health_check.py` | 1 | Vegyes diagnosztika – átmeneti legacy | Dashboardból is elérhető diagnosztika, ezért nem sorolható tisztán háttérfolyamatnak. |
| `daily_briefing.py` | 1 | CLI/háttérfeladat | A `main()` belépési pontban épít napi jelentést. |
| `email_inbox.py` | 1 | Háttérfolyamat | IMAP inbox feldolgozás és adatbázis-műveletek. |
| `email_sender.py` | 1 | Háttérfolyamat | Ütemezett, engedélyezési kapcsolókkal védett e-mail feldolgozás/küldés. |
| `follow_up.py` | 1 | Háttérfolyamat | Automatikus utánkövetés. |
| `global_lead_research_job.py` | 1 | Háttérfolyamat | Ütemezett globális leadkutatás és audit. |
| `inbox_monitor.py` | 1 | Háttérfolyamat | Bejövő válaszok figyelése és feldolgozása. |
| `lead_gen.py` | 1 | CLI/háttérfeladat | Átnézett lead CSV importálása és auditja. |
| `proactive_monitor_job.py` | 1 | Háttérfolyamat | Ütemezett proaktív monitor. |
| `jarvis_status.py` | 1 | CLI/operációs diagnosztika | Lead státuszok lekérdezése. |
| `stats.py` | 1 | CLI/operációs diagnosztika | Összesített státusz- és naplólekérdezés. |

## Célzott klienshatárok

1. **Felhasználói kliens:** kizárólag a bejelentkezett személy Supabase Auth JWT-jével, publikus/publishable kulccsal; a DB-oldali RLS-policy-k érvényesülnek. Ezt a dashboard jelenleg még nem használhatja üzleti műveletekre, mert nincs teljes Auth-bevezetés és táblánkénti RLS.
2. **Háttérfolyamat-kliens:** explicit nevű service-role kliens, csak nem felhasználói, szerveroldali jobok számára. A service-role kulcs nem kerülhet Streamlit sessionbe, UI callbackbe vagy böngészőbe.
3. **Átmeneti dashboard kliens:** a régi közös jelszavas dashboard jelenleg privilegizált klienssel működik. Ezt külön, átmeneti és kifejezetten nem-RBAC klienshatárként kell megnevezni; a név szerinti elkülönítés önmagában nem teszi biztonságossá. Csak akkor váltható user JWT-re, ha a felhasználók, a szerepkörök, a szükséges GRANT-ok és az RLS-policy-k készen állnak.
4. **Diagnosztika:** a `health_check.py` egyszerre dashboardról hívható és CLI/üzemeltetési ellenőrzés; a felhasználói UI útvonalat és a háttér/üzemeltetési útvonalat később szét kell választani.

## Biztonságos átállási sorrend

- A jelenlegi hívásleltár és a CI baseline rögzítése.
- Kliensgyárak név szerinti szétválasztása, majd az összes hívó explicit besorolása; a régi `get_supabase()` név fokozatos kivezetése.
- A dashboard legacy kliensének elkülönítése úgy, hogy a régi belépés és az üzleti funkciók ne sérüljenek.
- A háttérjobok service-role kliensének explicit megtartása, a szükséges minimális felület dokumentálásával.
- Auth felhasználók és admin által kezelt szerepkörök előkészítése.
- Production migration history és tényleges séma drift rendezése az eredeti SQL-források helyreállítása után.
- Táblánkénti RLS és GRANT tervezés, majd csak engedélyezett, verziókezelt migrációval történő alkalmazás.
- Valós Auth/JWT/RLS integrációs teszt csak létező, engedélyezett izolált környezetben. Új Supabase tesztprojekt vagy branch nem készül.

## Korlátok

- Ez a leltár nem állítja, hogy a felhasználói kliens vagy RLS már aktív.
- A service-role hozzáférés átnevezése nem helyettesíti a jogosultsági modellt.
- Nem történt production DB-írás, Auth-user létrehozás, RLS-policy alkalmazás vagy kézi SQL.
- A #11, #12 és #13 PR nincs merge-elve.
