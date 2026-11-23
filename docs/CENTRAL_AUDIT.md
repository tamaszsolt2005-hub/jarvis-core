# Központi műveleti napló és audit

## Alapelv

Az alkalmazás a meglévő `public.logs` táblát és a `jarvis_common.audit_event()`
függvényt használja. Nincs második audit tábla vagy párhuzamos naplózási backend.
A korábbi, szöveges `log_event()` bejegyzések változatlanul megmaradnak; az
strukturált auditbejegyzések ugyanabba a táblába kerülnek.

A strukturált rekord fontos mezői: `id`, `operation_id`, `created_at`,
`module`, `action`, `status`, `result`, `error`, `approved`,
`recipient`, `subject`, `delivery_id`, `level`.

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

Kész, szerepkör szerint védett adminisztrációs audit UI jelenleg nincs. A
dashboard még közös jelszót használ, ezért auditadatot megjelenítő új UI-t
nem szabad minden közös jelszóval rendelkező felhasználó számára megnyitni;
az admin-only felület az Auth/RBAC migrációval együtt vezethető be.

## Adatbázis-kompatibilitás és telepítés

A repository `supabase/schema.sql` fájlja a meglévő `logs` táblához
`ADD COLUMN IF NOT EXISTS` utasításokkal adja hozzá a strukturált mezőket,
és indexeket hoz létre. Ez additív: nem törli és nem írja át a korábbi
naplóbejegyzéseket. Ehhez a bővítéshez új tábla vagy új oszlop nem szükséges.

A forráskód és a sémafájl ellenőrzése nem bizonyítja, hogy a változás már
alkalmazva van az éles Supabase-projekten. A telepítés előtt ellenőrizni kell,
hogy a `logs` táblán a szükséges oszlopok és indexek léteznek-e; az éles
adatbázis módosítása külön jóváhagyást igényel.

## Ismert korlátok

- A `logs` táblán az RLS be van kapcsolva, de a repository sémája nem ad
  végleges, szerepkörspecifikus policy-kat. A service-role kulcs megkerüli az RLS-t.
- Admin-only audit UI még nincs; bevezetése az Auth/RBAC migrációtól függ.
- Nincs igazolt immutable/WORM tárolás, aláírt auditlánc vagy megőrzési/retenciós
  szabály. Ezekhez külön, jóváhagyott tárolási és megőrzési követelmény, valamint
  külső infrastruktúra szükséges.
- A batch audit nem helyettesíti a soronkénti üzleti rekordtörténetet.
