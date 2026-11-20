# GitHub Codespaces – e-mail környezet beállítása

## Állapot

2026-11-20-án a `jarvis-core` GitHub-repozitórium Codespaces környezetében az alábbi négy környezeti változó jelenlétét ellenőriztük:

- `EMAIL_USER`
- `EMAIL_PASSWORD`
- `EMAIL_DELIVERY_ENABLED`
- `CHAT_EMAIL_ENABLED`

Mind a négy változó **BEÁLLÍTVA** eredményt adott a Python `os.getenv()` ellenőrzésében, a Codespaces konténer újraépítése után.

A titkok tényleges értékei nem kerültek a dokumentációba, és nem szabad őket Gitbe feltölteni.

## Beállítás és frissítés

1. A GitHub-repozitóriumban nyisd meg a **Settings → Secrets and variables → Codespaces** részt.
2. A szükséges értékeket Repository secretként állítsd be.
3. Ha a Codespace már futott a titkok létrehozásakor vagy módosításakor, indítsd újra vagy építsd újra a Codespaces konténert, hogy a változók betöltődjenek.
4. A jelenlétüket az alábbi paranccsal ellenőrizheted. A parancs csak azt írja ki, hogy egy változó be van-e állítva; az értékét nem jeleníti meg.

```bash
python - <<'PY'
import os

for name in [
    "EMAIL_USER",
    "EMAIL_PASSWORD",
    "EMAIL_DELIVERY_ENABLED",
    "CHAT_EMAIL_ENABLED",
]:
    print(f"{name}: {'BEÁLLÍTVA' if os.getenv(name) else 'HIÁNYZIK'}")
PY
```

## JARVIS indítása

A projekt gyökérkönyvtárából:

```bash
streamlit run dashboard.py
```

## Fontos biztonsági megjegyzések

- Soha ne másold be a titkok értékét terminálkimenetbe, chatbe vagy dokumentációba.
- A `EMAIL_DELIVERY_ENABLED` és `CHAT_EMAIL_ENABLED` bekapcsolása önmagában nem bizonyítja, hogy az e-mail-küldés biztonságosan tesztelhető.
- Valódi e-mail küldése előtt ellenőrizni kell, hogy a tesztelés címzettje megfelelően korlátozott-e, és hogy a küldés csak a felhasználó kifejezett jóváhagyásával történhet.
- A háttérben futó automatikus e-mail-küldés és postaláda-figyelés kapcsolóit (`AUTO_SEND_ENABLED`, `EMAIL_INBOX_MONITOR_ENABLED`) a kezdeti chat-e-mail teszt során hagyd kikapcsolva.
- A jelen dokumentum a környezeti változók jelenlétét rögzíti; nem igazolja az SMTP/IMAP kapcsolatot vagy a tényleges e-mail kézbesítést.
