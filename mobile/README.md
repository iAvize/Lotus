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
