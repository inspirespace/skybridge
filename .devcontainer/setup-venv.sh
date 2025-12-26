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
elif [ "$(id -u)" -ne 0 ] && ! [ -w "$VENV_DIR" ]; then
  sudo chown -R "$(id -u)":"$(id -g)" "$VENV_DIR"
fi
