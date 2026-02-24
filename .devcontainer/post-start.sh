#!/usr/bin/env bash
set -euo pipefail

bash .devcontainer/setup-history.sh
bash .devcontainer/setup-codex.sh
bash .devcontainer/setup-venv.sh
bash .devcontainer/setup-completion.sh
bash .devcontainer/setup-zsh-autosuggestions.sh

# Ensure Firebase CLI is available in the devcontainer shell.
if ! command -v firebase >/dev/null 2>&1; then
  echo "Installing Firebase CLI..."
  NPM_CONFIG_CACHE=/tmp/npm-cache npm install -g firebase-tools
fi
echo "Firebase CLI: $(firebase --version)"

UV_CACHE_DIR=/tmp/uv-cache uv sync --frozen --extra dev
if ! command -v pytest >/dev/null 2>&1; then
  echo "pytest missing; reinstalling dev dependencies..."
  UV_CACHE_DIR=/tmp/uv-cache uv sync --frozen --extra dev
fi

# Optional: install VNC/noVNC deps for headed Playwright inside the container.
if [ "${DEVCONTAINER_E2E_VNC:-0}" = "1" ]; then
  bash ./scripts/setup-e2e-vnc.sh
  bash ./scripts/start-e2e-vnc.sh
fi

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
