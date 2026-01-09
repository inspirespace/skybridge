#!/usr/bin/env bash
set -euo pipefail

display="${DISPLAY:-:99}"
screen="${VNC_SCREEN:-1280x720x24}"
rfbport="${VNC_PORT:-5900}"
webport="${NOVNC_PORT:-6080}"

pid_dir="/tmp/skybridge-vnc"
mkdir -p "$pid_dir"

pid_xvfb="${pid_dir}/xvfb.pid"
pid_wm="${pid_dir}/wm.pid"
pid_vnc="${pid_dir}/vnc.pid"
pid_web="${pid_dir}/novnc.pid"

is_running() {
  local pid_file="$1"
  if [ -f "$pid_file" ]; then
    local pid
    pid="$(cat "$pid_file")"
    if [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1; then
      return 0
    fi
  fi
  return 1
}

if is_running "$pid_xvfb"; then
  echo "Xvfb already running on DISPLAY ${display}."
else
  Xvfb "$display" -screen 0 "$screen" -nolisten tcp -ac >/dev/null 2>&1 &
  echo $! > "$pid_xvfb"
fi

if is_running "$pid_wm"; then
  echo "Fluxbox already running."
else
  fluxbox >/dev/null 2>&1 &
  echo $! > "$pid_wm"
fi

if is_running "$pid_vnc"; then
  echo "x11vnc already running."
else
  x11vnc -display "$display" -rfbport "$rfbport" -shared -forever -nopw -quiet >/dev/null 2>&1 &
  echo $! > "$pid_vnc"
fi

if is_running "$pid_web"; then
  echo "noVNC/websockify already running."
else
  if command -v novnc_proxy >/dev/null 2>&1; then
    novnc_proxy --vnc "localhost:${rfbport}" --listen "$webport" >/dev/null 2>&1 &
    echo $! > "$pid_web"
  elif [ -x /usr/share/novnc/utils/novnc_proxy ]; then
    /usr/share/novnc/utils/novnc_proxy --vnc "localhost:${rfbport}" --listen "$webport" >/dev/null 2>&1 &
    echo $! > "$pid_web"
  elif command -v websockify >/dev/null 2>&1; then
    websockify --web /usr/share/novnc "$webport" "localhost:${rfbport}" >/dev/null 2>&1 &
    echo $! > "$pid_web"
  fi
fi

echo "E2E VNC ensured on DISPLAY ${display}."
url="http://localhost:${webport}/vnc_auto.html?autoconnect=1&resize=remote"
echo "Open ${url}"

if [ -n "${VSCODE_PID:-}" ] || [ -n "${VSCODE_IPC_HOOK_CLI:-}" ]; then
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 || true
  fi
  if command -v python3 >/dev/null 2>&1; then
    python3 -m webbrowser "$url" >/dev/null 2>&1 || true
  fi
fi
