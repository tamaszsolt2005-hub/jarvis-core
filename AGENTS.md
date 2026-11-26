# AI fejlesztési útmutató – JARVIS

## Aktuális munkamód

- A JARVIS app még nincs deployolva; jelenleg helyi Streamlit dashboard fejlesztés folyik. Ne keress vagy feltételezz JARVIS production hostot: nincs kiválasztva.
- A helyi funkciófejlesztést nem blokkolják a későbbi production release gate-ek. Az élesítési kapuk csak deploy, production DB/Auth/jogosultság módosítás vagy külső mellékhatás előtt érvényesek.
- Az aktuális státusz egyetlen központi összefoglalója: [CURRENT_STATE_AND_NEXT_STEPS.md](docs/CURRENT_STATE_AND_NEXT_STEPS.md).

## Elsődleges szabályok

1. **Minden munkamenet első dokumentuma: [JARVIS elsődleges fejlesztési útiterve](docs/JARVIS_DEVELOPMENT_ROADMAP.md).** Ez határozza meg a fejlesztés sorrendjét és az aktuális haladást.
2. A roadmap után olvasd el ezt a fájlt, a `README.md`-t és a releváns részletes dokumentációt.
3. A tartós ág a `main`. Feature ág/PR átmeneti integrációs eszköz; PR merge csak külön, konkrét felhasználói jóváhagyással történhet. Ne következtess merge-engedélyre általános munkafolytatási kérésből.
4. A forráskód, a `supabase/migrations/` és a `.github/workflows/` az elsődleges technikai igazság. A dokumentáció ezek összefoglalója.
5. Minden státusznál különböztesd meg: **kódban implementált**, **automatikusan tesztelt**, **külső integrációval igazolt**, **productionben aktív**. Ezek nem felcserélhetők.
6. Minden kódváltozással együtt frissítsd az érintett dokumentációt és a roadmap haladási státuszát. Ne készíts párhuzamos, dátumozott státusznaplót.
7. Ne találgass production állapotot. A production adatbázisról csak friss, read-only lekérdezés alapján állíts tényt.

## Production biztonsági határ

Külön, konkrét jóváhagyás nélkül TILOS:
- production Supabase DDL/DML vagy bármilyen adatírás;
- `supabase db push`, `supabase migration repair`, migration ledger kézi módosítása;
- GRANT/REVOKE, RLS policy vagy Auth user módosítása;
- production Auth/RBAC feature flag bekapcsolása;
- AWS production deploy vagy backup-infrastruktúra módosítása;
- új Supabase projekt vagy branch létrehozása;
- PR merge.

A production projekt read-only állapotának vizsgálata nem ad engedélyt írásra. Titkot, tokent, connection stringet, személyes adatot ne tegyél Gitbe, logba vagy dokumentációba.

## Ellenőrzés

- Tesztfüggőségek: `python -m pip install -r requirements-test.txt`
- Szintaxis: `python -m compileall -q .`
- Tesztek: `python -m pytest -q`
- Adatbázis migrációs és pgTAP tesztek: a `.github/workflows/ci.yml` által létrehozott izolált PostgreSQL 17 környezetben.
- Live Auth/JWT/RLS smoke kizárólag már létező, kifejezetten engedélyezett izolált Supabase környezetben futhat; productionre soha.

Ne állíts sikeres tesztet pusztán azért, mert a workflow elindult. A futásnak a vizsgált commiton befejezett `success` eredményűnek kell lennie.

## Dokumentumok – egyetlen forrás minden témához

- `docs/JARVIS_DEVELOPMENT_ROADMAP.md`: elsőként olvasandó, elsődleges fejlesztési sorrend és haladás.
- `README.md`: rövid projektismertető, telepítés, dokumentációs belépő.
- `docs/JARVIS_DOCUMENTATION.md`: jelenlegi képességek, architektúra, modulok, működési korlátok.
- `docs/PRODUCTION_STATE_AND_MIGRATION_PLAN.md`: production tények, migrációs drift, backup, Auth/RLS kapuk.
- `docs/DEVELOPMENT_REVIEW_AND_RECOMMENDATIONS.md`: részletes technikai backlog az elsődleges roadmaphez igazítva.
- `docs/REMAINING_WORK_AND_RELEASE_GATES.md`: kizárólag production/release engedélyezési kapuk.
- `docs/CURRENT_STATE_AND_NEXT_STEPS.md`: aktuális, egyetlen helyen karbantartott állapot és következő lépések.

A PR-állapotot, CI-eredményeket és dátumozott pillanatfelvételeket ne másold több dokumentumba. Hivatkozz a GitHub Actions futásra vagy frissítsd a megfelelő központi dokumentumot.
