#!/usr/bin/env bash
# Gordon — one-command demo bootstrap (macOS).
#
#   ./start.sh                 engine + backend + overlay
#   ./start.sh --with-capture  also start the screen-capture watcher
#   ./start.sh --mock          fire the PRD demo events after boot
#
# Ctrl-C tears everything down. Logs land in .demo-logs/.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$ROOT/.demo-logs"
ENGINE_PORT="${ENGINE_PORT:-8001}"
BACKEND_PORT="${BACKEND_PORT:-8765}"
WITH_CAPTURE=false
SEND_MOCK=false
for arg in "$@"; do
  case "$arg" in
    --with-capture) WITH_CAPTURE=true ;;
    --mock) SEND_MOCK=true ;;
    *) echo "unknown flag: $arg (use --with-capture / --mock)"; exit 1 ;;
  esac
done

mkdir -p "$LOG_DIR"
PIDS=()
cleanup() {
  trap - INT TERM EXIT
  echo
  echo "[gordon] shutting down..."
  for pid in "${PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  pkill -f "electron-shell/node_modules/electron" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

say_step() { printf '\n\033[1m[gordon] %s\033[0m\n' "$1"; }
wait_for() { # url label
  for _ in $(seq 1 60); do curl -sf -m 2 "$1" >/dev/null && return 0; sleep 0.5; done
  echo "[gordon] ERROR: $2 never came up — see $LOG_DIR"; exit 1
}

# ---------- prerequisites ----------
say_step "checking prerequisites"
[ "$(uname)" = "Darwin" ] || echo "  warning: built for macOS (voice fallback + overlay assume it)"
command -v python3 >/dev/null || { echo "  need python3 (3.11+)"; exit 1; }
command -v npm >/dev/null || { echo "  need node/npm (brew install node)"; exit 1; }
if ! command -v uv >/dev/null; then
  echo "  uv not found — installing (https://astral.sh/uv)"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# ---------- .env ----------
if [ ! -f "$ROOT/.env" ]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo "  created .env from .env.example"
fi
if ! grep -qE '^ANTHROPIC_API_KEY=.+' "$ROOT/.env"; then
  echo "  WARNING: ANTHROPIC_API_KEY empty in .env — engine can't roast;"
  echo "           backend will fall back to its mock evaluator until you fill it."
fi
if ! grep -qE '^ELEVENLABS_API_KEY=.+' "$ROOT/.env"; then
  echo "  note: ELEVENLABS_API_KEY empty — voice degrades to macOS system TTS."
fi

# ---------- engine (Person 3) ----------
say_step "engine -> http://127.0.0.1:$ENGINE_PORT"
if curl -sf -m 2 "http://127.0.0.1:$ENGINE_PORT/health" >/dev/null; then
  echo "  already running, reusing"
else
  (cd "$ROOT" && uv sync -q && uv run uvicorn gordon.api:app --port "$ENGINE_PORT" \
      >"$LOG_DIR/engine.log" 2>&1) &
  PIDS+=($!)
  wait_for "http://127.0.0.1:$ENGINE_PORT/health" "engine"
  echo "  up"
fi

# ---------- backend (Person 4) ----------
say_step "backend -> http://127.0.0.1:$BACKEND_PORT (engine wired via GORDON_ENGINE_URL)"
if curl -sf -m 2 "http://127.0.0.1:$BACKEND_PORT/docs" >/dev/null; then
  echo "  already running, reusing (make sure it was started with GORDON_ENGINE_URL=.../evaluate)"
else
  if [ ! -d "$ROOT/backend/.venv" ]; then
    python3 -m venv "$ROOT/backend/.venv"
    "$ROOT/backend/.venv/bin/pip" install -q -r "$ROOT/backend/requirements.txt"
  fi
  (cd "$ROOT/backend" && \
    GORDON_ENGINE_URL="http://127.0.0.1:$ENGINE_PORT/evaluate" \
    GORDON_ENGINE_TIMEOUT=30 \
    .venv/bin/uvicorn app.main:app --port "$BACKEND_PORT" \
      >"$LOG_DIR/backend.log" 2>&1) &
  PIDS+=($!)
  wait_for "http://127.0.0.1:$BACKEND_PORT/docs" "backend"
  echo "  up"
fi

# ---------- overlay (Person 1) ----------
say_step "overlay (Electron)"
cd "$ROOT/electron-shell"
[ -d node_modules ] || npm install --no-audit --no-fund
ELECTRON_BIN="node_modules/electron/dist/Electron.app"
if [ ! -x "$ELECTRON_BIN/Contents/MacOS/Electron" ]; then
  echo "  fetching Electron binary"
  node node_modules/electron/install.js
fi
# Gatekeeper: the npm-downloaded Electron.app is quarantined and unsigned —
# macOS SIGKILLs it ("Malware Blocked"). Strip quarantine + ad-hoc sign once.
xattr -dr com.apple.quarantine node_modules/electron/dist 2>/dev/null || true
codesign --force --deep --sign - "$ELECTRON_BIN" 2>/dev/null || true
# IDE terminals export ELECTRON_RUN_AS_NODE=1, which turns Electron into plain
# node and crashes main.js — always strip it.
(env -u ELECTRON_RUN_AS_NODE npm start >"$LOG_DIR/overlay.log" 2>&1) &
PIDS+=($!)
cd "$ROOT"
echo "  launched (window appears in a few seconds)"

# ---------- capture (Person 2, optional) ----------
if $WITH_CAPTURE; then
  say_step "capture watcher (needs macOS Screen Recording permission)"
  if [ ! -d "$ROOT/.venv-capture" ]; then
    python3 -m venv "$ROOT/.venv-capture"
    "$ROOT/.venv-capture/bin/pip" install -q -r "$ROOT/capture/requirements.txt"
  fi
  (cd "$ROOT" && .venv-capture/bin/python -m capture.main --submit-only \
      >"$LOG_DIR/capture.log" 2>&1) &
  PIDS+=($!)
  echo "  started in --submit-only mode; grant Screen Recording if prompted"
else
  echo
  echo "[gordon] capture not started (add --with-capture, needs screen permission)"
fi

# ---------- ready ----------
say_step "READY"
echo "  web      http://127.0.0.1:$BACKEND_PORT/          (landing + browser demo)"
echo "  engine   http://127.0.0.1:$ENGINE_PORT/health"
echo "  backend  http://127.0.0.1:$BACKEND_PORT/docs"
echo "  demo events:  backend/.venv/bin/python backend/scripts/send_mock_events.py"
echo "  logs:         $LOG_DIR/"
echo "  Ctrl-C stops everything."

if $SEND_MOCK; then
  say_step "firing PRD demo events"
  (cd "$ROOT/backend" && .venv/bin/python scripts/send_mock_events.py) || true
fi

wait
