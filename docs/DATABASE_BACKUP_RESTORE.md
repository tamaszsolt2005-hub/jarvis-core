# JARVIS – adatbázis-mentés és biztonságos visszaállítás

**Állapot:** előkészített kód és automatizmus; külső tárhely-konfiguráció és integrációs próba még szükséges.  
**Éles projektazonosító:** `kiutreccucbegskxowek` (Jarvis, EU West)

## 1. Mit kell menteni?

A teljes alkalmazásadatot és annak sémáját. A 2026-11-20-i élő, csak olvasási ellenőrzéskor a `public` séma nyolc táblát tartalmazott:

| Tábla | Mentési ok |
|---|---|
| `leads` | céges adatok, kapcsolattartási és hozzájárulási állapot |
| `tasks` | feladatok és határidők |
| `email_drafts` | e-mail-tervezetek |
| `logs` | technikai és műveleti naplók/audit |
| `settings` | beállítások és IMAP checkpointok |
| `jarvis_memory` | explicit módon mentett üzleti memória |
| `jarvis_proactive_state` | proaktív monitor technikai állapota |
| `posts` | élő adatbázisban lévő legacy tábla; a repository sémája nem definiálja, de a teljes public dump megőrzi |

Az ellenőrzéskori sorok száma: leads 11, logs 28, settings 1, jarvis_proactive_state 1; a többi felsorolt tábla 0 sort tartalmazott. Ezek időpillanat-felvételek, nem állandó értékek.

A mentés mindig a tényleges adatbázisból készül, nem a GitHub-sémából rekonstruálja az adatokat. A jelenlegi élő séma és a repository `supabase/schema.sql` fájlja között eltérések vannak; ezért a visszaállítás az élő dumpot tekinti adatforrásnak, és nem futtat automatikus éles migrációt.

## 2. Mi nem része ennek a logikai mentésnek?

A Supabase CLI `db dump` a Supabase által kezelt sémákat kizárja. Ez a megoldás ezért nem menti:
- `auth`, `storage`, `realtime` és más platform által kezelt sémák teljes tartalmát;
- Supabase Storage fájlobjektumok bináris tartalmát (a DB-ben tárolt metaadat önmagában nem fájlmentés);
- projektbeállításokat, API-kulcsokat, GitHub Actions/Codespaces titkokat;
- Supabase Vault root encryption key-t vagy egyedi szerepkör-jelszavakat.

A 2026-11-20-i olvasási ellenőrzéskor a `storage.buckets` üres volt, tehát nem volt Supabase Storage bucket. Ha ez változik, a fájlobjektumokra külön mentési folyamat kell.

A Supabase platform napi backup/PITR funkciója a csomagtól függ. A projekt csomagját és a Backups/PITR beállítást nem ellenőriztük. A külső logikai mentés nem helyettesíti a platform backupot.

## 3. Titkosított mentés

A mentési script:

```bash
python scripts/supabase_backup.py backup --output-dir .private-backups
```

Szükséges programok: Supabase CLI, `age`, Python 3.11+. A Supabase CLI Docker-alapú dump futtatást használhat, ezért Docker-kompatibilis runner szükséges. A visszaállításhoz az `age` mellett PostgreSQL `psql` kliens is kell, a szerverrel kompatibilis főverzióban.

Szükséges környezeti beállítások:
- `SUPABASE_DB_URL`: közvetlen vagy session-pooler adatbázis-kapcsolati URL, titokként kezelendő.
- `JARVIS_BACKUP_SOURCE_PROJECT_REF=kiutreccucbegskxowek`: a rögzített forrásazonosító.
- `BACKUP_AGE_RECIPIENT`: az age nyilvános címzettkulcsa; ez nem privát kulcs.

A script:
1. ellenőrzi, hogy a DB URL és a rögzített forrásprojekt az éles JARVIS-projektre mutat;
2. külön SQL-fájlba dumpolja a teljes `public` sémát és adatokat;
3. manifestet készít UTC időbélyeggel, UUID-s mentésazonosítóval és SHA-256 hash-ekkel;
4. a teljes archívumot age nyilvános kulccsal titkosítja;
5. csak a titkosított `.tar.gz.age` fájlt hagyja meg a kimeneti könyvtárban.

A helyi `.private-backups/` és a titkosított mentési kiterjesztések Git-ignore alatt vannak. Mentést semmilyen körülmények között ne commitolj a repositoryba.

## 4. Automatizált mentés – GitHub Actions

Workflow: `.github/workflows/database-backup.yml`  
Ütemezés: naponta 02:15 UTC, valamint kézi indítás.

GitHub Actions **Secrets**:
- `SUPABASE_DB_URL`
- `AWS_BACKUP_ROLE_ARN` (GitHub OIDC-vel felvehető, szűk jogosultságú AWS IAM role ARN)

GitHub Actions **Variables**:
- `JARVIS_BACKUP_SOURCE_PROJECT_REF` = `kiutreccucbegskxowek`
- `BACKUP_AGE_RECIPIENT`
- `BACKUP_AWS_REGION`
- `BACKUP_S3_BUCKET`

A workflow hiányzó beállítás esetén kihagyja a mentést, és jelzést tesz a futás összefoglalójába. Ha minden konfiguráció rendelkezésre áll, rövid életű GitHub OIDC hitelesítéssel lép be az AWS role-ba, majd a titkosított fájlt a privát S3 bucket `jarvis/database/` prefixébe tölti. Hosszú életű AWS access key/secret key nincs a workflow-ban.

**Még beállítandó az S3 szolgáltatónál:**
- privát bucket, nyilvános hozzáférés teljes tiltása;
- külön IAM-felhasználó/role, csak a szükséges bucket/prefix jogosultságokkal;
- bucket versioning;
- 30 napos lifecycle/retention szabály (vagy a szervezeti igénynek megfelelő idő);
- titkosítás és hozzáférési naplózás a szolgáltató oldalán.

A workflow nem hoz létre bucketet, nem konfigurál IAM-et, versioninget vagy lifecycle szabályt. A GitHub Actions artifact nem a tartós adatbázis-mentési tárhely.

Az age privát visszafejtő kulcsát a backup bucket-től és GitHub repositorytól elkülönítve kell őrizni (pl. offline titokkezelőben). A nyilvános recipient kulcs nem alkalmas visszafejtésre.

## 5. Visszaállítás – kizárólag elkülönített, üres célprojektbe

A visszaállítás **nem használható éles helyreállításra**. Az éles projektazonosító kódszinten tiltott.

Előfeltételek:
- külön Supabase tesztprojekt, amelynek azonosítója nem az éles projekt;
- a célprojekt `public` sémája teljesen üres;
- külön cél DB URL;
- `--confirm-restore` explicit kapcsoló;
- az age privát kulcs fájlja, amelynek útvonalát az `AGE_IDENTITY_FILE` változó tartalmazza; POSIX rendszeren a fájl jogosultsága legfeljebb 0600 lehet;
- `JARVIS_RESTORE_ALLOWED_PROJECT_REF` értéke pontosan a jóváhagyott sandbox projektazonosító.

Példa:

```bash
export JARVIS_RESTORE_DB_URL='postgresql://...'
export JARVIS_RESTORE_ALLOWED_PROJECT_REF='A_KULON_SANDBOX_PROJECT_REF'
export AGE_IDENTITY_FILE='/secure/path/age-identity.txt'

python scripts/supabase_backup.py restore \
  --archive .private-backups/jarvis-db-....tar.gz.age \
  --target-project-ref "$JARVIS_RESTORE_ALLOWED_PROJECT_REF" \
  --confirm-restore
```

A parancs explicit `--confirm-restore` megerősítést követel. A parancs ellenőrzi:
1. a célprojekt nem az éles JARVIS-projekt;
2. a célazonosító egyezik a külön allowlisttel és a DB URL-ben található azonosítóval;
3. a forrás és cél különböző projekt;
4. az archívum pontosan a várt fájlokat tartalmazza;
5. az SQL fájlok SHA-256 értékei egyeznek;
6. a cél public séma nem tartalmaz táblát, nézetet vagy szekvenciát.

A visszaállítás előtt visszavonja az `anon` és `authenticated` szerepkörök új public táblákra öröklődő alapértelmezett jogosultságait. Csak ezután futtatja a sémát és adatokat egyetlen PostgreSQL tranzakcióban, `ON_ERROR_STOP=1` mellett. Nem üres cél esetén a script még SQL-végrehajtás előtt leáll. A sikertelen tranzakció visszagörgethető.

A friss célprojektben a szükséges PostgreSQL-kiterjesztéseket és platformbeállításokat előzetesen ellenőrizni kell. A CLI dump nem másolja át az összes Supabase platformobjektumot vagy egyedi role-jelszót.

## 6. Megőrzés és helyreállítási célok

Javasolt kezdeti szabály: napi mentés, 30 napos S3 megőrzés, bucket versioning, külön offline age privát kulcs. A 30 napos szabály csak akkor tekinthető aktívnak, ha a bucket lifecycle policy ténylegesen be van állítva.

- **RPO:** napi futás mellett elméletileg legfeljebb kb. 24 óra adatvesztés, ha az utolsó mentés sikeres volt; ez nem garantált szolgáltatási érték.
- **RTO:** jelenleg nincs mérve; a tényleges visszaállítási időt sandbox-próbával kell meghatározni.
- A Supabase platform backup/PITR másodlagos helyreállítási lehetőség lehet, a csomagtól és konfigurációtól függően.

## 7. Tesztelés és jelenlegi állapot

A `tests/test_supabase_backup.py` mockolt teszteket tartalmaz:
- direct és pooler URL projektazonosító-felismerés;
- ismeretlen URL elutasítása;
- éles projekt visszaállításának tiltása külső parancs futtatása előtt;
- explicit `--confirm-restore` és sandbox allowlist követelménye;
- nem várt archívumfájlok és sérült hash elutasítása;
- adatbázis-jelszó eltávolítása a parancssori URL-ből és 0600 PGPASSFILE;
- a Supabase `public` séma meglévő objektumainak megtartása, a nem üres sandbox elutasítása.

Ezek egységtesztek, nem készítenek valódi adatbázis-mentést, nem töltenek fel S3-ba, és nem állítanak vissza adatbázist.

**2026-11-20 állapot:** a kód és workflow elő van készítve. Külső AWS/S3 tárhely és GitHub titkok/változók még nincsenek igazolva; sikeres mentési futás, feltöltés, és elkülönített visszaállítási próba még nem történt. Az éles Supabase-adatbázis a felülvizsgálat során csak olvasási műveleteket kapott, nem módosítottuk.
