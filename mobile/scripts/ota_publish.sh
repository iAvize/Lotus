#!/bin/bash
# Publish a JS-only OTA update for Lotus Beta (Firebase Hosting).
# The installed app fetches https://lotus-updates.web.app/manifest.json on launch.
# expo-updates requires the expo-protocol-version response header, which
# GitHub Pages cannot serve — Firebase Hosting adds it via firebase.json.
# Usage: bash mobile/scripts/ota_publish.sh
set -euo pipefail

cd "$(dirname "$0")/.."
OUT=dist-ota
SITE=/tmp/lotus-fb
BASE_URL="https://lotus-updates.web.app"
PLATFORM="${1:-android}"   # android or ios
MANIFEST="manifest.json"; [ "$PLATFORM" = "ios" ] && MANIFEST="ios-manifest.json"

echo "Exporting $PLATFORM bundle..."
npx expo export --platform "$PLATFORM" --output-dir "$OUT" >/dev/null

mkdir -p "$SITE/public"
cp -R "$OUT/_expo" "$SITE/public/"

# Generate the expo-updates protocol manifest for this bundle.
python3 - << PYEOF
import base64, hashlib, json, os, uuid
from datetime import datetime, timezone
os.chdir("$SITE/public")
bundle = None
for root, _, files in os.walk("_expo/static/js/$PLATFORM"):
    for f in files:
        if f.endswith(".hbc"):
            bundle = os.path.join(root, f).replace(os.sep, "/")
assert bundle, "no $PLATFORM bundle exported"
digest = base64.urlsafe_b64encode(hashlib.sha256(open(bundle, "rb").read()).digest()).decode().rstrip("=")
m = {"id": str(uuid.uuid4()), "createdAt": (lambda n: n.strftime("%Y-%m-%dT%H:%M:%S.") + f"{n.microsecond // 1000:03d}Z")(datetime.now(timezone.utc)),
     "runtimeVersion": json.load(open("$(pwd)/$OUT/../app.json"))["expo"]["version"],
     "launchAsset": {"key": "bundle", "contentType": "application/javascript",
                     "url": "$BASE_URL/" + bundle, "hash": digest},
     "assets": [], "metadata": {}, "extra": {}}
json.dump(m, open("$MANIFEST", "w"))
print("wrote $MANIFEST ->", bundle)
PYEOF

cd "$SITE" && npx firebase-tools deploy --only hosting --project lotus-updates
echo "Published to $BASE_URL/$MANIFEST"
