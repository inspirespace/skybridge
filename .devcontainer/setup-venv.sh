#!/usr/bin/env bash
set -euo pipefail

VENV_DIR="/opt/venv"

if [ ! -d "$VENV_DIR" ]; then
  if [ "$(id -u)" -ne 0 ]; then
    sudo mkdir -p "$VENV_DIR"
    sudo chown -R "$(id -u)":"$(id -g)" "$VENV_DIR"
  else
    mkdir -p "$VENV_DIR"
  fi
fi

# Always try to make the venv tree writable for the current user.
# This prevents uv from failing when replacing interpreter-specific files.
if [ "$(id -u)" -ne 0 ]; then
  if command -v sudo >/dev/null 2>&1; then
    sudo chown -R "$(id -u)":"$(id -g)" "$VENV_DIR" 2>/dev/null || true
    sudo chmod -R u+rwX "$VENV_DIR" 2>/dev/null || true
  else
    chown -R "$(id -u)":"$(id -g)" "$VENV_DIR" 2>/dev/null || true
    chmod -R u+rwX "$VENV_DIR" 2>/dev/null || true
  fi
fi
