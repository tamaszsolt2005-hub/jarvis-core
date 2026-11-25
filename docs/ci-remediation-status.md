# CI és üzemeltetési javítási napló

**Frissítve:** 2026-11-25  
**Repository:** tamaszsolt2005-hub/jarvis-core

Ez a dokumentum a 2026-11-25-i backup- és CI-ellenőrzés hibáit, a célzott javítást és a még nyitott biztonsági kapukat rögzíti. A futások állapota idővel változhat; a hivatkozott GitHub Actions futás az elsődleges bizonyíték.

## Vezetői összefoglaló

- **Éles titkosított adatbázis-logikai backup: sikeres.**
- **S3-feltöltés SSE-KMS-sel: sikeres.**
- **Letöltés, age-visszafejtés és manifest-hash ellenőrzés: sikeres.**
- **Izolált PostgreSQL 17 backup/restore integrációs teszt: sikeres.**
- **Teljes CI: a legutóbbi lezárt futásban egy napi briefing regressziós teszt hibázott; a célzott kódjavítás elkészült, az új CI-futás elindult.**
- **Production migráció, Auth/RBAC aktiválás és PR merge: továbbra is tiltott / nem engedélyezett.**

## Hibák és célzott javítások

### 1. Age privát kulcs formátuma

**Korábbi hiba:** a backup #22 feltöltése után az age visszafejtés elbukott, mert a runner nem tudta beolvasni a megadott identity fájlt (unknown identity type). A secret értéke nem megfelelő age privát identity formátumként került átadásra, vagy nem az elvárt titkos kulcsot tartalmazta.

**Javítás:** a workflow előzetesen ellenőrzi, hogy a BACKUP_AGE_IDENTITY secret AGE-SECRET-KEY-1... formátumú privát kulcsot tartalmazzon. A publikus age1... recipient nem használható privát identityként.

**Eredmény:** a [45611038142 backup futás](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45611038142) identity-előkészítési, mentési, AWS OIDC, S3-feltöltési, letöltési, visszafejtési és hash-ellenőrzési lépései mind sikeresek.

### 2. Éles backup és restore bizonyíték

A [45611038142 futás](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45611038142) bizonyítja, hogy a konfigurált GitHub Actions secret-ekkel/változókkal az éles Supabase PostgreSQL logikai dump elkészült, age segítségével titkosítva lett, privát S3 bucketbe SSE-KMS-sel feltöltődött, majd letöltés után visszafejtésre és hash-ellenőrzésre került.

A [45611038183 CI-futás](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45611038183) backup-restore-integration jobja sikeres: elkülönített PostgreSQL 17 adatbázisban tényleges age-titkosított backup/restore round-trip történt.

**Korlát:** ez a logikai adatbázis-mentést igazolja. Nem tartalmazza automatikusan a Supabase által kezelt auth, storage, realtime sémák teljes tartalmát, Storage bináris objektumokat, projektbeállításokat vagy titkos platformkulcsokat.

### 3. Napi vezetői jelentés dátumkezelési regressziója

**Hibás teszt:** tests/test_daily_briefing.py::test_daily_briefing_only_flags_overdue_followups_with_explicit_approval.

**Tünet:** a [45611038183 CI-futás](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45611038183) 639 sikeres és 3 kihagyott teszt mellett ezen az egy teszten bukott el.

**Gyökérok:** a build_daily_briefing(today=...) paraméterrel történelmi / determinisztikus riportdátum adható meg, de a hozzájárulás időpontját a kód korábban a futtató gép aktuális UTC-idejéhez hasonlította. Így egy, a riport dátumához képest későbbi hozzájárulás a teszt aktuális napján már érvényesnek látszhatott. Ez a riport referenciaidejének következetlen használata volt.

**Célzott javítás:** a daily_briefing.py most a consent_confirmed_at időpont Europe/Budapest szerinti naptári dátumát hasonlítja a riport today referencia-dátumához. A jövőbeli hozzájárulás nem számítható be egy korábbi riportba. A többi szigorú feltétel változatlan: explicit jóváhagyás, hozzájárulási jogalap, leiratkozás hiánya, válasz hiánya, érvényes e-mail, státusz és utánkövetési limit.

**Javító commit:** 5f6045069ea875997a896bb3ac83e83869da7e97.

**Új CI:** [45617159105](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45617159105) – a kódjavítás után indult; a dokumentum frissítésekor még nem volt lezárt eredménye. A javítás csak akkor tekinthető igazoltnak, ha ezen vagy egy újabb, pontosan a legfrissebb main commiton futó CI teljesen zöld.

## Még nyitott, nem a fenti CI-hibához tartozó blokkolók

1. A production Supabase migrációs ledger és a repository migrációs fájljai között továbbra is eltérés van; az öt történeti SQL-forrás eredetiségét külön kell kezelni.
2. A production logs táblában hiányoznak a strukturált audit- és hash-lánc mezők; az auditmigrációk production alkalmazása nincs engedélyezve.
3. A production táblák RLS/policy és default privilege állapotának rendezése csak ellenőrzött, jóváhagyott migrációs terv alapján történhet.
4. A Supabase Auth/RBAC funkció productionben maradjon kikapcsolva.
5. A PR #13 maradjon draft/open; automatikus merge nem megengedett.
6. A sikeres backup nem ad engedélyt production DDL/DML-re, migráció javítására, supabase db push futtatására vagy új Supabase projekt létrehozására.
7. Az AWS CloudFormation stack külön telepítési státusza, a teljes Supabase-platform-mentés, a Storage objektumok mentése, valamint a külső Gemini/SMTP/IMAP végponttól végpontig integráció továbbra is külön igazolandó.

## Biztonságos következő lépések

1. Várd meg a [45617159105 CI-futás](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45617159105) eredményét.
2. Ha a teljes CI zöld, ellenőrizd újra a legfrissebb main commiton a backup workflow és a restore-integrációs job eredményét.
3. A PR #13 draft állapotát, az Auth flag OFF állapotát és a production adatbázis változatlanságát tartsd fenn.
4. A migrációs eltéréseket külön, csak olvasási ellenőrzéssel és jóváhagyott tervvel kezeld.

**Jelenlegi döntés:** a backup/restore kapu teljesült az igazolt logikai backupra és az izolált restore-próbára. A teljes CI kapu a dátumkezelési javítás újrafuttatásáig nyitott. A production írási kapu nem teljesült, ezért production adatbázis-módosítás nem végezhető.
