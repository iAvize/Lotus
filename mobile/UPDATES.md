# Lotus mobile update paths

## Free Apple account — local rebuild

Use this for your own iPhone only. The app expires about every 7 days and needs a rebuild/reinstall after expiry.

One-command rebuild after pulling mobile changes:

```bash
cd ~/Lotus\ Source/mobile
./scripts/rebuild-ios.sh 00008130-000A045E21C1001C
```

Find the iPhone UDID with `xcrun devicectl list devices`. The script uses the local Node/Ruby/CocoaPods toolchains, builds the Release app, installs it, and launches it.

## Paid Apple Developer Program — TestFlight

Enroll at https://developer.apple.com/program ($99/year). Then use App Store Connect/TestFlight or EAS Submit so testers install from TestFlight instead of Xcode. Paid builds last longer, support more devices, and unlock capabilities the free account cannot use.

## EAS Update — smooth JS-only updates

For chat/UI-only changes, Expo Updates can push a new JavaScript bundle without reinstalling the app:

1. Create an Expo account and run `eas login`.
2. Run `eas init` in `mobile/` to create/link the EAS project.
3. Install `expo-updates` and add `updates.url` plus `runtimeVersion` in `app.json`.
4. Add `channel` values to the relevant `eas.json` build profiles.
5. Publish with `eas update --branch production`.

Native dependency or iOS project changes still require a new build/TestFlight upload; JS-only changes can use EAS Update.
