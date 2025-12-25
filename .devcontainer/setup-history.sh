#!/usr/bin/env bash
set -euo pipefail

HIST_DIR="/var/devcontainer/history"
HIST_FILE="${HIST_DIR}/.zsh_history"

mkdir -p "${HIST_DIR}"

# Ensure ownership for the current user (devcontainer runs as vscode)
if command -v id >/dev/null 2>&1; then
  chown -R "$(id -u):$(id -g)" "${HIST_DIR}" || true
fi

if [[ ! -f "${HIST_FILE}" ]]; then
  touch "${HIST_FILE}" || true
fi
