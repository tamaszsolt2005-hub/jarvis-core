# JARVIS projektállapot

**Utolsó dokumentációs frissítés:** 2026-11-18  
**Repository:** `tamaszsolt2005-hub/jarvis-core` · **Branch:** `main`

Ez a dokumentum a jelenlegi kódbázis és az elérhető CI-eredmények alapján választja szét az elkészült funkciókat azoktól, amelyek éles környezetben még kipróbálandók.

## Elkészült és automatizáltan tesztelt

- Prémium sötét Streamlit dashboard-téma és egyedi chat-workspace megjelenés.
- Központi Gemini-kliens és modellkonfiguráció; alapértelmezett modell: `gemini-3.8-flash`.
- Gemini átmeneti túlterhelésének kezelése korlátozott újrapróbálkozással és fallback modellel.
- Globális, forrásokra támaszkodó céges leadkutatás, vállalati adatokra korlátozott mentéssel.
- Külön kezelt weboldal-információs pontszám és üzleti illeszkedési becslés.
- Kutatási prioritás, piaci összesítés és napi vezetői jelentés.
- Kifejezett utasítással működő JARVIS-memória és strukturált üzleti tanulómemória.
- Jóváhagyáshoz kötött célpiacváltás, leadkutatás és feladatkezelés.
- Olvasásközpontú Supabase-adatkezelés és read-only rendszerdiagnosztika.
- Biztonságos weboldal-lekérési segéd: nyilvános IP-ellenőrzés, IP-rögzítés, átirányítás tiltása és időkorlát.
- Az e-mail-küldés kódszinten letiltva; a napi jelentés artifactként készül, nem e-mailben.
- Titokkonfigurációs súgó és Supabase-jogosultság-diagnosztika pontosítva.

## Legutóbbi automatikus ellenőrzés

| Ellenőrzés | Eredmény |
|---|---|
| GitHub Actions workflow | JARVIS CI #296 |
| Commit | `143f9af3ed2f45eaf91b0e962517fdfd4f929d84` |
| Függőségek telepítése | Sikeres |
| `python -m compileall -q .` | Sikeres |
| `python -m pytest -q` | **130 passed** |
| Workflow összesített állapota | **success** |

A CI automatizált kód- és tesztellenőrzés. Nem igazolja a valódi API-kulcsok érvényességét, a Supabase-séma telepítettségét vagy a teljes felhasználói folyamatot.

## Konfiguráció

A felhasználó visszajelzése szerint a Codespaces-ben rendelkezésre áll:

- `GEMINI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

A dashboard indításához a `JARVIS_DASHBOARD_PASSWORD` is szükséges. A napi GitHub Actions workflow-k külön GitHub Actions Secrets konfigurációt igényelnek; a Codespaces Secrets nem öröklődik automatikusan az Actions futtatókörnyezetbe. A titkok értékét soha ne commitold, és ne oszd meg chatben.

## Következő ellenőrzési lépések

1. A dashboardban futtasd a beépített rendszerdiagnosztikát.
2. Ellenőrizd, hogy a Gemini próbakérés sikeres-e.
3. Ellenőrizd a Supabase-kapcsolatot, a szükséges táblákat és oszlopokat (`leads.website`, `logs.level`).
4. Próbáld végig a dashboardot: bejelentkezés, természetes nyelvű kérdés, leadlista/elemzés, jóváhagyási előnézet.
5. Külön ellenőrizd a GitHub Actions napi workflow-it és az artifactokat.

## Tudatosan korlátozott / nem bekapcsolt funkciók

- Automatikus e-mail-küldés nincs; a küldés kódszinten tiltott.
- A leadkutatásból származó új cégek nem kapnak automatikus kapcsolatfelvételi engedélyt.
- A CI nem végez valódi Gemini- vagy Supabase-hívásokat.
- A napi workflow-k GitHub Actions titkok nélkül nem tudnak éles adatbázis-műveletet végezni; a Codespaces titkok önmagukban nem elegendők ehhez.
