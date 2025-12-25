#!/usr/bin/env bash
set -euo pipefail

CODEX_DIR="/var/devcontainer/codex"
mkdir -p "${CODEX_DIR}"

if command -v id >/dev/null 2>&1; then
  chown -R "$(id -u):$(id -g)" "${CODEX_DIR}" || true
fi

# Point the default codex config path at the mounted volume.
if [[ -e "/home/vscode/.codex" && ! -L "/home/vscode/.codex" ]]; then
  rm -rf "/home/vscode/.codex"
fi
if [[ ! -L "/home/vscode/.codex" ]]; then
  ln -sfn "${CODEX_DIR}" "/home/vscode/.codex"
fi

CODEX_BIN="/home/vscode/.npm-global/bin/codex"
if [[ ! -x "${CODEX_BIN}" ]]; then
  if command -v npm >/dev/null 2>&1; then
    mkdir -p /home/vscode/.npm-global
    npm config set prefix /home/vscode/.npm-global
    npm i -g @openai/codex || true
  fi
fi
