# Birdr Mobile

React Native (Expo) app for Birdr, with the same structure as the web app in `/app`: home page, top bar with left drawer (main menu) and right user menu.

**Expo SDK 54** (React 19.1, React Native 0.81). Use **Node 22+** for install and builds.

## Setup

Requires **Node 22+**.

```bash
cd mobile
npm install
```

## Run

- **Development:** `npm start` then press `i` for iOS or `a` for Android in the terminal, or scan the QR code with Expo Go.
- **Android:** `npm run android` (generates native project if needed). This uses `run-android-with-node22.sh` so Node 22 is on PATH when Gradle runs (required for autolinking). If you get *Process 'command 'node'' finished with non-zero exit value 1*, run `npm run android` again (the script stops the Gradle daemon so the next run uses Node 22). To run without the wrapper: `npm run android:expo` (ensure `nvm use 22` and `cd android && ./gradlew --stop` first).
- **iOS:** `npm run ios` (requires Mac and Xcode).

### Opening the iOS project in Xcode

If you open **`mobile/ios/Birdr.xcodeproj`** in Xcode and see an error like **"Unable to open base configuration reference file ... Pods-Birdr.release.xcconfig"**, the CocoaPods dependencies haven’t been installed in that copy of the project. Fix it by running `pod install` in the **same** `ios` folder that Xcode is using (e.g. the path shown in the error):

```bash
cd mobile/ios   # or cd /Volumes/workspace/repository/mobile/ios if that’s where you opened from
pod install
```

Then open the **workspace** (not the project) so Xcode sees the Pods:

```bash
open mobile/ios/Birdr.xcworkspace
```

Or in Xcode: **File → Open** → choose `Birdr.xcworkspace`. Always use the `.xcworkspace` when working with CocoaPods.

**“Cannot find native module ExpoAudio” (or similar):** The JS bundle is trying to use a native module that isn’t in the app binary you’re running. Rebuild the native app (don’t just refresh Metro): `npx expo run:ios` or `npx expo run:android`. If you added a new native dependency recently, run `npx pod-install` then `npx expo run:ios`, or `npx expo prebuild --clean` then run again.

### iOS device (iPad / iPhone)

To run on a **physical device** (e.g. connected iPad):

1. **Start Metro first** (in one terminal):
   ```bash
   cd mobile && nvm use 22 && npm start
   ```
2. **iPad and Mac on the same Wi‑Fi** so the app can load the JS bundle from Metro.
3. In another terminal, build and run on the device:
   ```bash
   cd mobile && nvm use 22 && npx expo run:ios --device "iPad van Loek"
   ```
   Use your device name (e.g. from Xcode → Window → Devices) or leave off `"iPad van Loek"` to pick from a list.
4. **Trust the developer** on the device: Settings → General → VPN & Device Management → tap your developer profile → Trust.

**“No bundle URL present”:** The app loads JavaScript from Metro on your Mac. Ensure Metro is running (`npm start`) and the device is on the same network; the app uses your Mac’s IP (embedded at build time) to connect to `http://<mac-ip>:8081`.

**Sign in with Apple (error 1000 / ERR_REQUEST_UNKNOWN):** This often happens on the **iOS Simulator**. Sign in with Apple is unreliable in the simulator; test it on a **physical device**. On the device, ensure the app has the “Sign in with Apple” capability (it’s in `Birdr.entitlements` and enabled via `usesAppleSignIn` in `app.json`) and that the App ID in the Apple Developer portal has Sign in with Apple enabled.

## Generate native projects (Android + iOS)

To get full `android/` and `ios/` folders (use **Node 22+**):

```bash
nvm use 22
npx expo prebuild
```

This also copies the app icon from `assets/icon.png` into the native projects (iOS AppIcon and Android adaptive icon). If you change the icon, run `npx expo prebuild` again so both platforms use it.

Then build a **debug APK for your phone**:

Use **Node 22+** in the same terminal (Gradle runs `node` for autolinking; older Node causes build failures). If the build fails with **Process 'command 'node'' finished with non-zero exit value 1**, the Gradle daemon was started with an older Node. Fix by either:

- **Option A:** Run `./gradlew --stop` in `android/`, then in a terminal where you’ve run `nvm use 22`, run `npm run build:android:debug` again.
- **Option B:** From `mobile/android/`, run `./run-with-node22.sh app:assembleDebug` (wrapper puts Node 22 on PATH, then runs Gradle).

```bash
nvm use 22   # must be run in this shell before the next command
npm run build:android:debug
```

The debug APK is written to:

**`android/app/build/outputs/apk/debug/app-debug.apk`**

Copy it to your Android device (e.g. via USB, cloud, or email) and open it to install. You may need to allow “Install from unknown sources” for the app or file manager you use.

**“Unable to load script”:** The debug APK is built with the JS bundle **included**, so it runs without a dev server. If you see that error, reinstall the APK from the path above (after running `npm run build:android:debug` again). If you prefer to load from Metro instead, connect the phone via USB, run `adb reverse tcp:8081 tcp:8081`, start Metro with `npm start`, then open the app.

## Android UI tests (Espresso)

Automated UI tests for the Country challenge flow (tap → assert screen/modal changes). Run them with an **emulator or device** connected and **Node 22+** (Gradle runs Node for the React Native build). If you see "Process 'command 'node'' finished with non-zero exit value 1", the Gradle daemon was started with an older Node—use one of:

```bash
cd mobile/android

# Option A: Stop daemon, then run (daemon restarts with current Node)
./gradlew --stop
./gradlew connectedDebugAndroidTest

# Option B: Wrapper (uses Node 22 and avoids daemon PATH issues)
./run-with-node22.sh connectedDebugAndroidTest
```

Or from repo root:

```bash
cd mobile && (cd android && ./run-with-node22.sh connectedDebugAndroidTest)
```

Tests live in `mobile/android/app/src/androidTest/kotlin/pro/birdr/app/CountryChallengeFlowTest.kt`. They launch the app, go to Country challenge from Home, open/close country and language modals, and (in a second test) fill the form, tap “Start challenge”, and assert that the next state (level intro or play screen) appears. **Test 2 calls the real “Start challenge” API**; use a running backend (e.g. staging) or a test build variant with a test API URL if you need a controlled environment.

- **CI:** Add a job that starts an Android emulator (e.g. `system-images;android-34;google_apis;x86_64`), runs `./gradlew connectedDebugAndroidTest`, and fails the build if any test fails.
- **Firebase Test Lab:** Build the debug APK and test APK, then run `gcloud firebase test android run` with the APKs to run the same tests on multiple devices/API levels.

## Automated Google Play releases

The Android counterpart to the **Xcode Cloud** workflow that ships iOS builds to App Store
Connect. `.github/workflows/android-play-release.yml` runs on `ubuntu-latest`, builds the
release AAB with Gradle from the committed `android/` directory, and publishes it to Google
Play — no Mac minutes, no EAS involved.

### When it runs

On every push to `main` that touches `mobile/**` (the same shape as the Xcode Cloud trigger),
**but only uploads when `expo.buildNumber` in `mobile/app.json` actually changed in that push.**
Play rejects a `versionCode` it has already seen, so a push without a release bump would fail
the job; instead it logs why it skipped and exits green. `workflow_dispatch` always uploads.

By default the release goes to the **production** track with status `completed` — live to 100%
of users, no button to press. Run it manually to pick a different track, a `draft` release, or
a staged `inProgress` rollout with a user fraction.

### One-time setup

1. **Play service account** — Play Console → *Users and permissions* → invite the Google Cloud
   service account, grant it *Release apps to testing tracks* and *Release to production*. In
   Google Cloud Console, create a JSON key for that service account (APIs & Services →
   Credentials). Then in Play Console → *API access*, confirm the account is linked.

2. **Base64-encode the upload keystore** (`android/keys/` is gitignored, so CI restores it from
   secrets):
   ```bash
   base64 -i mobile/android/keys/upload-keystore.jks | pbcopy
   ```

3. **Add repo secrets** (GitHub → Settings → Secrets and variables → Actions):

   | Secret | Value |
   | --- | --- |
   | `ANDROID_KEYSTORE_BASE64` | output of the `base64` command above |
   | `ANDROID_KEYSTORE_PASSWORD` | `storePassword` from `android/keys/keystore.properties` |
   | `ANDROID_KEY_ALIAS` | `keyAlias` from the same file |
   | `ANDROID_KEY_PASSWORD` | `keyPassword` from the same file |
   | `PLAY_SERVICE_ACCOUNT_JSON` | full contents of the service account JSON key |

   The workflow checks all five up front and fails with the missing names rather than dying
   halfway through a Gradle build.

### Shipping a release

Use the **`/birdr-release`** skill, or run it by hand:

```bash
cd mobile
npm run release:set          # next build number
npm run release:set -- 106   # a specific one
```

Releases are named after the bird whose species id equals the build number — build 106 is
`Kelp Goose`, from [`/api/species/106/`](https://birdr.pro/api/species/106/) — and the version
is always `1.<build>.0`. The script writes `expo.version`, `expo.buildNumber` and
`expo.releaseCodename` into `app.json` and syncs `ios/Birdr/Info.plist` (Android reads
`app.json` directly at build time, iOS does not). It refuses a build number at or below the
current one, since both stores reject a reused one.

Commit those two files and push to `main`, and both stores build: Xcode Cloud for iOS, this
workflow for Android. Every run also
attaches the AAB and the R8 `mapping.txt` as a GitHub artifact (30 days), and the mapping file is
uploaded to Play so crash reports deobfuscate.

> **Note:** `android/app/build.gradle` sets `versionName releaseCodename`, so Play displays the
> codename (e.g. `Upland Goose`) where iOS shows `1.105.0`. Change it to `appJsonExpo.version` if
> you want the two stores to agree.

## Automated store releases (GitHub Actions)

Ship new versions to **TestFlight / App Store Connect** and **Google Play** without a Mac in CI. The workflow only starts an EAS build on Expo’s servers (`ubuntu-latest`), so it fits a free GitHub plan.

### One-time setup

1. **Expo access token**  
   Create at [expo.dev/settings/access-tokens](https://expo.dev/settings/access-tokens), then add a repo secret named `EXPO_TOKEN`.

2. **iOS credentials on EAS** (if not already):
   ```bash
   cd mobile
   eas credentials --platform ios
   ```
   Use your existing distribution cert / App Store profile, or let EAS manage them. Also configure App Store Connect API key under submit credentials when prompted (or in the Expo dashboard).

3. **Android keystore on EAS** (required for cloud builds — production profile uses `credentialsSource: "remote"`):
   ```bash
   cd mobile
   eas credentials --platform android
   ```
   Choose “Use existing keystore”, upload `android/keys/upload-keystore.jks` (or `android/app/upload-keystore.jks` if that’s where yours lives), and enter the alias/passwords from `keystore.properties`.  
   Also link a Play Console service account JSON for submit (Expo dashboard → project → credentials / `eas submit` prompts).

4. **Bump the release** in `mobile/app.json` before shipping:
   - `expo.version` (e.g. `1.87.0`)
   - `expo.buildNumber` (must increase each store upload)
   - `expo.releaseCodename` (optional display name)

### Run a release

- **GitHub:** Actions → **Mobile store release** → Run workflow → pick `ios` / `android` / `all`, leave submit on.
- **Local:**
  ```bash
  cd mobile
  npm run release:ios        # EAS cloud + auto-submit
  npm run release:android
  npm run release:store      # both
  ```

Builds land in App Store Connect (TestFlight) and Play Console. You still press **Submit for review** in each console unless you later add fully automatic review submission.

Local Android builds that need `credentials.json` on disk still use:
```bash
npm run build:android        # profile production-local --local
npm run build:android:push
```

## Android release / AAB (testing & Play Store)


Use **Node 22+** in the same terminal as for debug.

### Testing: release APK or AAB (signed with debug keystore)

Right now release is signed with the **debug keystore**, so you can build without creating a release key:

- **Release APK** (single file, good for sideload / testing):
  ```bash
  npm run build:android:release
  ```
  Output: `android/app/build/outputs/apk/release/app-release.apk`

- **Release AAB** (Android App Bundle, required for Play Store upload, smaller downloads):
  ```bash
  npm run build:android:aab
  ```
  Output: `android/app/build/outputs/bundle/release/app-release.aab`

Do **not** use `./gradlew clean` before the AAB if you hit CMake **GLOB mismatch** / missing `codegen/jni` errors: Gradle’s native **clean** can fail when those folders were never generated. For a **full fresh build**, use **`npm run build:android:aab:rebuild`** (removes `android/app/.cxx` and `android/app/build`, then `bundleRelease`). If Play Console still shows an old **versionCode**, bump it in `android/app/build.gradle` and `app.json`, rebuild, and upload the AAB whose **file time** matches the build—not an old copy from elsewhere.

You can upload the AAB to Play Console (Internal testing track or Production). For **internal testing** you can also use the release APK and share it directly.

### Production: sign with your own keystore

For **production** you must sign release builds with your own keystore:

1. **Create a keystore** (once):
   ```bash
   keytool -genkeypair -v -storetype PKCS12 -keystore android/app/my-release-key.keystore -alias my-key-alias -keyalg RSA -keysize 2048 -validity 10000
   ```
   Store the keystore file and passwords safely (e.g. in a secrets manager). **Do not commit the keystore to git.**

2. **Configure release signing** in `android/app/build.gradle`:
   - Add a `release` block under `signingConfigs` that points to your keystore and use env vars or `gradle.properties` (not committed) for passwords.
   - In `buildTypes.release`, set `signingConfig signingConfigs.release`.

   Example using `gradle.properties` (add `android/app/my-release-key.keystore` to `.gitignore` and keep passwords out of version control):

   ```groovy
   signingConfigs {
       release {
           storeFile file('my-release-key.keystore')
           storePassword System.getenv("KEYSTORE_PASSWORD") ?: findProperty('MYAPP_RELEASE_STORE_PASSWORD')
           keyAlias System.getenv("KEY_ALIAS") ?: findProperty('MYAPP_RELEASE_KEY_ALIAS')
           keyPassword System.getenv("KEY_PASSWORD") ?: findProperty('MYAPP_RELEASE_KEY_PASSWORD')
       }
   }
   ```

   Then run the same commands:
   - `npm run build:android:release` → APK for testing or direct distribution.
   - `npm run build:android:aab` → AAB for Play Store.

### EAS Build: use keystore from `android/app/`

Release builds via EAS **cloud** (`production` profile) use the **remote** keystore stored in your Expo project. Upload it once with `eas credentials --platform android` (see [Automated store releases](#automated-store-releases-github-actions)).

- **`npm run build:android`** / **`npm run build:android:push`** use profile **`production-local`** so the build runs on your machine and reads `credentials.json` + the local `.jks`.
- **`npm run build:android:cloud`**, **`npm run release:android`**, and the GitHub **Mobile store release** workflow use **`production`** with remote credentials.

### Google Play: 16 KB page size support

Google Play requires apps targeting Android 15+ to support 16 KB memory page sizes. This project uses **Expo SDK 53** with **React Native 0.79** and **NDK 28**, so native libs are built with 16 KB alignment. **`useLegacyPackaging false`** in `android/app/build.gradle` keeps that alignment in the AAB. The config plugin **`plugins/withAndroid16Kb.js`** re-applies NDK 28 and packaging options when you run **`npx expo prebuild`**, so EAS cloud builds stay compliant. If Play still shows "ondersteunt geen geheugenpagina's van 16 KB", build the AAB with **`npm run build:android:aab`** (or EAS local) so the committed `android/` is used, then upload that AAB.

### Useful commands

- **SHA-1 (e.g. for Google Sign-In / Firebase):** `npm run print-sha1` (use the SHA-1 from the release variant when you use a release keystore).

## Google Sign-In (DEVELOPER_ERROR on Android)

If you see **DEVELOPER_ERROR** when signing in with Google on Android:

1. **Package name in Google Console must be** `pro.birdr.app` (not `pro.birdr.mobile`).
2. Add the **SHA-1** of the keystore that signs your build to the Android OAuth client:
   ```bash
   npm run print-sha1
   ```
   Copy the SHA-1 for the variant you use (e.g. `debug`), then in [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials → your **Android** OAuth client, add that fingerprint.
3. Rebuild the app after changing credentials.

Full steps: see **`GOOGLE_CONSOLE_SETUP.md`**.

## Opening game links in the app (QR code / share link)

When someone scans the lobby QR code or taps a shared game link (`https://birdr.pro/join/<game_token>`), the link should open in the Birdr app instead of the browser.

**What’s already in place**

- **App:** Custom scheme `birdr://` and (on Android) an App Link intent for `https://birdr.pro/join/`. `DeepLinkHandler` loads the game and navigates to Lobby.
- **Server:** `GET /join/<token>/` redirects to `birdr://join/<token>`, so opening the HTTPS link in a browser sends the user into the app. The same backend serves `.well-known/apple-app-site-association` (iOS) and `.well-known/assetlinks.json` (Android) for verified App Links.

**To get “Open in app” without a disambiguation dialog**

1. **iOS (Universal Links)**  
   In `jizz/urls.py`, in `apple_app_site_association`, replace `TEAM_ID` with your Apple Team ID (e.g. `ABC123XYZ`). The bundle ID must stay `pro.birdr.app` (it matches `app.json`).

2. **Android (App Links)**  
   In `jizz/urls.py`, in `android_asset_links`, replace `SHA256_FINGERPRINT_PLACEHOLDER` with the SHA-256 fingerprint of the certificate that signs your app (colon-separated). Get it with:
   ```bash
   keytool -list -v -keystore your.keystore -alias youralias
   ```
   Use the same signing key you use for Play Store builds. The `package_name` is already `pro.birdr.app`.

After deploying the updated `.well-known` files, install the app and tap `https://birdr.pro/join/<token>` (e.g. from Notes or Messages). If verification succeeds, the link should open directly in the app. If not, the server redirect still sends `birdr://join/<token>`, so the system may show “Open in Birdr?” once.

## Structure

- **Top bar:** Left = open main (left) drawer; center = title; right = open user menu.
- **Left drawer:** Home, New game, High scores, Country challenge, Updates, Help, Privacy, About Birdr + footer (data/media credits, contact).
- **Right user menu (modal):** Account, Login, Register, My Games, Profile, Review media, Logout.

Screens beyond Home are placeholders; wire them to your API and logic as in the web app.

## Assets

Add `icon.png`, `splash-icon.png`, and `adaptive-icon.png` under `assets/` (or replace after `expo prebuild`). See `assets/README.md`.
