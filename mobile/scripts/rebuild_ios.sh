#!/bin/bash
# Rebuild + install Lotus Beta on a connected iPhone — no Expo account needed.
# Usage: bash mobile/scripts/rebuild_ios.sh
set -euo pipefail

cd "$(dirname "$0")/.."

UDID=$(xcrun devicectl list devices 2>/dev/null \
  | grep -oE '[0-9A-F]{8}-[0-9A-F]{16}' | head -1)
if [ -z "$UDID" ]; then
  echo "No iPhone connected — plug it in and trust this Mac." >&2
  exit 1
fi
echo "Installing to device $UDID"

BUILD_DIR=/tmp/lotus_ios_build
xcodebuild -workspace ios/LotusBeta.xcworkspace \
  -scheme LotusBeta -configuration Release \
  -destination "platform=iOS,id=$UDID" \
  -derivedDataPath "$BUILD_DIR" \
  -allowProvisioningUpdates build

xcrun devicectl device install app --device "$UDID" \
  "$BUILD_DIR/Build/Products/Release-iphoneos/LotusBeta.app"
echo "Done — Lotus Beta updated on the iPhone."
