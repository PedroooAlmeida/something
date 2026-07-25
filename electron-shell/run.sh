#!/usr/bin/env bash
# Launch the Gordon desktop shell.
# Darwin 25's Gatekeeper reaps the unsigned prebuilt Electron binary on quit,
# so we make sure it exists, strip quarantine, and ad-hoc sign before starting.
set -e
cd "$(dirname "$0")"

APP="node_modules/electron/dist/Electron.app"

if [ ! -d "$APP" ]; then
  echo "Electron binary missing — installing…"
  npm install electron@^31.0.0 >/dev/null 2>&1
fi

xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true
codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || true

echo "Launching Gordon…  (⌥⌘Y = make him yell · ⌥⌘G = open the Kitchen)"
exec npx electron .
