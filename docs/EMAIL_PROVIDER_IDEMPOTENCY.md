# JARVIS – e-mail és provider állapot

**Aktuális állapot:** a kimenő e-mail küldés kódszinten hard-disabled. Ez a dokumentum a repositoryban lévő adaptereket és biztonsági korlátokat írja le; nem jelent élő provider kapcsolatot vagy engedélyezett küldést.

## 1. Kimenő e-mail állapota
- Az email_sender.py tartalmaz SMTP és Resend adapterkódot.
- A chatből indított e-mail külön tervezetet készíthet, megmutathatja a pontos címzettet, tárgyat és törzset, majd jóváhagyást kérhet.
- A küldő kódban az EMAIL_DELIVERY_ENABLED = False konstans miatt a küldés leáll; környezeti változóval nem oldható fel.
- A .github/workflows/email-automation.yml outbound küldési lépése if: false miatt tiltott.
- Provider live E2E, valós SMTP kapcsolat és küldés nem igazolt. Ne tekintsd a konfigurációs kulcsok meglétét bizonyított működésnek.
- A JARVIS jelenleg nem küld kimenő e-mailt. Ne kérj vagy jeleníts meg jelszót, alkalmazásjelszót vagy API-kulcsot.

## 2. Provider és idempotencia
A Resend adapter kódban elérhető, és stabil üzleti operation ID-t használhat Idempotency-Key fejlécben. SMTP esetén nincs provider-oldali deduplikációs garancia. A workflow/provider konfiguráció és a kódbeli adapterek megléte nem bizonyítja, hogy bármelyik provider aktívan hitelesített vagy használatban van.

## 3. Bizonytalan kimenetel
A hálózati timeout, 409/429/5xx, illetve hiányzó/érvénytelen provider message ID bizonytalan kézbesítési kimenetelt eredményezhet. Ilyen esetben az állapot unknown, automatikus újraküldés tilos. Előbb a provider eseményeivel kell egyeztetni, és csak bizonyított nem-kézbesítés után lehet új műveletet tervezni.

## 4. Inbound inbox
Az inbound IMAP monitor a kimenő küldéstől külön funkció. Az email_inbox.py a EMAIL_INBOX_MONITOR_ENABLED kapcsolót ellenőrzi; a GitHub workflow külön inbox ellenőrzést indíthat konfigurált környezetben. Ez sem bizonyítja, hogy folyamatos worker vagy production JARVIS app fut. Az inbox titkokat ne tedd repóba vagy chatbe.

## 5. Feloldási feltételek
A kimenő hard-disable nem oldható fel pusztán secret vagy környezeti változó beállításával. Szükséges:
1. Provider és feladói identitás külön döntése.
2. Külön engedélyezett tesztkörnyezet.
3. Stabil üzleti idempotency key és payload-stabilitás.
4. Provider-elfogadás, message ID, unknown és retry viselkedés E2E tesztje.
5. Audit fail-closed és duplikált küldést kizáró ellenőrzés.
6. Külön security review és konkrét felhasználói jóváhagyás a kódbeli tiltás, majd a workflow lépés feloldására.

## 6. Kapcsolódó dokumentumok
- [JARVIS parancs- és kifejezéskalauz](JARVIS_COMMAND_GUIDE.md) – a chat e-mail kérésének korlátai.
- [Production állapot és migrációs terv](PRODUCTION_STATE_AND_MIGRATION_PLAN.md).
- [Release gate-ek](REMAINING_WORK_AND_RELEASE_GATES.md).

**Biztonsági megjegyzés:** sem valódi e-mailküldés, sem secretmódosítás, sem production deploy nem része a dokumentációfrissítésnek.
