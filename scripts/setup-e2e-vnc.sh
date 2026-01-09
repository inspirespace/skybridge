#!/usr/bin/env bash
set -euo pipefail

packages=(
  xvfb
  x11vnc
  fluxbox
  novnc
  websockify
)

missing=()
for pkg in "${packages[@]}"; do
  if ! dpkg -s "$pkg" >/dev/null 2>&1; then
    missing+=("$pkg")
  fi
done

if [ "${#missing[@]}" -eq 0 ]; then
  echo "E2E VNC dependencies already installed."
  exit 0
fi

echo "Installing E2E VNC dependencies: ${missing[*]}"
sudo apt-get update
sudo apt-get install -y "${missing[@]}"
