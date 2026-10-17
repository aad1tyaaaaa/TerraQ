#!/usr/bin/env bash
# =============================================================================
#  TerraQ — one-time setup
#
#  Run this once after cloning, then use ./start.sh to launch.
#  Safe to re-run: every step is skipped if it is already done.
#
#  Usage:
#    bash setup.sh              install everything
#    bash setup.sh --prewarm    also fill the analysis cache (~7 min, do this
#                               before a demo so clicks return instantly)
#
#  This does NOT set up the quantum research pipeline — the Hyperion data it
#  needs is not in the repo. See RUN.md.
# =============================================================================
set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

PREWARM=0
[ "${1:-}" = "--prewarm" ] && PREWARM=1

ok()   { printf "  \033[92m✓\033[0m %s\n" "$1"; }
warn() { printf "  \033[93m!\033[0m %s\n" "$1"; }
die()  { printf "  \033[91m✗ %s\033[0m\n" "$1"; exit 1; }
step() { printf "\n\033[1m%s\033[0m\n" "$1"; }

# --- 1. Python ---------------------------------------------------------------
step "1/5  Python"
# 3.12 specifically: pennylane 0.38 pins numpy<2, and neither resolves on 3.13+.
PY_BIN=""
for c in python3.12 python3 python; do
  command -v "$c" >/dev/null 2>&1 || continue
  v="$("$c" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null)" || continue
  [ "$v" = "3.12" ] && { PY_BIN="$c"; break; }
done
if [ -z "$PY_BIN" ]; then
  die "Python 3.12 not found.
      This project needs 3.12 exactly — pennylane 0.38 requires numpy<2, which
      does not resolve on 3.13 or newer.
        macOS:  brew install python@3.12
        Linux:  sudo apt install python3.12 python3.12-venv
        or:     https://www.python.org/downloads/release/python-3120/"
fi
ok "found $PY_BIN ($("$PY_BIN" -V 2>&1))"

# --- 2. Node -----------------------------------------------------------------
step "2/5  Node.js"
command -v node >/dev/null 2>&1 || die "Node.js not found. Install Node 18 or newer: https://nodejs.org"
NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
[ "$NODE_MAJOR" -ge 18 ] || die "Node $(node -v) is too old. Node 18 or newer is required."
command -v npm >/dev/null 2>&1 || die "npm not found (it ships with Node)."
ok "found node $(node -v), npm $(npm -v)"

# --- 3. Python environment ---------------------------------------------------
step "3/5  Python packages"
if [ ! -x ".venv/bin/python" ]; then
  "$PY_BIN" -m venv .venv || die "could not create .venv"
  ok "created .venv"
else
  ok ".venv already exists"
fi

# Re-install only when requirements have changed since the last successful run.
STAMP=".venv/.requirements.sha"
NEW_SHA="$(shasum -a 256 requirements.txt 2>/dev/null | cut -d' ' -f1)"
if [ "$(cat "$STAMP" 2>/dev/null || echo none)" = "$NEW_SHA" ]; then
  ok "packages already match requirements.txt"
else
  echo "  installing (torch is large, this can take a few minutes)…"
  ./.venv/bin/pip install --quiet --upgrade pip || die "pip upgrade failed"
  ./.venv/bin/pip install --quiet -r requirements.txt || die "pip install failed — see the error above"
  echo "$NEW_SHA" > "$STAMP"
  ok "installed"
fi

# Prove the engine can actually import, rather than assuming pip succeeded.
./.venv/bin/python - <<'PY' || die "the engine could not import its dependencies"
import sys, importlib
for m in ("numpy", "scipy", "rasterio", "pyproj", "matplotlib", "PIL"):
    importlib.import_module(m)
sys.path.insert(0, "product")
import sentinel_engine, overlay_export, target_finder     # noqa: F401
PY
ok "engine imports cleanly"

# --- 4. Node packages --------------------------------------------------------
step "4/5  Web app packages"
if [ -d "terraq/node_modules/next" ]; then
  ok "node_modules already installed"
else
  ( cd terraq && npm install --no-audit --no-fund ) || die "npm install failed"
  ok "installed"
fi

# Optional config. Everything works with no keys at all; a key only enables the
# AI summary and the Ask panel.
if [ ! -f "terraq/.env.local" ] && [ -f "terraq/.env.example" ]; then
  cp terraq/.env.example terraq/.env.local
  warn "created terraq/.env.local from the example (all values blank)"
  warn "the app runs fine as-is; add a GROQ_API_KEY only if you want AI summaries"
fi

# --- 5. Cache ----------------------------------------------------------------
step "5/5  Analysis cache"
CACHED=$(ls -d outputs/jobs/*/ 2>/dev/null | wc -l | tr -d ' ')
if [ "$PREWARM" = "1" ]; then
  echo "  filling the cache for all 7 presets — serial, a few minutes…"
  ./.venv/bin/python product/prewarm.py || warn "prewarm had failures (see above); the app still runs"
  ok "cache ready"
elif [ "$CACHED" -gt 0 ]; then
  ok "$CACHED cached area(s) already present"
else
  warn "cache is empty — the first analysis of any area will take 1–3 minutes"
  warn "before a demo, run:  bash setup.sh --prewarm"
fi

printf "\n\033[1m\033[92mSetup complete.\033[0m\n\n"
echo "  Start it:   bash start.sh"
echo "  Stop it:    bash stop.sh"
echo "  Guide:      RUN.md"
echo ""
