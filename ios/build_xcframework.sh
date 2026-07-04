#!/bin/bash
# Cross-compile the Speedrun anki-ffi crate (thin C ABI over Anki's shared Rust
# engine) for iOS device + simulator and package AnkiRust.xcframework.
# Reproducible: one command rebuilds the engine the iOS app links against.
set -euo pipefail
export PATH="/opt/homebrew/opt/rustup/bin:$HOME/.cargo/bin:$PATH"
REPO=~/dev/Speedrun/anki
cd "$REPO"

DEVICE=aarch64-apple-ios          # real iPhone
SIM=aarch64-apple-ios-sim         # Apple-silicon simulator
# Match the app's min iOS so the cdylib link finds modern runtime symbols
# (e.g. ___chkstk_darwin) instead of defaulting to iOS 10.0.
export IPHONEOS_DEPLOYMENT_TARGET=16.0
XCF=ios/SpeedrunMCAT/AnkiRust.xcframework
HDRDIR=ios/SpeedrunMCAT/anki_ffi_headers          # headers dir for -create-xcframework

rustup target add "$DEVICE" "$SIM" >/dev/null 2>&1 || true

# Stage the canonical hand-written header into a headers directory.
mkdir -p "$HDRDIR"
cp ios/SpeedrunMCAT/anki_ffi.h "$HDRDIR/anki_ffi.h"

echo "==> building anki-ffi for $DEVICE"
cargo build -p anki-ffi --release --target "$DEVICE"
echo "==> building anki-ffi for $SIM"
cargo build -p anki-ffi --release --target "$SIM"

DEV_LIB="target/$DEVICE/release/libanki_ffi.a"
SIM_LIB="target/$SIM/release/libanki_ffi.a"

echo "==> repackaging $XCF"
rm -rf "$XCF"
xcodebuild -create-xcframework \
  -library "$DEV_LIB" -headers "$HDRDIR" \
  -library "$SIM_LIB" -headers "$HDRDIR" \
  -output "$XCF"

echo "==> done"
lipo -info "$DEV_LIB" "$SIM_LIB"
ls -la "$XCF"
