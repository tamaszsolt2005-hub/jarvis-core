# Szerepköralapú hozzáférés – célmodell és bevezetési terv

## Cél

A JARVIS jelenlegi, közös dashboard-jelszavas belépése nem biztosít felhasználónkénti identitást. Az alábbi modell a jóváhagyott három szerepkör célállapota; **önmagában ez a dokumentum és a hozzá tartozó tesztelés még nem aktivál RBAC-védelmet**.

## Szerepkörök

- **admin**: teljes hozzáférés, beleértve a rendszerbeállításokat és az adminisztratív műveleteket.
- **operator**: üzleti napi műveletek – leadek és feladatok kezelése, e-mail-tervezetek előkészítése és a külön jóváhagyási folyamaton belüli engedélyezett műveletek. Rendszerbeállításokat és felhasználói jogosultságokat nem módosíthat.
- **reader**: csak olvasás; nem módosíthat üzleti rekordot, nem indíthat küldést és nem hajthat végre jóváhagyott műveletet.

## Első hozzáférési mátrix

| Erőforrás / művelet | admin | operator | reader |
|---|---:|---:|---:|
| Leadek olvasása | igen | igen | igen |
| Leadek létrehozása/módosítása | igen | igen | nem |
| Feladatok olvasása | igen | igen | igen |
| Feladatok létrehozása/módosítása/lezárása | igen | igen | nem |
| E-mail-tervezetek olvasása | igen | igen | igen |
| E-mail-tervezetek létrehozása/módosítása | igen | igen | nem |
| Jóváhagyott e-mail-küldés | igen | igen, külön megerősítéssel | nem |
| Analitika olvasása | igen | igen | igen |
| Rendszerbeállítások olvasása/módosítása | igen | nem | nem |
| Felhasználók és szerepkörök kezelése | igen | nem | nem |
| Auditnapló olvasása | igen | nem | nem |
| Hosszú távú memória módosítása | igen | igen, explicit utasítással | nem |

A végleges táblánkénti SQL-policy-kat a tényleges táblák, függvények, view-k és háttérfolyamatok áttekintése után kell rögzíteni. Az audit események írása backend-feladat; a böngészőből közvetlen audit-hamisítást nem szabad engedni.

## Kötelező biztonsági architektúra

1. Egyedi Supabase Auth-felhasználó minden embernek; a közös dashboard-jelszó nem lehet az RBAC identitásforrása.
2. A szerepkör kizárólag megbízható, admin által kezelt `app_metadata`-ból származhat. A felhasználó által módosítható `user_metadata` nem használható jogosultsági döntéshez.
3. A szerepkör hiánya, hibás értéke, lejárt/érvénytelen session vagy nem ellenőrizhető token esetén a hozzáférés alapértelmezetten tiltott.
4. A felhasználói műveletekhez a felhasználó JWT-jével működő, RLS-t érvényesítő adatbázis-kliens szükséges. A service-role kulcs megkerüli az RLS-t, ezért nem lehet a felhasználói hozzáférés-ellenőrzés helyettesítője.
5. A service-role kulcs kizárólag szűk, szerveroldali, külön ellenőrzött háttérfeladatokban maradhat; nem kerülhet böngészőbe vagy user-controlled kódba.
6. Minden módosító műveletnél UI- és szerveroldali ellenőrzés kell. A UI gomb elrejtése nem biztonsági határ.
7. A jóváhagyás legyen művelethez kötött, egyszer használatos és lejáró; a jelenlegi `approved=True` paraméter önmagában nem hitelesítési mechanizmus.
8. Minden RLS-policy-nál ellenőrizni kell a SELECT/INSERT/UPDATE/DELETE műveleteket, beleértve az UPDATE `USING` és `WITH CHECK` feltételeit, valamint a view-k és RPC-k hozzáférését.

## Bevezetési lépések

1. Supabase Auth beléptetés és felhasználói session kialakítása a jelenlegi megosztott jelszó helyett.
2. Szerepkör-adminisztráció kizárólag megbízható admin felületen / szerveroldali folyamatban.
3. A dashboard és a modulok DB-hozzáférésének átalakítása felhasználói JWT-re, ahol felhasználói művelet történik.
4. Táblánkénti RLS-policy-k és minimális GRANT-ok kialakítása.
5. Valós Auth/JWT/RLS teszt csak már létező, kifejezetten engedélyezett izolált környezetben végezhető; új Supabase tesztprojekt létrehozása nem része ennek a munkának.
6. Migráció után régi közös jelszó belépésének eltávolítása, majd teljes böngészős regresszió.

## Kötelező negatív tesztek

- anon és érvénytelen/hiányzó role nem olvashat és nem írhat védett adatot;
- reader minden írási útvonalon tiltást kap (UI, közvetlen DB API, RPC és modulfüggvény);
- operator nem módosíthat settings-et, szerepkört vagy admin-only auditadatot;
- operator nem emelheti saját szerepkörét user_metadata vagy közvetlen kliens payload segítségével;
- egyik felhasználó sessionje nem használható másik felhasználó nevében;
- UPDATE nem változtathatja meg a rekord tulajdonosát / jogosultsági hatókörét;
- service-role műveletek csak explicit, tesztelt szerveroldali belépési ponton érhetők el;
- e-mail-küldés readerként, jóváhagyás nélkül, illetve kikapcsolt szerveroldali kapcsolóval mindig blokkolt.

## Tesztelési határ

A repositoryban futó mockolt pytest/AppTest tesztek az alkalmazás logikáját és a policy-szerződéseket ellenőrizhetik, a CI PostgreSQL 17 + pgTAP tesztjei pedig a migrációk és SQL-policy-k adatbázis-szintű viselkedését ellenőrzik. Ezek egyike sem bizonyítja a Supabase Auth szolgáltatás valós JWT-integrációját. Valós Auth/JWT/RLS teszt kizárólag már létező, engedélyezett izolált környezetben végezhető; új Supabase projektet nem hozunk létre. A production adatbázis nem használható tesztkörnyezetként.

**Jelenlegi állapot:** a projekt továbbra is közös jelszavas, service-role kulcsot használó architektúrával rendelkezik. Az RBAC célmodell dokumentálva van, de még nincs élesítve; a production schema és adatok nem változtak.


## Aktuális megvalósítási állapot – audit-admin rész

A külön auditoldal már Supabase Auth belépést és szerveroldali
`get_user()` tokenellenőrzést követel. A szerepkört kizárólag a hitelesített
felhasználó `app_metadata.role` claimjéből olvassa; a közös dashboard-jelszó
nem jogosít auditolvasásra. A `logs` táblára készített migráció
`authenticated` SELECT grantet és admin-only RLS policy-t ad, valamint
megtiltja a kliensoldali írást/módosítást/törlést.

Ez **csak az audit olvasási felületét védi**. A teljes admin/operator/reader
mátrix a leadekre, feladatokra, e-mail-tervezetekre, beállításokra és
memóriára még nem aktív, mert ezek a modulok jelenleg a szerveroldali
service-role klienssel működnek. Tenant-izoláció sincs, mivel a jelenlegi
adatmodell egyetlen üzleti munkaterületet feltételez. Ezeket a hiányokat nem
lehet biztonságosan egyetlen audit policy-val megoldani.

## RBAC Auth-alap – első kódfázis

**Implementálva a `feat/supabase-auth-rbac-foundation` ágon:**
- Új `jarvis_auth.py`: külön Supabase Auth-fiókos belépés, szerver által ellenőrzött `get_user()`, megerősített e-mail követelménye, és kizárólag a megbízható `app_metadata.role` olvasása.
- A felhasználói adatbázis-kliens kizárólag `SUPABASE_PUBLISHABLE_KEY` vagy a régi `SUPABASE_ANON_KEY` kulcsot fogadja el; nem esik vissza `SUPABASE_SERVICE_ROLE_KEY` vagy a kétértelmű `SUPABASE_KEY` értékre.
- Session-frissítéskor újra ellenőrzi a felhasználót, az azonosítót és a szerepkört; hiányzó/érvénytelen szerepkör és nem engedélyezett szerep esetén tilt.
- Központi, fail-closed jogosultságmátrix az admin/operator/reader szerepkörökhöz.
- Mockolt tesztek lefedik a kulcsválasztást, a megbízható metadata forrást, a hiányzó/hibás role-t, a megerősítetlen e-mailt, a session-ellenőrzést és a szerepkör-mátrixot.

**Ez még nem aktív dashboard-RBAC.** A fő Streamlit belépés egyelőre nem lett lecserélve, az alkalmazás üzleti moduljai továbbra is használhatják a meglévő service-role klienst, és nem készültek / nem kerültek alkalmazásra táblánkénti RLS-policy-k. A régi közös jelszó eltávolítása most azonnal kizárhatná a felhasználót, mert a korábbi read-only felméréskor nem volt Supabase Auth-felhasználó.

**Élesítés előtti blokkolók:**
1. A meglévő Supabase Auth-fiókok és megerősített e-mail-címek ellenőrzése; admin szerepkör kiosztása kizárólag megbízható admin folyamatban.
2. A hiányzó történeti migrációk forrásának helyreállítása és a tényleges production séma/migration history egyeztetése.
3. Táblánkénti hozzáférési modell és RLS-policy-k megtervezése a tényleges üzleti műveletekhez, valamint a service-role háttérfolyamatok leválasztása.
4. Valós Auth/JWT/RLS integrációs bizonyíték. Új tesztprojektet nem hozunk létre; amíg nincs engedélyezett izolált tesztkörnyezet, csak mockolt tesztek állíthatók sikeresnek.

**Éles adatbázis, Auth-felhasználók, szerepkörök és production migrációk nem változtak.**
