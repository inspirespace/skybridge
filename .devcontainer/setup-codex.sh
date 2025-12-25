#!/usr/bin/env bash
set -euo pipefail

CODEX_DIR="/home/vscode/.codex"
mkdir -p "${CODEX_DIR}"

if command -v id >/dev/null 2>&1; then
  chown -R "$(id -u):$(id -g)" "${CODEX_DIR}" || true
fi
