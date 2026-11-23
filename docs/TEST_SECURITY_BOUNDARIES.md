# Tesztbiztonsági határok és jogosultsági lefedettség

## Hálózati izoláció a pytest alatt

A `tests/conftest.py` minden normál teszteset előtt tiltja a DNS-feloldást és a kimenő socketműveleteket (`connect`, `connect_ex`, `sendto`, `create_connection`). Ha egy teszt valódi külső kapcsolatot próbál nyitni mock nélkül, a teszt hibával leáll.

A hálózati tiltás alóli kivétel nem pusztán a marker meglététől függ: kizárólag a `tests/test_live_integrations.py` fájlban, `live_integration` markerrel és `JARVIS_LIVE_INTEGRATION_TESTS=1` környezeti kapcsolóval engedélyezett. Egy másik teszt nem tudja egy marker hozzáadásával kikapcsolni a hálózati védelmet. Ezek a live tesztek Supabase olvasást és Gemini generálást végeznek; nem küldenek e-mailt és nem írnak üzleti rekordot.

A socket-védelem a pytest folyamaton belüli Python hálózati hívásokat fogja meg. Nem tekinthető operációsrendszer-szintű sandboxnak, és önmagában nem korlátoz egy külön elindított subprocess-t. Külső folyamatot indító tesztekben a subprocess hívást külön mockolni kell.

## Jelenleg tesztelt alkalmazás-hozzáférési határok

- A dashboard közös `JARVIS_DASHBOARD_PASSWORD` jelszóval védett.
- A belépési session legfeljebb 8 óráig érvényes; hiányzó, lejárt vagy jövőbeli időbélyeg esetén a session, a gyorsítótárazott DB-kliens és a függő művelet törlődik.
- A dashboard a hitelesítés hiányában `st.stop()` hívással megállítja a privát felület további feldolgozását.
- A feladatműveletek végrehajtó függvénye alapértelmezetten elutasítja a hívást; csak a valódi boolean `approved=True` fogadható el. A dashboard ezt csak a külön jóváhagyási ágon adja át.
- A feladatművelet teljes payloadja típus-, mező-, hossz-, UUID-, prioritás- és időzóna-ellenőrzést kap, még az audit- és adatbázis-elérés előtt.
- A tesztek ellenőrzik a jóváhagyás nélküli és hibás payloadú hívás elutasítását, valamint azt, hogy ilyen esetben az adatbázis elérése sem indul el.
- A külön follow-up küldő csak időbélyegzett, aktuális explicit hozzájárulással, érvényes címmel, leiratkozás és válasz nélkül dolgozhat. SMTP-kísérlet utáni bizonytalan kimenet nem kerül vissza automatikusan küldhető állapotba.
- A bejövő e-mail tesztek mockolt IMAP-pal ellenőrzik a válasz/leiratkozás feldolgozását és az UID checkpointot; valódi levélküldés nincs.
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


## Tesztlefedettség mérése

A CI a `pytest-cov` csomaggal minden push és pull request során lefedettségi riportot készít:

```bash
python -m pytest -q --cov --cov-report=term-missing:skip-covered --cov-report=xml
```

A repository jelenlegi minimum küszöbe 80%. A küszöb alatti futás hibás CI-eredményt ad. A százalék a Python statement-lefedettséget méri; önmagában nem bizonyítja az összes üzleti útvonal, integráció, jogosultsági szabály vagy éles szolgáltatás helyességét. A nagy Streamlit UI-felület és az összetett adatbázis-/külső szolgáltatási folyamatok további célzott tesztelést igényelnek.
