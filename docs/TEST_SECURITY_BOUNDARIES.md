# Tesztbiztonsági határok és jogosultsági lefedettség

## Hálózati izoláció a pytest alatt

A `tests/conftest.py` minden normál teszteset előtt tiltja a DNS-feloldást és a kimenő socketműveleteket (`connect`, `connect_ex`, `sendto`, `create_connection`). Ha egy teszt valódi külső kapcsolatot próbál nyitni mock nélkül, a teszt hibával leáll.

Kivétel kizárólag a `live_integration` markerrel ellátott, külön opt-in teszt lehet. A jelenlegi `tests/test_live_integrations.py` csak akkor fut, ha a `JARVIS_LIVE_INTEGRATION_TESTS=1` beállítás kifejezetten engedélyezett. Ezek a tesztek Supabase olvasást és Gemini generálást végeznek; nem küldenek e-mailt és nem írnak üzleti rekordot.

A socket-védelem a pytest folyamaton belüli Python hálózati hívásokat fogja meg. Nem tekinthető operációsrendszer-szintű sandboxnak, és önmagában nem korlátoz egy külön elindított subprocess-t. Külső folyamatot indító tesztekben a subprocess hívást külön mockolni kell.

## Jelenleg tesztelt alkalmazás-hozzáférési határok

- A dashboard közös `JARVIS_DASHBOARD_PASSWORD` jelszóval védett.
- A belépési session legfeljebb 8 óráig érvényes; hiányzó, lejárt vagy jövőbeli időbélyeg esetén a session, a gyorsítótárazott DB-kliens és a függő művelet törlődik.
- A dashboard a hitelesítés hiányában `st.stop()` hívással megállítja a privát felület további feldolgozását.
- A feladatműveletek végrehajtó függvénye alapértelmezetten elutasítja a hívást; a dashboard csak a külön jóváhagyási ágon ad át `approved=True` értéket.
- A tesztek ellenőrzik a jóváhagyás nélküli hívás elutasítását, valamint azt, hogy ilyen esetben az adatbázis elérése sem indul el.
- A repository SQL-sémája bekapcsolja az RLS-t az alkalmazástáblákon.

## Fontos, még nem megoldott jogosultsági korlátok

A jelenlegi dashboard egyetlen megosztott jelszót használ. Nincs külön felhasználói identitás, admin/user szerepkör, felhasználónkénti jogosultságmátrix vagy tenant-szintű adatszegregáció. Az `approved=True` paraméter alkalmazáson belüli védőkorlát, nem önálló hitelesítési token vagy RBAC-rendszer.

A repository `supabase/schema.sql` fájlja RLS-t engedélyez, de nem definiál táblánkénti `CREATE POLICY` szabályokat. A dashboard szerveroldali Supabase service-role kulcsot is használhat; a service-role hozzáférés megkerüli az RLS-t. Emiatt a jelenlegi pytest tesztek az RLS bekapcsolását igazolják, nem a tényleges adatbázis-szintű hozzáférés-szabályokat.

Éles jogosultsági garanciához külön döntés és elkülönített tesztkörnyezet szükséges:
1. egyedi felhasználói identitás és szerepkörmodell meghatározása;
2. táblánkénti RLS policy-k és service-role használati határok megtervezése;
3. anon, authenticated, admin és service-role hozzáférési mátrix ellenőrzése izolált Supabase tesztprojektben;
4. negatív tesztek más felhasználó rekordjainak olvasására és módosítására;
5. a tényleges dashboard-bejelentkezési folyamat végponttól végpontig történő tesztelése.

Ezeket a teszteket nem szabad mockolt egységtesztek alapján éles adatbázis-jogosultságként vagy teljes RBAC-ként feltüntetni.
