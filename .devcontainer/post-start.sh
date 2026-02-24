#!/usr/bin/env bash
set -euo pipefail

bash .devcontainer/setup-history.sh
bash .devcontainer/setup-codex.sh
bash .devcontainer/setup-venv.sh
bash .devcontainer/setup-completion.sh
bash .devcontainer/setup-zsh-autosuggestions.sh

NPM_CACHE_DIR="${HOME}/.cache/npm"
UV_CACHE_DIR="${HOME}/.cache/uv"
mkdir -p "${NPM_CACHE_DIR}" "${UV_CACHE_DIR}"

# Ensure Firebase CLI is available in the devcontainer shell.
if ! command -v firebase >/dev/null 2>&1; then
  echo "Installing Firebase CLI..."
  if ! NPM_CONFIG_CACHE="${NPM_CACHE_DIR}" npm install -g firebase-tools; then
    echo "Warning: failed to install Firebase CLI; continuing without it."
  fi
fi
if command -v firebase >/dev/null 2>&1; then
  echo "Firebase CLI: $(firebase --version)"
else
  echo "Firebase CLI not available."
fi

PYTHON_BIN=""
if command -v python3.11 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3.11)"
elif [ -x "/usr/local/python/current/bin/python3.11" ]; then
  PYTHON_BIN="/usr/local/python/current/bin/python3.11"
elif command -v python3 >/dev/null 2>&1; then
  if python3 -c 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)'; then
    PYTHON_BIN="$(command -v python3)"
  fi
fi

if [ -z "${PYTHON_BIN}" ]; then
  DETECTED_PYTHON="$(python3 --version 2>/dev/null || echo 'python3 not found')"
  echo "Error: Python 3.11 is required in the devcontainer to match Firebase Functions runtime (python311). Detected: ${DETECTED_PYTHON}" >&2
  exit 1
fi

UV_CACHE_DIR="${UV_CACHE_DIR}" uv sync --python "${PYTHON_BIN}" --frozen --extra dev
if ! command -v pytest >/dev/null 2>&1; then
  echo "pytest missing; reinstalling dev dependencies..."
  UV_CACHE_DIR="${UV_CACHE_DIR}" uv sync --python "${PYTHON_BIN}" --frozen --extra dev
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
    (cd src/frontend && NPM_CONFIG_CACHE="${NPM_CACHE_DIR}" npm ci)
  fi
fi

bash .devcontainer/cleanup-shell.sh
