# Lotus Mobile (beta)

React Native (Expo) client for iOS/Android — text chat with Gemini,
BYOK (your own key, stored in the device keychain). Companion to the
Windows desktop app; shares its identity, not its codebase.

## Run on your phone today (free, no Apple account)

1. Install **Expo Go** from the App Store (free).
2. On this machine:
   ```
   cd mobile
   npm install
   npx expo start --tunnel
   ```
3. Scan the QR code with your iPhone camera → opens in Expo Go.
4. First launch asks for a Gemini API key (same one as the desktop app).

`--tunnel` works when phone and PC aren't on the same Wi-Fi; on the same
network `npx expo start` alone is faster.

## Path to TestFlight

- TestFlight needs the $99/yr Apple Developer program — everything here
  transfers when you enroll.
- With an account: `eas build --platform ios` (Expo EAS) → automatic
  TestFlight upload; CI on `macos-latest` runners can drive the same flow.
