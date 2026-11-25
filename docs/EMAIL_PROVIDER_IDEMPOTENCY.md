# JARVIS – e-mail provider és idempotencia

## Állapot és kiválasztott küldési út

A JARVIS meglévő Gmail-fiókját használjuk a kimenő levelek feladójaként, a már implementált Gmail SMTP útvonalon. Saját domain és Resend-fiók nem szükséges ehhez a megoldáshoz.

- A `.github/workflows/email-automation.yml` workflow `EMAIL_PROVIDER=smtp` értéket állít be.
- A küldő kód alapértelmezett SMTP-végpontja `smtp.gmail.com:587`; STARTTLS-t használ.
- Szükséges GitHub Actions repository secret nevek: `EMAIL_USER` (a JARVIS-ban már megadott Gmail-cím) és `EMAIL_PASSWORD` (a Gmail-fiókhoz generált alkalmazásjelszó, ha a Google-fiók beállításai ezt támogatják/megkövetelik). Az értékeket soha ne tedd kódba vagy chatbe.
- Opcionális SMTP felülírások: `SMTP_HOST`, `SMTP_PORT`; Gmailhez az alapértelmezések megfelelőek.
- A bejövő IMAP monitor külön konfigurációt használhat (`IMAP_HOST`, `IMAP_PORT`).
- A Resend adapter a kódban megmarad alternatívaként, de a JARVIS jelenlegi küldési útvonalának nem része; domainhitelesítést és `RESEND_API_KEY`-t nem kérünk ehhez a Gmail-megoldáshoz.
- `EMAIL_DELIVERY_ENABLED = False` – kódszintű, környezeti változóval nem feloldható tiltás.
- Az outbound workflow-lépés továbbra is `if: false`.
- Nem történt valódi SMTP-kapcsolat, live küldés vagy GitHub secretmódosítás.

## Működés

Az email_sender.email_idempotency_key determinisztikus UUID-t képez:
- első kapcsolat: lead ID + first-contact:1;
- follow-up: lead ID + aktuális follow-up sorszám.

A kulcs az audit operation_id mezőjében is szerepel, és Resend használatakor az API Idempotency-Key fejlécébe kerül. A follow_up.py legacy útvonal ugyanazt a helper függvényt használja. A Resend API-t a meglévő requests dependency hívja, új SDK vagy másik alkalmazás nem került a projekthez.

A provider visszaadott message ID-ja kerül a lead állapotába és a sikeres auditbejegyzésbe.

## Hibakezelés

| Eset | Kezelés |
|---|---|
| Resend 2xx és érvényes message ID | Sikeres provider acceptance |
| 4xx elutasítás (kivéve 409/429) | Ismert hiba; nem tekintjük elküldöttnek |
| 409 | Bizonytalan: lehet párhuzamos azonos kulcsú kérés vagy eltérő payload |
| 429 / 5xx | Konzervatívan bizonytalan |
| Hálózati exception / timeout | Bizonytalan |
| 2xx, de hiányzó/olvashatatlan message ID | Bizonytalan |

A bizonytalan kimenetel send_unknown vagy followup_unknown állapotot eredményez. Automatikus retry nincs. Ne állítsd vissza a leadet new / sent állapotba provider-oldali egyeztetés nélkül.

## 24 órás korlát

A Resend dokumentációja szerint az idempotenciakulcsok 24 óráig vannak megőrizve. Ugyanazon kulcs és ugyanazon payload ismétlése visszaadja az eredeti eredményt; ugyanazon kulcs eltérő payloadhoz 409-et adhat. 24 óra után a provider-oldali deduplikáció nem garantált.

Ezért:
1. A send_unknown állapotot nem szabad automatikusan újrapróbálni.
2. 24 órán belüli kézi retry előtt ellenőrizni kell a Resend dashboard/API eseményeit és az eredeti payload azonosságát.
3. 24 órán túl nem szabad az idempotency key-re hagyatkozni; a provider eseményekkel kell egyeztetni, és csak bizonyított nem-kézbesítés után szabad új műveletet indítani.

Források:
- [Resend – Idempotency Keys](https://resend.com/changelog/idempotency-keys)
- [Resend – API OpenAPI definition](https://github.com/resend/resend-openapi/blob/main/resend.yaml)

## Gmail SMTP ellenőrzési lista (küldés továbbra is tiltva)

- [x] A GitHub Actions repository `EMAIL_USER` és `EMAIL_PASSWORD` secretneveinek meglétét a repo tulajdonosa ellenőrizte. Ez nem igazolja a secretértékek helyességét vagy a Gmail SMTP-kapcsolat működését.
- [ ] A `EMAIL_USER` a JARVIS-ban használt Gmail-cím legyen.
- [ ] Ha a Google-fiók megköveteli, külön Google App Password legyen létrehozva, és annak értéke kerüljön az `EMAIL_PASSWORD` secretbe. Ne használd a normál Google-fiók jelszavát, és ne oszd meg a titkot chatben.
- [ ] Inbound IMAP-hoz ellenőrizni az `IMAP_HOST`, `IMAP_PORT` és `EMAIL_INBOX_MONITOR_ENABLED` beállításokat; ez a küldéstől független.
- [ ] Külön, jóváhagyott tesztkörnyezetben ellenőrizni a Gmail SMTP hitelesítést és a küldés eredményét, mielőtt bármilyen éles küldési kapcsoló feloldására sor kerülne.
- [ ] Külön security review és konkrét jóváhagyás szükséges a kódbeli hard-disable, majd külön az outbound workflow step feloldásához.

A workflow provider-választása és a dokumentáció Gmail SMTP-re van igazítva. A secretnevek megléte ellenőrzött, de a titkos értékeket nem olvastuk ki, nem módosítottuk, és SMTP-kapcsolatpróba/live küldés nem történt. A `EMAIL_DELIVERY_ENABLED = False` hard-disable és az outbound workflow `if: false` feltétel változatlan. Nem történt deploy, Supabase migráció vagy jogosultságváltoztatás.
