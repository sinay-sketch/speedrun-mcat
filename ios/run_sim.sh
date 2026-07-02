#!/bin/bash
# Build the Speedrun MCAT iOS app and run it in the iOS Simulator on the
# shared Anki Rust engine. Requires the iOS simulator runtime to be installed.
set -e
export PATH="/opt/homebrew/opt/rustup/bin:$HOME/.cargo/bin:$PATH"
cd "$(dirname "$0")/SpeedrunMCAT"
REPO=~/dev/Speedrun/anki

# 1) Ensure the bundled MCAT collection exists.
if [ ! -f Resources/collection.anki2 ]; then
  (cd "$REPO" && PYTHONPATH=out/pylib out/pyenv/bin/python tools/speedrun/prepare_ios_collection.py)
fi

# 2) Pick an installed iOS runtime and create/reuse a simulator device.
RUNTIME=$(xcrun simctl list runtimes | awk -F' - ' '/iOS/{print $NF}' | tail -1)
# Extract the 36-char UUID of an existing Speedrun-iPhone device, if any.
DEV_ID=$(xcrun simctl list devices | grep "Speedrun-iPhone (" | grep -oE "[0-9A-Fa-f-]{36}" | head -1)
if [ -z "$DEV_ID" ]; then
  DEVTYPE=$(xcrun simctl list devicetypes | awk -F'[()]' '/iPhone 1[5-7]( Pro)? \(/{print $2; exit}')
  DEV_ID=$(xcrun simctl create "Speedrun-iPhone" "$DEVTYPE" "$RUNTIME")
fi
echo "simulator device: $DEV_ID"
xcrun simctl boot "$DEV_ID" 2>/dev/null || true
open -a Simulator || true

# 3) Regenerate the Xcode project and build for this simulator.
xcodegen generate
xcodebuild -project SpeedrunMCAT.xcodeproj -scheme SpeedrunMCAT \
  -sdk iphonesimulator -configuration Debug -derivedDataPath build \
  -destination "id=$DEV_ID" build

# 4) Install and launch.
APP=$(find build/Build/Products/Debug-iphonesimulator -maxdepth 1 -name '*.app' | head -1)
echo "installing $APP"
xcrun simctl install "$DEV_ID" "$APP"
xcrun simctl launch "$DEV_ID" com.speedrun.mcat
