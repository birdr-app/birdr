# Google Console setup for in-app Google Sign-In

The app signs in with Google **inside the app** (no browser redirect). You need the right OAuth clients in Google Cloud Console.

## 1. Open Google Cloud Console

- Go to [Google Cloud Console](https://console.cloud.google.com/) and select your project (or create one).
- **APIs & Services** → **Credentials**.

## 2. OAuth consent screen

- **OAuth consent screen**: If not already set, configure the consent screen (User type: External is fine), add your app name and support email.

## 3. Create / use OAuth 2.0 Client IDs

You need **two** client IDs for the mobile app:

### A. Web application client (for ID token and backend)

- **Create** or use an existing **Web application** OAuth 2.0 Client ID.
- This client is used as `webClientId` in the app and by your backend to verify the Google ID token.
- Copy the **Client ID** (e.g. `123456789-xxx.apps.googleusercontent.com`).

**In the app:**

- Set `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` in `.env` (or in `app.config.js` / `app.json` extra and read in `src/api/config.ts`) to this Web client ID.
- In `app.json`, replace `REPLACE_WITH_YOUR_WEB_CLIENT_ID` in the Google Sign-In plugin with the **numeric/hyphen part** of your Web client ID (the part before `.apps.googleusercontent.com`).  
  Example: if your Web client ID is `123456789-abcdefg.apps.googleusercontent.com`, set `iosUrlScheme` to `com.googleusercontent.apps.123456789-abcdefg`.

**Backend:** Your Django app should already be configured to accept ID tokens from this Web client (same project / client ID used to validate the token).

### B. Android client (for native sign-in on Android)

- **Create** an **Android** OAuth 2.0 Client ID.
- **Package name:** `pro.birdr.app` (must match `android.package` in `app.json`).
- **SHA-1 certificate fingerprint:** Add the SHA-1 of the keystore used to sign the app.

**Get SHA-1:**

- **Debug:**  
  `keytool -list -v -keystore android/app/debug.keystore -alias androiddebugkey -storepass android -keypass android`
- **Release:**  
  `keytool -list -v -keystore /path/to/your/release.keystore -alias your-key-alias`

Copy the **SHA-1** line (e.g. `AA:BB:CC:...`) into the Android client in Google Console. You can add both debug and release SHA-1 to the same Android client (add multiple fingerprints if needed).

### C. iOS client (if you build for iOS)

- **Create** an **iOS** OAuth 2.0 Client ID.
- **Bundle ID:** `pro.birdr.app` (must match `ios.bundleIdentifier` in `app.json`).

No SHA-1 for iOS; the bundle ID is enough.

## 4. Summary

| Use case              | Client type | What to set |
|-----------------------|------------|-------------|
| App + backend token   | Web        | `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` and iOS URL scheme in `app.json` |
| Android native sign-in| Android    | Package `pro.birdr.app` + SHA-1 (debug + release) |
| iOS native sign-in    | iOS        | Bundle ID `pro.birdr.app` |

After adding or changing clients, rebuild the app (`npx expo prebuild --clean` then `npx expo run:android` or `run:ios`).

## 5. Troubleshooting

### Fix DEVELOPER_ERROR (Android)

This error means Google could not verify your app: the **SHA-1** of the build you’re running is not registered for the Android OAuth client (or the package name is wrong).

**Step 1 – Get your SHA-1**

From the `mobile/` directory, use either method:

**Option A – keytool (debug build)**  
If you use the default debug keystore at `android/app/debug.keystore`:

```bash
keytool -list -v -keystore android/app/debug.keystore -alias androiddebugkey -storepass android -keypass android
```

**Option B – Gradle (all build types)**  
This prints SHA-1 for debug and release. From `mobile/` run:

```bash
npm run print-sha1
```

or `cd android && ./gradlew signingReport`.

In the output, find **SHA1** under `Variant: debug` (or the variant you run). Copy the value (e.g. `AA:BB:CC:DD:...`).

**Step 2 – Register SHA-1 in Google Cloud**

1. Open [Google Cloud Console](https://console.cloud.google.com/) → **APIs & Services** → **Credentials**.
2. Open your **Android** OAuth 2.0 Client ID (or create one):
   - **Application type:** Android  
   - **Package name:** `pro.birdr.app` (exactly — must match your app).  
   - Under **SHA-1 certificate fingerprint**, click **Add fingerprint** and paste the SHA-1 from Step 1.
3. Save. If the client is new, wait a few minutes for changes to apply.

**Step 3 – Rebuild and run**

```bash
cd mobile
npx expo run:android
```

Use the same keystore you used to get the SHA-1 (e.g. don’t switch from local debug to EAS build without adding EAS’s SHA-1 as well).

---

### Fix DEVELOPER_ERROR when the app is installed from the **Play Store**

If Google Sign-In works in the **emulator / local debug** but shows **DEVELOPER_ERROR** when you install the app from the **Play Store**, the Play Store build is signed with a **different certificate** than your debug (or upload) keystore. You must register the **Play App Signing** certificate’s SHA-1.

**Where to get the SHA-1 for the Play Store build**

1. Open [Google Play Console](https://play.google.com/console/) and select your app **Motmot**.
2. Go to **Release** → **Setup** → **App signing** (or **Setup** → **App integrity**).
3. Under **App signing key certificate**, copy the **SHA-1 certificate fingerprint** (and optionally **SHA-256**).
   - If you use **Google Play App Signing**, this is the key Google uses to sign the APKs/AABs that users download. This is the SHA-1 you need.
4. In [Google Cloud Console](https://console.cloud.google.com/) → **APIs & Services** → **Credentials**, open your **Android** OAuth 2.0 Client ID (package `pro.birdr.app`).
5. Click **Add fingerprint** and paste the **SHA-1** from Play Console. Save.
6. Wait a few minutes for propagation, then try Google Sign-In again in the app installed from the Play Store.

**Summary**

| Build you're testing | SHA-1 to add in Google Cloud Android client |
|----------------------|------------------------------------------------|
| Local / emulator (debug) | From `./gradlew signingReport` → **debug** variant |
| EAS / CI build        | From EAS credentials or your upload keystore  |
| **Play Store install** | From **Play Console → App signing → App signing key certificate** |

**Checklist**

- [ ] Android OAuth client has **Package name** `pro.birdr.app` (not pro.birdr.mobile).  
- [ ] **SHA-1** added for the keystore that actually signs the build you’re testing.  
- [ ] **Web** client ID is set in the app (for the ID token).  
- [ ] App rebuilt after changing credentials.

---

- **“Developer Error” or sign-in fails on Android:** Check package name and SHA-1. Ensure the Android client’s SHA-1 matches the keystore you use to build.
- **Missing ID token / “missing ID token” in app:** Ensure `webClientId` is set to the **Web** client ID and that you’ve configured the Google Sign-In plugin in `app.json` (and run prebuild).
- **“RNGoogleSignin offline use requires server web ClientID”:** Set `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` in a `.env` file in the `mobile/` directory (e.g. `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=123456789-xxx.apps.googleusercontent.com`), then restart the dev server and rebuild the app so the value is picked up.
- **iOS redirect / scheme:** The `iosUrlScheme` in the plugin must be the reversed Web client ID (`com.googleusercontent.apps.<client_id>`).
