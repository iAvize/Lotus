#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Toolchains used for the free-account local iOS build on the Mac.
export PATH="$HOME/.local/ruby-env/bin:$HOME/.local/node22/bin:$PATH"

npm ci

if [ ! -d ios ]; then
  npx expo prebuild -p ios
fi

cd ios
pod install

NODE_BIN="${NODE_BINARY:-$(command -v node)}"
VERSION="$("$NODE_BIN" -p "require('../app.json').expo.version")"
BUILD_NUMBER="$("$NODE_BIN" -p "require('../app.json').expo.ios.buildNumber || '1'")"
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" LotusBeta/Info.plist
/usr/libexec/PlistBuddy -c "Set :CFBundleVersion $BUILD_NUMBER" LotusBeta/Info.plist

DEVICE="${1:-${LOTUS_IOS_UDID:-}}"
if [ -z "$DEVICE" ]; then
  echo "Usage: $0 <iPhone UDID>" >&2
  echo "Find it with: xcrun devicectl list devices" >&2
  exit 1
fi

xcodebuild -workspace LotusBeta.xcworkspace -scheme LotusBeta -configuration Release -sdk iphoneos -destination "id=$DEVICE" -derivedDataPath "$PWD/build" -allowProvisioningUpdates build

APP="$PWD/build/Build/Products/Release-iphoneos/LotusBeta.app"
xcrun devicectl device install app --device "$DEVICE" "$APP"
xcrun devicectl device process launch --device "$DEVICE" com.avize.lotus.beta || true

echo "Installed Lotus Beta $VERSION ($BUILD_NUMBER) on $DEVICE"
