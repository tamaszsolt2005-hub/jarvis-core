# JARVIS – merge és production release gate-ek

**Felülvizsgálat:** 2026-11-25  
**Tartós fejlesztési ág:** `main`

> **A fejlesztési javaslatok és azok implementációs státuszának egyetlen forrása:** [Fejlesztési áttekintés, ellenőrzött állapot és javaslatok](DEVELOPMENT_REVIEW_AND_RECOMMENDATIONS.md). Ez a dokumentum szándékosan nem ismétli meg az ott felsorolt fejlesztési feladatokat; kizárólag a merge és production kiadás döntési kapuit tartalmazza.

## 1. Aktuális GitHub-állapot

- Main HEAD: `6b22893b650c4a6336adef3b43429ce69e567738`.
- PR #13 head: `32aef539c0128c1fedaa9e03768477433e93abe1`.
- PR #13: draft, nyitott, nincs merge-elve.
- PR #13: a main integrálása megtörtént; 0 commit behind. A PR továbbra is draft és nincs merge-elve.
- [PR CI #45620672894](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45620672894): sikeres a PR akkori headjén.
- [Main CI #45621572548](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45621572548): sikeres a `f49eda7` main headen.

A CI eredmények csak a megadott commitokra érvényesek. A main és a PR frissítése után a legújabb headeken újra kell ellenőrizni őket.

## 2. PR merge gate

- [x] A PR frissítése a legújabb mainre; a behind érték 0.
- [ ] A teljes PR diff és commit-történet review-ja lezárult.
- [ ] A migrációk, RLS/GRANT, Auth trust boundary, backup workflow és approval/idempotencia útvonalak review-ja lezárult.
- [ ] A PR legfrissebb headjén minden kötelező CI-job sikeres.
- [ ] A GitHub mergeability és branch protection közvetlenül a döntés előtt ellenőrizve.
- [ ] A dokumentáció és a kód állapota egyezik; nincs elavult CI/head vagy egymásnak ellentmondó checklist.
- [ ] A fennmaradó, nem blokkoló fejlesztési adósságok elfogadása és ütemezése dokumentált.
- [ ] Külön, kifejezett döntés született a merge-ről.

**Merge-döntés:** a CI-zöldség önmagában nem elég. A PR jelentős változáscsomagja miatt teljes review szükséges. A merge nem automatikus.

## 3. Production release gate

A production bevezetés a PR merge-től külön döntés. A következő bizonyítékok nélkül a production Supabase maradjon read-only, az Auth/RBAC flag pedig OFF:

- [ ] A konkrét production backup archívum visszaállítása külön, izolált adatbázisba.
- [ ] Post-restore ellenőrzés és jegyzőkönyv: séma, rekordok, kritikus táblák, indexek, jogosultságok és alkalmazás-kompatibilitás.
- [ ] Production preflight és migrációs ledger eltérés dokumentált, felülvizsgált rendezési terve.
- [ ] Valós Auth-issued JWT/PostgREST/RLS teszt kizárólag már létező és kifejezetten engedélyezett izolált Supabase környezetben.
- [ ] Minden production változtatáshoz külön jóváhagyott terv, rollback és megfigyelési/ellenőrzési lépések.
- [ ] Backup/recovery, retention, kulcskezelés és incidenskezelés üzemeltetési feltételei elfogadva.

## 4. Tiltott műveletek külön jóváhagyás nélkül

- Production DDL/DML.
- `supabase db push`, `supabase migration repair`, migration ledger kézi módosítása.
- GRANT/REVOKE vagy RLS policy módosítás productionben.
- Production Auth-user provisioning vagy Auth/RBAC aktiválás.
- AWS production stack deploy.
- Új Supabase account, projekt vagy branch létrehozása.
- PR merge.

## 5. Döntési állapot

**PR #13:** a main szinkronizálása megtörtént (0 behind). A teljes változáscsomagot továbbra is review-zni kell, és a friss head CI-jét ellenőrizni.

**Production:** nem release-ready, amíg a konkrét production backup restore, preflight és az izolált élő Auth/JWT/RLS bizonyítékok nem állnak rendelkezésre, és a production változtatási terv nincs külön jóváhagyva.

**Munkaszervezés:** a cél egyetlen tartós `main` ág. Az átmeneti PR ág csak a jelenlegi integrációs folyamat miatt létezik; a további munka a merge után a mainen folytatódik.
