# Központi műveleti napló és audit

## Alapelv

Az alkalmazás a meglévő `public.logs` táblát és a `jarvis_common.audit_event()`
függvényt használja. Nincs második audit tábla vagy párhuzamos naplózási backend.
A korábbi, szöveges `log_event()` bejegyzések változatlanul megmaradnak; az
strukturált auditbejegyzések ugyanabba a táblába kerülnek.

A strukturált rekord fontos mezői: `id`, `operation_id`, `created_at`,
`module`, `action`, `status`, `result`, `error`, `approved`,
`recipient`, `subject`, `delivery_id`, `actor_user_id`, `previous_hash`, `entry_hash`, `level`.

## Lefedett műveleti életciklusok

| Terület | Audit esemény | Működés |
|---|---|---|
| Feladatok | `task_actions` műveletek | pending a DB-művelet előtt; success/blocked/failed/unknown a kimenet szerint |
| Kimenő e-mail | `email_sender` | pending az SMTP előtt; címzett, tárgy, jóváhagyás; siker esetén delivery/message ID |
| Follow-up e-mail | `follow_up.send_follow_up_email` | pending az SMTP előtt; egyetlen UUID köti össze a pending és a lezáró eseményt |
| CSV lead import | `lead_gen.import_reviewed_csv` + `create_reviewed_lead` | batch pending/success; minden tényleges lead beszúrás saját pending/success vagy failed/unknown eseménnyel és külön operation ID-val; e-mail-cím és lead payload nélkül |
| Globális kutatási automatizmus | `global_lead_research_job.daily_global_research` | pending a kutatás előtt; success csak a futás lezárása után; failed hiba esetén |
| Bejövő e-mail | `email_inbox.inbound_reply` / `inbound_opt_out` | pending a lead állapotmódosítása előtt; success utána; UID-alapú determinisztikus operation ID segíti az audit helyreállítását |

A CSV-import batch- és ténylegesen beszúrt lead-szintű auditot ad; a duplikált vagy
validáció miatt kihagyott sorok csak a batch számlálóiban jelennek meg. A globális
kutatási automatizmus batch-szintű auditot ad; nem állítja, hogy minden kutatási
jelölt vagy kihagyott jelölt külön auditrekordot kap.

## Hibakezelési szabály

- Ha a pending audit nem menthető, a hozzá tartozó lead-import, kutatási vagy
  bejövő levél DB-művelet nem indul el.
- Ha egy külső vagy DB-művelet már megtörtént, de a lezáró audit nem menthető,
  a rendszer hibát jelez, és nem állítja biztosra a teljes műveleti láncot.
- Bejövő IMAP üzenetnél a UID checkpoint nem lép tovább záró audit-hiba esetén.
  Az ismételt futás ugyanazzal a determinisztikus operation ID-val megpróbálja
  helyreállítani a lezáró auditot.
- SMTP-küldés után bizonytalan kimenet esetén az állapot nem válik automatikusan
  újraküldhetővé; az esemény `unknown` állapotot kaphat.
- Az audit írásának hibája önmagában is kritikus diagnosztikai eseményként kerül
  jelentésre a központi hibakezelőn keresztül.

## Adatvédelem

- E-mail törzs, IMAP üzenettörzs és teljes lead payload nem kerül az auditba.
- Kimenő levélnél a címzett és tárgy üzleti auditmezőként rögzül; inbound eseménynél
  csak a feldolgozási állapot, műveleti ID és üzenet/delivery azonosító szerepel.
- A `audit_event()` a hibaszöveget, tárgyat, címzettet, delivery ID-t és eredményt
  korlátozza/tisztítja; a titokkulcsokra utaló eredménymezőket maszkolja.
- Ez nem általános DLP-rendszer: az önkényes szövegben szereplő minden személyes
  adat felismerése nem garantált. Új auditmezőt csak minimális, előre meghatározott
  üzleti metaadattal szabad bevezetni.

## Lekérdezés

A `get_audit_events()` a meglévő táblából kér le strukturált eseményeket,
legújabbtól legrégebbiig rendezve. Szűrhető modul, művelet, státusz és
`operation_id` szerint; a lekérdezési limit legfeljebb 1000. A stabil
`created_at + id` összetett kulcson alapuló lapozást a
`get_audit_events_page()` biztosítja (legfeljebb 500 rekord/oldal), az
azonos időbélyegű események kihagyása nélkül. A kurzor időbélyegét és UUID-ját
a lekérdezés előtt validálja.

A külön audit-admin oldal már elkészült. A közös dashboard-jelszó önmagában
nem ad hozzáférést: külön Supabase Auth belépés, szerveroldali `get_user()`
ellenőrzés és a megbízható `app_metadata.role = admin` claim szükséges.
A nézet felhasználói JWT-vel olvas, modul/státusz/operation ID szerint szűr,
kurzorosan lapoz, CSV-t exportál pending/success audit-életciklussal, és
kézzel indítható hash-lánc integritás-ellenőrzést biztosít.

## Adatbázis-kompatibilitás és telepítés

A repository `supabase/schema.sql` fájlja és a két egymásra épülő migráció
additív módon bővíti a meglévő `logs` táblát. A második migráció egyetlen
privát `audit_chain_state` fejállapot-táblát használ a hash-lánc sorosításához;
ez nem párhuzamos eseménynapló. A régi naplóbejegyzések nem kerülnek átírásra.

A forráskód és a sémafájl ellenőrzése nem bizonyítja, hogy a változás már
alkalmazva van az éles Supabase-projekten. A telepítés előtt ellenőrizni kell,
hogy a `logs` táblán a szükséges oszlopok és indexek léteznek-e; az éles
adatbázis módosítása külön jóváhagyást igényel.

## Ismert korlátok

- A `logs` olvasása admin-only RLS policy-val védett, de a service-role kulcs
  továbbra is megkerüli az RLS-t, és szerveroldali üzleti műveletek használják.
- A hash-lánc append-only triggert és SHA-256 ellenőrzést biztosít az új
  rekordokra, de nem WORM és nem véd a DB-tulajdonos vagy más privilegizált
  operátor ellen. A régi rekordok nem részei a láncnak.
- Nincs jóváhagyott megőrzési idő, jogi hold vagy külső immutable/WORM archívum.
  Ezekhez külön üzleti döntés és tárolási infrastruktúra szükséges.
- A batch audit nem helyettesíti a soronkénti üzleti rekordtörténetet.


## Irányítás és éles bevezetés

A felhasználó-azonosítás, RBAC, RLS-ellenőrzés, megőrzési döntés, változtathatatlan archiválás, integritás-ellenőrzés, riasztások és audit-export bevezetési feltételeit a [AUDIT_GOVERNANCE.md](AUDIT_GOVERNANCE.md) rögzíti. Ezek közül a külső infrastruktúrát vagy üzleti döntést igénylő kontrollokat ez a PR nem állítja késznek.



## Adminisztratív audit-hozzáférés és integritás

Az admin-only Supabase Auth auditnézet, a JWT-alapú RLS policy, az append-only adatbázis-triggerek és a SHA-256 hash-lánc részleteit a [AUDIT_GOVERNANCE.md](AUDIT_GOVERNANCE.md) dokumentálja. A hash-lánc nem WORM; a teljes üzleti RBAC és tenant-izoláció továbbra sincs bevezetve.
