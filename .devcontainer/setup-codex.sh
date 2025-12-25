#!/usr/bin/env bash
set -euo pipefail

CODEX_DIR="/home/vscode/.codex"
mkdir -p "${CODEX_DIR}"

if command -v id >/dev/null 2>&1; then
  chown -R "$(id -u):$(id -g)" "${CODEX_DIR}" || true
fi

CODEX_BIN="/home/vscode/.npm-global/bin/codex"
if [[ ! -x "${CODEX_BIN}" ]]; then
  if command -v npm >/dev/null 2>&1; then
    mkdir -p /home/vscode/.npm-global
    npm config set prefix /home/vscode/.npm-global
    npm i -g @openai/codex || true
  fi
fi
