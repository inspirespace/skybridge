#!/usr/bin/env bash
set -euo pipefail

pid_dir="/tmp/skybridge-vnc"
pid_files=(
  "${pid_dir}/novnc.pid"
  "${pid_dir}/vnc.pid"
  "${pid_dir}/wm.pid"
  "${pid_dir}/xvfb.pid"
)

for pid_file in "${pid_files[@]}"; do
  if [ -f "$pid_file" ]; then
    pid="$(cat "$pid_file")"
    if [ -n "$pid" ]; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
    rm -f "$pid_file"
  fi
done

echo "E2E VNC stopped."
