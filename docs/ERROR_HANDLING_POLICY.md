# JARVIS hibakezelési és naplózási szabályzat

Ez a dokumentum a meglévő `jarvis_errors.report_error()` és a strukturált auditnapló használatát egységesíti. Nem vezet be új adatbázistáblát vagy sémamódosítást.

## Súlyossági szintek

| Szint | Mikor használd | Elvárt vezérlés |
|---|---|---|
| `warning` | Várható, helyreállítható vagy opcionális funkció hibája, amely nem teszi érvénytelenné az aktuális műveletet | A folyamat folytatható; a kihagyott funkciót jelezni kell |
| `error` | Az aktuális művelet nem teljesült, de a többi, attól független munka folytatható | Az érintett műveletet meg kell szakítani; a hívó dönt a folytatásról |
| `critical` | A folyamat biztonságos vagy helyes folytatása nem garantálható, illetve váratlan futási hiba történt | Az aktuális jobot meg kell szakítani, a kivételt tovább kell dobni vagy a jobot nem nulla kóddal kell lezárni |

## Használati szabályok

1. Hibát jelentő, helyreállítási vagy külső I/O műveletnél használd a `report_error(error, module=..., operation=..., severity=..., db=...)` függvényt.
2. A jelentés tartalmazzon stabil modul- és műveletnevet. A kivételt ne alakítsd át olyan általános szöveggé, amely elveszíti a diagnosztikai értéket.
3. A központi jelentés helyi naplózása az elsődleges fallback. A Supabase `logs` írása best-effort; a naplózási hiba nem okozhat rekurzív hibajelentést.
4. A `warning` nem használható egy sikertelen, kötelező üzleti művelet elrejtésére. A `critical` nem jelenti automatikusan az egész alkalmazás leállítását: az aktuális háttérfeladatot kell biztonságosan megszakítani.
5. Input-validációs elutasítás, normális hiányzó opcionális konfiguráció és erőforrás-takarítás közben kezelt kivétel önmagában nem feltétlenül rendszerhiba. Az ilyen kivételeket csak akkor naplózd hibaként, ha működési hibát jeleznek.
6. Alacsony szintű könyvtári segédfüggvények (például HTTP-kliens) a kivételt továbbdobhatják; a műveletet indító réteg felel a központi jelentésért. Ne naplózd ugyanazt a kivételt minden rétegben.
7. Érzékeny külső művelet előtt a kötelező auditbejegyzésnek sikerülnie kell. Ha a pending audit mentése sikertelen, a műveletet blokkolni kell. A már elküldött e-mail utólagos audit-hibája nem indokol automatikus újraküldést; az állapotot bizonytalanként kell kezelni.
8. A hibakezelés soha nem kerülheti meg a jóváhagyást, hozzájárulást, jogosultság-ellenőrzést, célprojekt-ellenőrzést vagy fail-closed védelmet.
9. Soha ne naplózz nyers jelszót, tokent, API-kulcsot, teljes hitelesített URL-t, e-mail-törzset vagy teljes külső parancssort. A `sanitize_log_text()` csökkenti a kockázatot, de nem garantálja minden ismeretlen titokformátum felismerését.
10. Új vagy módosított hibakezeléshez írj izolált tesztet: ellenőrizd a jelentés metaadatait, a titokmaszkolást, a kivétel továbbdobását és azt, hogy a biztonsági kapuk hibánál zárva maradnak.

## Éles integrációk

A normál CI tesztjei izolált/fake szolgáltatásokat használjanak. Éles Supabase-, SMTP- vagy külső API-integrációt csak külön, explicit tesztkörnyezetben és dedikált, minimális jogosultságú tesztadatokkal szabad futtatni. Éles adatbázisba író vagy éles e-mailt küldő teszt nem része a normál CI-nek.
