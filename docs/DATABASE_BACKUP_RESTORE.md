# JARVIS – adatbázis-mentés és biztonságos visszaállítás

**Állapot:** előkészített kód és automatizmus; külső tárhely-konfiguráció és integrációs próba még szükséges. A 2026-11-23-i read-only ellenőrzés frissítette az adatleltárt.  
**Éles projektazonosító:** `kiutreccucbegskxowek` (Jarvis, EU West)

## 1. Mit kell menteni?

A teljes alkalmazásadatot és annak sémáját. A 2026-11-23-i élő, csak olvasási ellenőrzéskor a `public` séma nyolc táblát tartalmazott:

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

Az ellenőrzéskori becsült sorok száma: `leads` 11, `logs` 28, `settings` 1, `jarvis_proactive_state` 1; a többi felsorolt tábla 0 sort tartalmazott. A `storage.buckets` lekérdezés 0 bucketet adott vissza. Ezek időpillanat-felvételek, nem állandó értékek. A Supabase `auth.users` táblában a vizsgálatkor 0 rekord volt; az Auth-séma továbbra sem része a logikai mentésnek.

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

Szükséges programok: PostgreSQL 17-kompatibilis `pg_dump`, `pg_restore` és `psql`, `age`, Python 3.11+. A mentés egyetlen custom-format `pg_dump` snapshotból készül; a sémát és adatokat ebből a változatlan archívumból bontja ki a `pg_restore`, így a két SQL-fájl ugyanahhoz az MVCC-pillanatképhez tartozik. Docker és Supabase CLI nem szükséges.

Szükséges környezeti beállítások:
- `SUPABASE_DB_URL`: közvetlen vagy session-pooler adatbázis-kapcsolati URL, titokként kezelendő.
- `JARVIS_BACKUP_SOURCE_PROJECT_REF=kiutreccucbegskxowek`: a rögzített forrásazonosító.
- `BACKUP_AGE_RECIPIENT`: az age nyilvános címzettkulcsa; ez nem privát kulcs.

A script:
1. ellenőrzi, hogy a DB URL és a rögzített forrásprojekt az éles JARVIS-projektre mutat;
2. egyetlen konzisztens custom-format PostgreSQL-pillanatképet készít, majd ebből külön SQL-fájlba bontja a teljes `public` sémát és adatokat;
3. manifestet készít UTC időbélyeggel, UUID-s mentésazonosítóval és SHA-256 hash-ekkel;
4. a teljes archívumot age nyilvános kulccsal titkosítja;
5. csak a titkosított `.tar.gz.age` fájlt hagyja meg a kimeneti könyvtárban.

A helyi `.private-backups/` és a titkosított mentési kiterjesztések Git-ignore alatt vannak. Mentést semmilyen körülmények között ne commitolj a repositoryba.

## 4. AWS/S3 infrastruktúra és GitHub Actions

Workflow: `.github/workflows/database-backup.yml`  
Ütemezés: naponta 02:15 UTC, valamint kézi indítás.  
A workflow rögzített `ubuntu-24.04` runneren fut, és a PGDG tárolóból telepített PostgreSQL 17 `pg_dump`, `pg_restore` és `psql` binárisok verzióját futás előtt ellenőrzi; ez illeszkedik az ellenőrzött éles PostgreSQL 17.11 szerverhez.

### 4.1. AWS erőforrások létrehozása

Az infrastruktúra CloudFormation sablonja: [`infra/aws-backup-stack.yaml`](../infra/aws-backup-stack.yaml). A sablon a következőket hozza létre:
- privát S3 bucket teljes public-access blokkolással és Bucket Owner Enforced tulajdonosi móddal;
- S3 versioning és 30 napos lifecycle a `jarvis/database/` prefix alatt;
- saját, automatikus kulcsrotációval ellátott KMS kulcs és alias;
- GitHub OIDC provider (vagy megadható már létező provider ARN);
- IAM role, amely csak a megadott repository `main` ágának GitHub Actions tokenjét fogadja el, és csak a backup prefixre enged feltöltést, a megadott KMS kulccsal.

AWS Console → CloudFormation → Create stack → With new resources (standard) → töltsd fel a sablont. A `GitHubRepository` alapértéke `tamaszsolt2005-hub/jarvis-core`, a `GitHubBranch` értéke `main`. Ha az AWS-fiókban már van `token.actions.githubusercontent.com` OIDC provider, annak ARN-jét add meg az `ExistingGitHubOidcProviderArn` paraméterben; különben hagyd üresen, és a stack létrehozza.

A stack létrehozása után mentsd ki az Outputs értékeit:
- `BackupBucketName`
- `BackupKmsKeyArn`
- `GitHubBackupRoleArn`

A stack AWS-fiókban történő telepítése még nincs végrehajtva. A sablon csak a repositoryban található.

### 4.2. GitHub Actions beállítások

A repository Settings → Secrets and variables → Actions alatt:

GitHub Actions **Secrets**:
- `SUPABASE_DB_URL`: a JARVIS Supabase adatbázis-kapcsolati URL-je, jelszóval együtt; kizárólag GitHub Secretként add meg.
- `AWS_BACKUP_ROLE_ARN`: a CloudFormation `GitHubBackupRoleArn` outputja.

GitHub Actions **Variables**:
- `JARVIS_BACKUP_SOURCE_PROJECT_REF` = `kiutreccucbegskxowek`
- `BACKUP_AGE_RECIPIENT` = az age nyilvános recipient kulcsa
- `BACKUP_AWS_REGION` = az AWS régió, ahol a stack létrejött
- `BACKUP_S3_BUCKET` = a CloudFormation `BackupBucketName` outputja
- `BACKUP_S3_KMS_KEY_ARN` = a CloudFormation `BackupKmsKeyArn` outputja

A workflow hiányzó beállítás esetén kihagyja a mentést, és jelzést tesz a futás összefoglalójába. Teljes konfiguráció esetén rövid életű GitHub OIDC hitelesítéssel lép be az AWS role-ba, majd az age-gel titkosított fájlt a privát S3 bucket `jarvis/database/` prefixébe tölti fel, a customer-managed KMS kulccsal. Hosszú életű AWS access key/secret key nincs a workflow-ban.

A GitHub repository titkait a rendelkezésre álló GitHub-kapcsolat nem tudja írni vagy olvasni; ezeket a repository beállításainál kell megadni. Soha ne küldd el a DB URL-t vagy jelszót a chatben.

### 4.3. Első próba

1. Először ellenőrizd, hogy a CloudFormation stack állapota `CREATE_COMPLETE`.
2. Ellenőrizd a bucket public-access block, versioning, default KMS encryption és lifecycle beállításait.
3. Add meg a GitHub Secret/Variables értékeket.
4. Actions → JARVIS encrypted database backup → Run workflow.
5. Ellenőrizd, hogy a futás sikeres, és a privát bucket `jarvis/database/` prefixében megjelent a `.tar.gz.age` fájl.
6. Ellenőrizd, hogy a feltöltött objektum SSE-KMS titkosítást használ, és a várt KMS kulcs ARN-jével készült.
7. A visszafejtő age privát kulcsot offline, a GitHubtól és az S3 buckettől elkülönítve őrizd.

A javasolt kezdeti megőrzés 30 nap. Ezt a CloudFormation lifecycle szabály konfigurálja, de csak a stack sikeres telepítése után aktív. A GitHub Actions artifact nem a tartós adatbázis-mentési tárhely.

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

A friss célprojektben a szükséges PostgreSQL-kiterjesztéseket és platformbeállításokat előzetesen ellenőrizni kell. A PostgreSQL logikai dump nem másolja át az összes Supabase platformobjektumot vagy egyedi role-jelszót.

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
- adatbázis-jelszó eltávolítása a parancssori URL-ből, külső folyamatok környezetének szűk allowlistje (nem öröklődnek a JARVIS API-kulcsai vagy Supabase service-role titkai), és 0600 age identity fájl;
- a Supabase `public` séma meglévő objektumainak megtartása, a nem üres sandbox elutasítása.

Ezek egységtesztek, nem készítenek valódi adatbázis-mentést, nem töltenek fel S3-ba, és nem állítanak vissza adatbázist. A tesztek külön ellenőrzik, hogy a séma és az adatok ugyanabból az egyetlen `pg_dump` snapshotból származnak, és a DB URL-t tartalmazó környezeti változók nem öröklődnek tovább a külső folyamatokba. A mentési modul mockolt biztonsági tesztjei a teljes CI-futtatás részeként futnak; a legfrissebb futás eredményét a PR Actions ellenőrzése mutatja.

**2026-11-23 állapot:** a kód és workflow elő van készítve. Külső AWS/S3 tárhely és GitHub titkok/változók még nincsenek igazolva; sikeres mentési futás, feltöltés, és elkülönített visszaállítási próba még nem történt. Az éles Supabase-adatbázis a felülvizsgálat során csak olvasási műveleteket kapott, nem módosítottuk.
