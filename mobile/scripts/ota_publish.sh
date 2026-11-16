#!/bin/bash
# Publish a JS-only OTA update for Lotus Beta (self-hosted on GitHub Pages).
# The installed app checks https://iavize.github.io/Lotus/ on every launch.
# Usage: bash mobile/scripts/ota_publish.sh
set -euo pipefail

cd "$(dirname "$0")/.."
OUT=dist-pages
PAGES_CLONE=/tmp/lotus-pages

echo "Exporting update bundle..."
npx expo export --platform ios --output-dir "$OUT" >/dev/null

if [ ! -d "$PAGES_CLONE/.git" ]; then
  git clone -q --branch gh-pages https://github.com/iAvize/Lotus "$PAGES_CLONE"
fi
cd "$PAGES_CLONE" && git pull -q origin gh-pages
git rm -rfq --ignore-unmatch . ':!.git'
cp -R "$OLDPWD/$OUT/"* .
touch .nojekyll
git add -A
if git diff --cached --quiet; then
  echo "No update content changed — nothing to publish."
  exit 0
fi
git -c user.name="iAvize" -c user.email="142369908+iAvize@users.noreply.github.com" \
  commit -qm "ota: update $(date +%Y-%m-%d)"
git push origin gh-pages
echo "Published — installed builds pick it up on next launch."
