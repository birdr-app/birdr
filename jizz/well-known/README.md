# Deep links: App Links / Universal Links

Bestanden in deze map worden geserveerd op:
- `https://birdr.pro/.well-known/apple-app-site-association` (iOS Universal Links)
- `https://birdr.pro/.well-known/assetlinks.json` (Android App Links)

Zodat `https://birdr.pro/join/<token>` en `https://birdr.pro/join/challenge/<token>` in de Motmot-app openen in plaats van in de browser.

## "Deze URL is een deep link met problemen" / Resultaat: Webbrowser

Als de link in de **browser** opent in plaats van in de app, controleer het volgende.

### Algemeen (beide platforms)

- Beide URLs moeten via **HTTPS** bereikbaar zijn, **zonder redirect**.
- Content-Type moet `application/json` zijn (Django doet dit al).

### Android (assetlinks.json)

1. **SHA256-certificaat** in `assetlinks.json` moet exact overeenkomen met het certificaat waarmee de app is ondertekend.
   - **Release:** het certificaat waarmee je de Play Store-build ondertekent.
   - **Debug:** SHA256 van je debug-keystore.
   - Lokaal fingerprint tonen: `cd mobile/android && ./gradlew signingReport` → kopieer de SHA256 (met dubbele punten, bijvoorbeeld `EF:F1:D0:...`).
2. Als je een **nieuwe keystore** of een **andere build-variant** gebruikt, voeg die fingerprint toe aan het `sha256_cert_fingerprints`-array in `assetlinks.json`.
3. Na wijziging: deploy naar birdr.pro; daarna kan het even duren tot Android de file opnieuw ophaalt. Testen: Instellingen → Apps → Motmot → Open by default / Supported web addresses.

### iOS (apple-app-site-association)

1. **appID** in het bestand moet `TEAM_ID.bundleIdentifier` zijn (bijv. `Z886G5H7D2.pro.birdr.app`). Team ID staat in Apple Developer.
2. In de app: **Associated Domains** entitlement met `applinks:birdr.pro` (staat al in `mobile/app.json` onder `ios.associatedDomains`).
3. Apple cached de AASA; na deploy kan het 24–48 uur duren. Voor snelle test: app verwijderen en opnieuw installeren.
4. **Paths:** `/join/*` en `/join/challenge/*` dekken zowel spel- als challenge-joinlinks.
5. **Gedeelde spellen (`/s/*`) staan bewust nog niet in de AASA.** Oudere app-versies kunnen gedeelde spellen niet openen; zonder `/s/*` opent de link op iPhone de webversie (die volledig werkt). Voeg `"/s/*"` aan `paths` toe zodra de meeste iPhone-gebruikers op de versie met gedeelde spellen zitten. Android claimt `/s/` al via de manifest van die versie, dus oudere Android-apps openen de link in de browser.

### Handmatig testen

- **iOS:** Lange druk op link in Notes/Mail → “Open in Motmot”. Of link in Safari openen; als Universal Links goed staan, opent de app.
- **Android:** Link in Chrome openen; als App Links geverifieerd zijn, opent de app of krijg je een keuzemenu. Controleer onder Instellingen → Apps → Motmot → “Open supported links”.
