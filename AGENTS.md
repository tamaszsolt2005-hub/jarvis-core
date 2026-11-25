# AI fejlesztési útmutató – JARVIS

## Elsődleges szabályok

1. A tartós ág a `main`. A feature ág és PR csak átmeneti integrációs eszköz; merge után zárd le, ha a GitHub jogosultság engedi.
2. Módosítás előtt olvasd el ezt a fájlt, a `README.md`-t és a releváns részt a `docs/JARVIS_DOCUMENTATION.md`-ből.
3. A forráskód, a `supabase/migrations/` és a `.github/workflows/` az elsődleges technikai igazság. A dokumentáció ezek összefoglalója.
4. Minden státusznál különböztesd meg: **kódban implementált**, **automatikusan tesztelt**, **külső integrációval igazolt**, **productionben aktív**. Ezek nem felcserélhetők.
5. Minden kódváltozással együtt frissítsd az érintett dokumentációt. Töröld az elavult állításokat; ne adj hozzá újabb dátumos státusznaplót, ha a meglévő központi dokumentum frissíthető.
6. Ne találgass production állapotot. A production adatbázisról csak friss, read-only lekérdezés alapján állíts tényt.

## Production biztonsági határ

Külön, konkrét jóváhagyás nélkül TILOS:
- production Supabase DDL/DML vagy bármilyen adatírás;
- `supabase db push`, `supabase migration repair`, migration ledger kézi módosítása;
- GRANT/REVOKE, RLS policy vagy Auth user módosítása;
- production Auth/RBAC feature flag bekapcsolása;
- AWS production deploy vagy backup-infrastruktúra módosítása;
- új Supabase projekt vagy branch létrehozása.

A production projekt read-only állapotának vizsgálata nem ad engedélyt írásra. Titkot, tokent, connection stringet, személyes adatot ne tegyél Gitbe, logba vagy dokumentációba.

## Ellenőrzés

- Tesztfüggőségek: `python -m pip install -r requirements-test.txt`
- Szintaxis: `python -m compileall -q .`
- Tesztek: `python -m pytest -q`
- Adatbázis migrációs és pgTAP tesztek: a `.github/workflows/ci.yml` által létrehozott izolált PostgreSQL 17 környezetben.
- Live Auth/JWT/RLS smoke kizárólag már létező, kifejezetten engedélyezett izolált Supabase környezetben futhat; productionre soha.

Ne állíts sikeres tesztet pusztán azért, mert a workflow elindult. A futásnak a vizsgált commiton befejezett `success` eredményűnek kell lennie.

## Dokumentumok – egyetlen forrás minden témához

- `README.md`: rövid projektismertető, telepítés, dokumentációs belépő.
- `docs/JARVIS_DOCUMENTATION.md`: jelenlegi képességek, architektúra, modulok, működési korlátok.
- `docs/PRODUCTION_STATE_AND_MIGRATION_PLAN.md`: production tények, migrációs drift, backup, Auth/RLS kapuk.
- `docs/DEVELOPMENT_REVIEW_AND_RECOMMENDATIONS.md`: egyetlen fejlesztési backlog, prioritással.
- `docs/REMAINING_WORK_AND_RELEASE_GATES.md`: kizárólag production/release engedélyezési kapuk.

A PR-állapotot, CI-eredményeket és dátumozott pillanatfelvételeket ne másold több dokumentumba. Hivatkozz a GitHub Actions futásra vagy frissítsd a fenti központi fájlt.
