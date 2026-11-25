# JARVIS – e-mail provider és idempotencia

## Állapot

A Resend HTTPS API adapter implementálva van a PR #26 branchben. Ez **nem** jelenti a kimenő e-mail engedélyezését.

- EMAIL_DELIVERY_ENABLED = False – kódszintű, környezeti változóval nem feloldható tiltás.
- .github/workflows/email-automation.yml – az outbound step továbbra is if: false.
- EMAIL_PROVIDER=resend és RESEND_API_KEY env/secret mapping előkészítve.
- Nem történt Resend API-hívás, live küldés, secretmódosítás vagy feladói domain-ellenőrzés.

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

## Aktiválás előfeltételei

- [ ] GitHub Actions RESEND_API_KEY secret tényleges beállítása (az értéket ne tedd commitba vagy chatbe).
- [ ] Az EMAIL_USER feladói domain ellenőrzése a Resend fiókban.
- [ ] Kontrollált staging/live E2E: sikeres küldés, ugyanazon kulcs/payload replay, eltérő payload 409, timeout/unknown kezelés.
- [ ] Audit és lead állapot egyeztetés bizonyítása.
- [ ] Külön security review és konkrét jóváhagyás a kódbeli hard-disable, majd külön az outbound workflow step feloldására.

Egyik előfeltétel sem teljesül automatikusan a PR merge-étől. Production deploy, Supabase migráció, Auth/RLS vagy GRANT/REVOKE módosítás nem része ennek a provider adapternek.
