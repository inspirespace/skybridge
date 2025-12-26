#!/usr/bin/env bash
set -euo pipefail

# Automatically repair GitHub Copilot extensions to avoid "invalid extension" warnings
# caused by mismatched host/remote architectures in the devcontainer.

CODE_SERVER_BIN=$(ls -1d "${HOME}"/.vscode-server/bin/*/bin/code-server 2>/dev/null | head -n 1 || true)
if [[ -z "${CODE_SERVER_BIN}" || ! -x "${CODE_SERVER_BIN}" ]]; then
  exit 0
fi

extensions=(github.copilot github.copilot-chat)

for ext in "${extensions[@]}"; do
  # Force reinstall to fetch the correct targetPlatform for the container arch.
  "${CODE_SERVER_BIN}" --uninstall-extension "${ext}" --force >/dev/null 2>&1 || true
  "${CODE_SERVER_BIN}" --install-extension "${ext}" --force || true
done
