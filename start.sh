#!/usr/bin/env bash
# Start the website (dashboard + engine) WITHOUT running the research pipeline.
# Usage:  bash start.sh
# Stop everything later with:  bash stop.sh
#
# Ports are auto-selected: if the preferred port is already taken by something
# else on this machine, the next free one is used and printed below. Override
# with  DASH_PORT=3005 ENGINE_PORT=8770 bash start.sh

set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
mkdir -p .logs

PY="$ROOT/.venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "✗ Python environment missing (.venv)."
  echo "  Run setup first:   bash setup.sh"
  exit 1
fi
if [ ! -d "$ROOT/terraq/node_modules/next" ]; then
  echo "✗ Web app dependencies missing (terraq/node_modules)."
  echo "  Run setup first:   bash setup.sh"
  exit 1
fi

# find the first free port at or after $1
free_port() {
  local p=$1
  while lsof -nP -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1; do p=$((p+1)); done
  echo "$p"
}

ENGINE_PORT="$(free_port "${ENGINE_PORT:-8765}")"
DASH_PORT="$(free_port "${DASH_PORT:-3000}")"

echo "▶ Starting mineral-prospectivity engine (port $ENGINE_PORT)…"
# -u: without it the engine's per-request progress prints sit in a block buffer
# and .logs/engine.log stays empty for the whole (multi-minute) request.
PORT="$ENGINE_PORT" nohup "$PY" -u product/server.py > .logs/engine.log 2>&1 &
echo $! > .logs/engine.pid

echo "▶ Starting terraq dashboard (port $DASH_PORT)…"
(
  cd terraq
  CI=true NEXT_PUBLIC_ENGINE_URL="http://localhost:$ENGINE_PORT" \
    nohup node node_modules/next/dist/bin/next dev -p "$DASH_PORT" \
    > "$ROOT/.logs/dashboard.log" 2>&1 &
  echo $! > "$ROOT/.logs/dashboard.pid"
)

# wait for both to answer (engine imports rasterio, so give it a while)
wait_up() {
  local url=$1 name=$2 tries=${3:-40}
  for _ in $(seq 1 "$tries"); do
    if curl -fsS -o /dev/null --max-time 2 "$url" 2>/dev/null; then echo "  ✓ $name ready"; return 0; fi
    sleep 1
  done
  echo "  ✗ $name did not come up — see .logs/"; return 1
}

ok=0
wait_up "http://localhost:$ENGINE_PORT/" "engine"    || ok=1
wait_up "http://localhost:$DASH_PORT/"   "dashboard" || ok=1

echo ""
echo "  Dashboard      → http://localhost:$DASH_PORT"
echo "  Live Analysis  → http://localhost:$DASH_PORT  (sidebar → Live Analysis)"
echo "  Engine (raw)   → http://localhost:$ENGINE_PORT"
echo ""
echo "Logs: .logs/dashboard.log  .logs/engine.log"
echo "Stop: bash stop.sh"
exit $ok
