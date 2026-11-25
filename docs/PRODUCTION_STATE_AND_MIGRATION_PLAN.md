# Production állapot és migrációs terv

**Állapot dátuma:** 2026-11-25. A séma/ledger tényállás az utolsó dokumentált read-only auditból származik; a production backup/restore ezt követően sikeresen lefutott, production séma módosítás nélkül.
**Production adatbázis:** Supabase PostgreSQL 17, project ref: `kiutreccucbegskxowek`.

## 1. Rövid állapot

- A production projekt elérhető, de a repositoryban lévő audit/RBAC migrációk nincsenek productionben alkalmazva.
- A megfigyelt 8 public tábla RLS-e engedélyezett, de a read-only lekérdezés 0 policy-t talált.
- A megfigyelt production `auth.users` tábla üres volt.
- A `logs` tábla legacy szerkezetű; a strukturált audit- és hash mezők, valamint az `audit_chain_state` hiányoztak.
- A shared-workspace RBAC migráció csak a repositoryban van; productionben nem futott.
- A dashboard Auth/RBAC feature flag maradjon OFF.
- A production változtatásokhoz szükséges migrációs előzmény nincs biztonságosan reconciliálva.

Ezek időponthoz kötött megfigyelések, nem örök érvényű állítások. Módosítás előtt új read-only ellenőrzés szükséges.

## 2. Migration drift

A production remote migration ledger öt olyan korábbi verziót tartalmaz, amelyek SQL-forrása visszakerült a repositoryba:

- `20261119191911_create_jarvis_memory_and_fk_indexes`
- `20261119192040_complete_jarvis_runtime_schema`
- `20261119192145_enable_rls_on_legacy_posts`
- `20261119192412_revoke_anon_authenticated_public_table_and_sequence_privileges`
- `20261119192559_secure_postgres_default_privileges_public_schema`

További eltérések:
- A `20261117090000_add_leads_website.sql` és `20261117100000_add_logs_level.sql` hatásai a production sémában látszottak, de a verzióik nem szerepeltek a megfigyelt remote ledgerben.
- A strukturált audit, hash-chain, shared-workspace RBAC és task-create idempotencia migrációk repository-only állapotúak; productionben nem alkalmazottak.
- A production `settings` integer ID/sequence modellt és legacy `posts` táblát tartalmazott; a történeti adatokat meg kell őrizni.

A CI PostgreSQL 17 fixture a migrációs láncot és a katalógus-postconditionöket teszteli. Ez nem oldja meg a remote ledger és a live séma eltérését.

## 3. Kötelező rendezési sorrend

1. Friss, read-only production schema + migration ledger snapshot készítése.
2. A két 20261117 verzió hiányzó ledger-bejegyzésének okát és biztonságos kezelését pontosan megállapítani. Ne futtasd újra vakon a már látható hatású SQL-t.
3. Az öt visszanyert történeti SQL-forrást, a live postconditionöket és a repo migrációkat függetlenül összevetni.
4. A teljes migrációs láncot production-shape izolált PostgreSQL 17 környezetben próbálni, meglévő adatok megőrzésével.
5. Az audit/RBAC/idempotencia migrációkat és az alkalmazási sorrendet külön SQL review-val jóváhagyni.
6. Valós Auth/JWT/RLS smoke tesztet csak már létező, kifejezetten engedélyezett izolált Supabase környezetben futtatni. Új projektet vagy branch-et ne hozz létre.
7. Csak mindezek után készíts pontos production változtatási tervet, friss ellenőrzött backup mellett. A production DDL végrehajtásához külön, konkrét jóváhagyás kell.
8. Read-only postcondition ellenőrzés, admin Auth user provisioning és feature flag aktiválás külön release lépés, külön engedéllyel.

## 4. Backup állapot

**Friss eredmény (2026-11-25):** a main commit `2e2a97e` alatti workflow-dispatch run `45655512387` teljesen sikeres. A workflow létrehozta az age titkosított production logikai dumpot, feltöltötte privát S3-ba SSE-KMS titkosítással, ellenőrizte a S3 objektum KMS kulcsát és méretét, letöltötte az objektumot, visszafejtette és ellenőrizte a manifest SHA-256 hash-eket, majd az archívumot egy külön, eldobható PostgreSQL 17 konténerbe állította vissza. Az ellenőrzés 8 várt public táblát és a leads/logs/settings rekordszám-lekérdezéseit igazolta. A workflow summary szerint production DB írás nem történt. [Részletes workflow](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45655512387).

Ez a sikeres futás a korábbi, hibás #45652336576 / #45654544915 próbálkozásokat felülírja a backup gate szempontjából. A korábbi sikertelenségek történeti hibák, nem a jelenlegi workflow állapota.



A korábbi, 2026-11-25-i `45611038142` workflow sikeresen titkosította a production logikai adatbázis-dumpot age segítségével, S3-ba töltötte SSE-KMS titkosítással, majd letöltés/visszafejtés/hash ellenőrzést végzett. Ez történeti siker, nem igazolja a legutóbbi main futás eredményét.

A PR #13 merge után indult `45624735241` backup workflow **FAILED**: a `scripts/supabase_backup.py` indításakor `ModuleNotFoundError: No module named 'jarvis_errors'` történt. Emiatt a backup létrehozása, S3-feltöltése és restore lépései nem futottak le. A hiba kódjavítást és új futást igényel.

A sikeres logikai dump sem teljes Supabase platform-mentés: nem tekinthető a Storage bináris objektumok, Auth/Realtime platformadatok, projektbeállítások és titkos platformkulcsok teljes mentésének. A tényleges production archívum külön adatbázisba történő restore-ját külön kell bizonyítani.

## 5. CI állapot a merge után

- Aktuális main commit: `2e2a97e182687c9b9d018da99b87095b75a21054` (PR #20 squash merge).
- Main CI run `45655131500`: sikeres.
- PR #20 CI run `45654575685`: sikeres.
- Main push backup run `45655131449` és kézi workflow-dispatch backup run `45655512387`: sikeres; utóbbi minden ellenőrzési és restore lépése zöld.



- Main commit: `bb5788e94b60a11185c45502b45d351ab2b2189b`.
- A merge utáni CI `45624735367`: mindkét job (`test`, `backup-restore-integration`) befejeződött és sikeres. [GitHub Actions](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/45624735367).
- A merge utáni production backup workflow `45624735241`: sikertelen, a fenti importhiba miatt.
- A CI eredményeket mindig a pontos commit SHA-hoz kösd; ne másold át a korábbi branch vagy régi main futás eredményét.

## 6. Tilos külön jóváhagyás nélkül

- `supabase db push`, `supabase migration repair`, migration ledger kézi módosítása;
- production DDL/DML, GRANT/REVOKE, RLS policy változtatás;
- Auth user létrehozás, szerepkör kiosztás, production Auth/RBAC flag bekapcsolása;
- AWS production deploy vagy backup infrastruktúra módosítása;
- új Supabase projekt vagy branch létrehozása.

A sikeres backup nem oldja meg a migration driftet, és nem engedélyez production DDL-t. A részletes release-engedélyezési feltételek a [release gate dokumentumban](REMAINING_WORK_AND_RELEASE_GATES.md) vannak.
