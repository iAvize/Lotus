# Lotus Mobile (beta)

React Native (Expo SDK 58) client for iOS/Android — text chat with Gemini,
BYOK (your own key, stored in the device keychain). Companion to the
Windows desktop app; shares its identity, not its codebase.

## Layout

- `src/App.tsx` — single-screen chat UI (dark purple Lotus theme),
  settings screen (key entry, clear history, version + install id).
- `src/gemini.ts` — BYOK REST client; model ladder `2.5-flash →
  flash-lite → 2.0-flash`; Lotus cybersecurity system prompt.
- `src/store.ts` — AsyncStorage (chat history, install id) +
  expo-secure-store (Gemini key → iOS Keychain).
- `app.json` — bundle id `com.avize.lotus.beta`, scheme `lotusbeta`,
  version `0.1.0-beta.1`.

## Dev preview (Expo Go) — current status

Works in principle via `npx expo start` + Expo Go, but the Expo Go
sign-in wall blocks anonymous dev projects on current SDKs. Notable
gotchas hit during bring-up:

- Expo Go silently closes on **SDK mismatch** — keep `expo` + deps
  aligned with current (`npx expo install --fix` after any `expo`
  upgrade). Project is on **SDK 58** (RN 0.88.1, React 19.3).
- Signed tunnels need a human expo.dev account on BOTH the CLI and the
  Expo Go app — **robot tokens can't sign into Expo Go**.
- Accounts created via "Sign in with Apple" have **no password option**
  and can't sign into Expo Go with email — create a plain email+password
  Expo account instead.
- LAN mode needs port 8081 through Windows firewall:
  `New-NetFirewallRule -DisplayName "Expo Metro" -Direction Inbound
  -Protocol TCP -LocalPort 8081 -Action Allow` (admin PowerShell).
  VirtualBox's host-only adapter (`192.168.56.1`) can confuse Metro's
  advertised IP — use the real LAN IP manually if needed.

## Path to TestFlight (when Apple Developer is enrolled)

1. `eas init` + `eas login` (human account).
2. `eas build --platform ios --profile preview` → produces a device
   build; `eas submit` pushes it to TestFlight via App Store Connect.
3. CI alternative: GitHub Actions `macos-latest` + Fastlane
   (`fastlane pilot`) can build/sign/upload — needs the App Store
   Connect API key stored as CI secrets.
4. App icon/splash: drop assets into `mobile/assets/` and reference
   them in `app.json` before the first build.

## Notes

- BYOK means no backend today; Gemini calls go phone → Google directly.
  LotusCloud (proxy + usage + billing) is the planned seam for launch.
- Streaming SSE is not yet implemented — RN needs a polyfill or the
  `@google/genai` SDK's stream; non-streaming replies are still fast.

## TestFlight shipping checklist (pre-baked)

- **Apple processing delay**: after upload, builds take 15 min – a few
  hours to appear in TestFlight. Submit once, then wait — do NOT re-run
  builds or retry uploads while Apple processes.
- **Build numbers**: `eas.json` preview + production profiles have
  `autoIncrement: true`; if building manually, bump `buildNumber` in
  `app.json` EVERY upload — Apple rejects duplicates.
- **Privacy/infoPlist**: `app.json → ios.infoPlist` pre-declares the
  standard permission strings (we request none — camera/location/
  tracking are declared unused). If a permission is ever added, update
  its description there or Apple auto-rejects.

## Path to Android (much easier than iOS)

Android needs **no paid developer account** for device testing — an APK
sideloads instantly. Build on either OS (EAS is cloud):

1. `eas login` + `eas init` (same Expo account used for iOS).
2. Preview/device build:
   `eas build --platform android --profile preview`
   → produces an **APK** on expo.dev; open the link on the phone (or
   `adb install lotus-beta.apk`) — done. Enable "install unknown apps"
   once for the browser/files app.
3. Emulator option: `npx expo run:android` with Android Studio's
   emulator installed — works on Windows and macOS.
4. Play Store (later): `$25` one-time developer account,
   `eas build -p android --profile production` → `.aab`,
   `eas submit -p android`.

Android notes:

- `app.json → android` block: package `com.avize.lotus.beta`,
  `versionCode` auto-increments via eas.json profiles (bump manually
  for local builds), adaptive icon + themed status/nav bars set.
- Hardware back returns to **Ask** first; from Ask it exits.
- `expo run:android` needs a local JDK + Android SDK (Android Studio
  install covers both) — EAS is the zero-setup path.

## OTA updates (Firebase Hosting, no Expo account)

JS/TS changes ship over-the-air via `expo-updates` pointed at Firebase
Hosting — **GitHub Pages does not work**: the client rejects manifests
without an `expo-protocol-version: 1` response header, which Pages can't
emit. firebase.json (committed at `scripts/firebase.json`) adds it.

- Host: `https://lotus-updates.web.app` (Firebase project `lotus-updates`)
- Manifests are **per-platform**: `manifest.json` = Android,
  `ios-manifest.json` = iOS. iOS's `Expo.plist` is re-pointed at the iOS
  manifest by `rebuild_ios.sh` after any prebuild.
- Publish (either machine, after `firebase login` once):
  `bash mobile/scripts/ota_publish.sh [android|ios]` — exports the bundle,
  regenerates the manifest with a unique launchAsset key (stale-cache fix),
  clears that platform's stale bundles, deploys.
- Version discipline: bump `VERSION` in `App.tsx` + `patchNotes.ts` for
  OTA. `app.json → version` is the runtimeVersion key — bump ONLY with a
  native rebuild or the update is rejected as incompatible.
- Cellular/service data: verified working (beta.17 canary). The native
  launch check applies updates before JS boots (no banner); mid-session
  fetches show the restart banner once per update id. The JS check retries
  with backoff and re-runs on foreground. `fallbackToCacheTimeout: 10000`
  is set in app.json — takes effect on the next native builds.
- Native/module/permission/app.json changes need a native rebuild:
  `rebuild_ios.sh` (device connected) or the Android equivalent — OTA only
  carries JS.
- macOS tooling: pod install needs the conda Ruby (`~/.local/ruby-env/bin`
  on PATH) — system Ruby 2.6 can't install CocoaPods. Node 22 lives at
  `~/.local/node22` (system node is too old for Expo CLI); ota_publish.sh
  prefers it automatically.
