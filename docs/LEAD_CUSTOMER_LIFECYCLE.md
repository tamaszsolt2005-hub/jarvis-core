# JARVIS CRM – ügyfél-életciklus és interakciók

## Cél

A Leadkezelőben jóváhagyott leadek ügyfélkapcsolati folyamatának követése. A CRM az ember által végrehajtott kapcsolatfelvételt és ügyfélinterakciókat naplózza; nem kezdeményez automatikus kapcsolatfelvételt.

## Életciklus

- approved_lead – jóváhagyott lead
- contacted – kapcsolatfelvétel megtörtént
- responded – válaszolt
- qualified – minősített érdeklődő
- proposal – ajánlat előkészítése / elküldve
- pilot – pilot
- customer – ügyfél
- lost – lezárt / elvesztett

A státusz manuálisan módosítható. Nincs automatikus státuszváltás e-mailből, és a bejövő válaszra JARVIS nem küld választ.

## Rögzíthető események

- Státuszváltozás indoklással.
- Interakció rögzítése: kézzel rögzített e-mail, telefon, megbeszélés, belső jegyzet vagy egyéb csatorna.
- Következő teendő és opcionális határidő.

Minden esemény append-only előzményként kerül tárolásra. A CRM aktuális állapota külön táblában gyorsan lekérdezhető.

## Jogosultság

- admin / operator: a CRM-eseményeket kizárólag a record_lead_customer_lifecycle_event RPC-n keresztül rögzítheti.
- reader: csak olvashat.
- anon: nincs hozzáférése.
- A művelet csak lead_review_states.review_status = approved leaden engedélyezett.
- A dashboard authenticated Supabase klienst használ; nincs service-role írási kerülőút.

## Biztonsági határ

- A CRM nem küld e-mailt, nem indít follow-upot és nem változtat kapcsolatfelvételi engedélyt.
- Az e-mail csatorna kiválasztása csak egy korábban megtörtént, kézzel rögzített interakció naplózása.
- A kimenő e-mailküldés EMAIL_DELIVERY_ENABLED = False hard gate változatlanul aktív.
- A bejövő ügyfélválaszokat JARVIS külön jelzi; válaszadás csak a felhasználó későbbi utasítására történhet.

## Migráció

supabase/migrations/20261127210000_lead_customer_lifecycle.sql

A migráció kizárólag a PR #35 fejlesztési ágban van; production adatbázison nem futott le.


## Lejárt következő teendők

A CRM dashboard a rögzített `next_action` és `next_action_due` mezőkből külön lejárt teendő számlálót és szűrőt képez. Csak akkor jelöl egy sort lejártnak, ha tényleges teendő szöveg és múltbeli dátum is van; a mai határidő még nem lejárt, a hibás dátumot pedig nem minősíti automatikusan késedelmesnek. A dátum-összehasonlítás Europe/Budapest helyi naptári nap szerint történik. A listában a lejárt teendők kerülnek előre, a lead részlete pedig figyelmeztetést jelenít meg. Ez megjelenítési és prioritási funkció, nem küld automatikus értesítést vagy e-mailt.


## Feladatközpont-integráció

A Feladatközpont külön CRM-teendő nézetben olvassa a jóváhagyott leadek `lead_customer_lifecycle.next_action` és `next_action_due` mezőit. A nézet a meglévő `tasks.lead_id` kapcsolaton keresztül megmutatja, van-e már nyitott feladat az adott leadhez, és felsorolja annak címét. A lezárt feladat nem számít aktív kapcsoltnak.

- A CRM-teendő és a JARVIS-feladat két külön rekord marad; a nézet nem hoz létre automatikusan feladatot és nem módosít adatot.
- Csak jóváhagyott lead CRM-teendője jelenik meg.
- A lejárt állapot a Europe/Budapest szerinti helyi naptári nap alapján készül.
- Ha a CRM lifecycle vagy a lead review adatforrás hibás, a nézet figyelmeztetést mutat, nem tekinti üresnek az adatot.
- A feladat létrehozása/módosítása továbbra is a chat külön jóváhagyási folyamatán keresztül történik.
