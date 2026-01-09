#!/usr/bin/env bash
set -euo pipefail

if ! command -v Xvfb >/dev/null 2>&1; then
  echo "Missing Xvfb. Run: ./scripts/setup-e2e-vnc.sh" >&2
  exit 1
fi

if ! command -v x11vnc >/dev/null 2>&1; then
  echo "Missing x11vnc. Run: ./scripts/setup-e2e-vnc.sh" >&2
  exit 1
fi

if ! command -v fluxbox >/dev/null 2>&1; then
  echo "Missing fluxbox. Run: ./scripts/setup-e2e-vnc.sh" >&2
  exit 1
fi

display="${DISPLAY:-:99}"
export DISPLAY="$display"

if [ -x ./scripts/start-e2e-vnc.sh ]; then
  ./scripts/start-e2e-vnc.sh
fi

screen="${VNC_SCREEN:-1280x720x24}"
rfbport="${VNC_PORT:-5900}"
webport="${NOVNC_PORT:-6080}"

echo "VNC server running on localhost:${rfbport} (no password)"
echo "noVNC available on http://localhost:${webport}/"
echo "Starting Playwright in headed mode..."

npm --prefix src/frontend run test:e2e -- --headed
