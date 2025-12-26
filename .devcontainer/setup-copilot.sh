#!/usr/bin/env bash
set -euo pipefail

# Remove GitHub Copilot extensions entirely in the devcontainer.

CODE_SERVER_BIN=$(ls -1d "${HOME}"/.vscode-server/bin/*/bin/code-server 2>/dev/null | head -n 1 || true)
if [[ -z "${CODE_SERVER_BIN}" || ! -x "${CODE_SERVER_BIN}" ]]; then
  exit 0
fi

extensions=(github.copilot github.copilot-chat)

for ext in "${extensions[@]}"; do
  "${CODE_SERVER_BIN}" --uninstall-extension "${ext}" --force >/dev/null 2>&1 || true
done
