#!/usr/bin/env bash
set -euo pipefail

VENV_DIR="/opt/venv"

if [ -d "$VENV_DIR" ] && [ "$(id -u)" -ne 0 ]; then
  if ! [ -w "$VENV_DIR" ]; then
    sudo chown -R "$(id -u)":"$(id -g)" "$VENV_DIR"
  fi
fi
