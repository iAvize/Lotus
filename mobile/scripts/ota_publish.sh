#!/bin/bash
# Publish a JS-only OTA update for Lotus Beta (self-hosted on GitHub Pages).
# Android builds fetch https://iavize.github.io/Lotus/manifest.json on launch;
# the manifest must be an expo-updates protocol manifest (not export metadata).
# Usage: bash mobile/scripts/ota_publish.sh
set -euo pipefail

cd "$(dirname "$0")/.."
OUT=dist-pages
PAGES_CLONE=/tmp/lotus-pages
BASE_URL="https://iavize.github.io/Lotus"

echo "Exporting update bundles..."
npx expo export --platform android --output-dir "$OUT-android" >/dev/null
npx expo export --platform ios --output-dir "$OUT-ios" >/dev/null

if [ ! -d "$PAGES_CLONE/.git" ]; then
  git clone -q --branch gh-pages https://github.com/iAvize/Lotus "$PAGES_CLONE"
fi
cd "$PAGES_CLONE" && git pull -q origin gh-pages
git rm -rfq --ignore-unmatch . ':!.git'
cp -R "$OLDPWD/$OUT-android/"* .
cp -R "$OLDPWD/$OUT-ios/"* .
touch .nojekyll

# Generate expo-updates protocol manifests (one per platform; a static host
# can't branch on the expo-platform header, so each platform needs its own
# manifest file and its own baked updates.url).
python3 - "$OLDPWD" << 'PYEOF'
import base64, hashlib, json, os, sys, uuid
from datetime import datetime, timezone

mobile_dir = sys.argv[1]
runtime = json.load(open(os.path.join(mobile_dir, "app.json")))["expo"]["version"]

def write_manifest(platform, out_name):
    meta = json.load(open("metadata.json")) if os.path.exists("metadata.json") else {}
    bundle = None
    for root, _, files in os.walk("_expo/static/js/%s" % platform):
        for f in files:
            if f.endswith(".hbc"):
                bundle = os.path.join(root, f).replace(os.sep, "/")
    if not bundle:
        print("no %s bundle found, skipping %s" % (platform, out_name)); return
    digest = base64.urlsafe_b64encode(hashlib.sha256(open(bundle, "rb").read()).digest()).decode().rstrip("=")
    manifest = {
        "id": str(uuid.uuid4()),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "runtimeVersion": runtime,
        "launchAsset": {"key": "bundle", "contentType": "application/javascript",
                        "url": "https://iavize.github.io/Lotus/" + bundle, "hash": digest},
        "assets": [], "metadata": {}, "extra": {},
    }
    with open(out_name, "w") as fh:
        json.dump(manifest, fh)
    print("wrote", out_name, "->", bundle)

write_manifest("android", "manifest.json")
write_manifest("ios", "ios-manifest.json")
PYEOF

# Legacy fallback: older builds request the bare directory URL, so serve the
# android manifest as index.html there too.
cp manifest.json index.html

git add -A
git -c user.name="iAvize" -c user.email="142369908+iAvize@users.noreply.github.com" \
  commit -qm "OTA update $(date -u +%Y-%m-%dT%H:%M:%SZ)" || true
git push -q origin gh-pages
echo "Published to $BASE_URL"
