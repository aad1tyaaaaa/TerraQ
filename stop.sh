#!/usr/bin/env bash
# Stop the dashboard + engine started by start.sh.   Usage: bash stop.sh
# Only kills the PIDs start.sh recorded, so unrelated servers on this machine
# (e.g. another project already using port 3000) are left alone.
ROOT="$(cd "$(dirname "$0")" && pwd)"
for svc in engine dashboard; do
  f="$ROOT/.logs/$svc.pid"
  if [ -f "$f" ] && kill "$(cat "$f")" 2>/dev/null; then
    echo "stopped $svc (pid $(cat "$f"))"
  else
    echo "$svc not running"
  fi
  rm -f "$f"
done
