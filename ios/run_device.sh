#!/bin/bash
# Build + install the Speedrun MCAT app onto a REAL iPhone via a free Apple-ID
# sideload (no App Store, no paid account). Prereqs (one-time, done by you):
#   1. Plug the iPhone into this Mac with a cable; unlock it; tap "Trust This Computer".
#   2. Sign your Apple ID into Xcode: Xcode ▸ Settings ▸ Accounts ▸ "+" ▸ Apple ID.
# Then just run this script. The app is signed with your free "Personal Team"
# (works untethered for 7 days). After install, on the phone approve the dev cert:
#   Settings ▸ General ▸ VPN & Device Management ▸ (your Apple ID) ▸ Trust.
set -euo pipefail
export PATH="/opt/homebrew/opt/rustup/bin:$HOME/.cargo/bin:$PATH"
cd "$(dirname "$0")/SpeedrunMCAT"

echo "==> finding a connected iPhone…"
UDID=$(xcrun devicectl list devices 2>/dev/null | awk '/iPhone|iPad/ && /connected|available/ {print $(NF-1)}' | head -1)
if [ -z "${UDID:-}" ]; then
  # fallback parser
  UDID=$(xcrun devicectl list devices 2>/dev/null | grep -iE "iphone|ipad" | grep -oiE "[0-9A-F]{8}-[0-9A-F]{16}|[0-9A-F-]{36}" | head -1)
fi
[ -z "${UDID:-}" ] && { echo "ERROR: no iPhone detected. Plug it in, unlock, tap 'Trust This Computer', and retry."; exit 1; }
echo "    device: $UDID"

echo "==> detecting your free Apple-ID signing team…"
TEAM=$(security find-identity -v -p codesigning 2>/dev/null | grep -oE "Apple Development: .*\(([A-Z0-9]{10})\)" | grep -oE "\([A-Z0-9]{10}\)" | tr -d "()" | head -1)
[ -z "${TEAM:-}" ] && { echo "ERROR: no 'Apple Development' identity. In Xcode ▸ Settings ▸ Accounts, add your Apple ID, then retry."; exit 1; }
echo "    team: $TEAM"

echo "==> generating project + building for the device (automatic signing)…"
xcodegen generate
xcodebuild -project SpeedrunMCAT.xcodeproj -scheme SpeedrunMCAT \
  -sdk iphoneos -configuration Debug -derivedDataPath build-device \
  -destination "id=$UDID" -allowProvisioningUpdates \
  CODE_SIGN_STYLE=Automatic DEVELOPMENT_TEAM="$TEAM" \
  PRODUCT_BUNDLE_IDENTIFIER="com.speedrun.mcat" build

APP=$(find build-device/Build/Products/Debug-iphoneos -maxdepth 1 -name '*.app' | head -1)
echo "==> installing $APP onto the phone…"
xcrun devicectl device install app --device "$UDID" "$APP"
echo "==> launching…"
xcrun devicectl device process launch --device "$UDID" com.speedrun.mcat || true
echo "==> done. If it won't open, on the phone: Settings ▸ General ▸ VPN & Device Management ▸ Trust your Apple ID."
