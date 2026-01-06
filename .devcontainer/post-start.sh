#!/usr/bin/env bash
set -euo pipefail

bash .devcontainer/setup-history.sh
bash .devcontainer/setup-codex.sh
bash .devcontainer/setup-venv.sh
bash .devcontainer/setup-completion.sh
bash .devcontainer/setup-copilot.sh
bash .devcontainer/setup-zsh-autosuggestions.sh
UV_CACHE_DIR=/tmp/uv-cache uv sync --frozen --extra dev

# Ensure frontend deps match Linux platform for Playwright/Vite.
if [ -d "src/frontend" ]; then
  arch="$(uname -m)"
  if [ "$arch" = "aarch64" ] || [ "$arch" = "arm64" ]; then
    rollup_pkg="@rollup/rollup-linux-arm64-gnu"
  else
    rollup_pkg="@rollup/rollup-linux-x64-gnu"
  fi
  if [ ! -d "src/frontend/node_modules/$rollup_pkg" ]; then
    echo "Reinstalling frontend dependencies for Linux ($arch)..."
    rm -rf src/frontend/node_modules
    (cd src/frontend && NPM_CONFIG_CACHE=/tmp/npm-cache npm ci)
  fi
fi

bash .devcontainer/cleanup-shell.sh
