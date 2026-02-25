#!/usr/bin/env bash
set -euo pipefail

# Keep devcontainer startup output clean and deterministic.
export NPM_CONFIG_UPDATE_NOTIFIER=false

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
  if ! NPM_CONFIG_CACHE="${NPM_CACHE_DIR}" NPM_CONFIG_UPDATE_NOTIFIER=false npm install -g firebase-tools; then
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

# Keep the venv path stable so VS Code does not fall back to /bin/python
# during startup if it probes interpreters while post-start is still running.
if [ -x "/opt/venv/bin/python" ]; then
  if ! /opt/venv/bin/python -c 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)'; then
    echo "Refreshing /opt/venv to Python 3.11..."
    UV_BIN="$(command -v uv)"
    if ! "${UV_BIN}" venv /opt/venv --python "${PYTHON_BIN}" --clear; then
      if [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1; then
        echo "Retrying /opt/venv refresh with sudo..."
        sudo "${UV_BIN}" venv /opt/venv --python "${PYTHON_BIN}" --clear
        sudo chown -R "$(id -u)":"$(id -g)" /opt/venv
      else
        echo "Error: failed to refresh /opt/venv and sudo is unavailable." >&2
        exit 1
      fi
    fi
  fi
fi

UV_CACHE_DIR="${UV_CACHE_DIR}" uv sync --python "${PYTHON_BIN}" --frozen --extra dev
if ! /opt/venv/bin/python -m pytest --version >/dev/null 2>&1; then
  echo "pytest missing from /opt/venv; reinstalling dev dependencies..."
  UV_CACHE_DIR="${UV_CACHE_DIR}" uv sync --python "${PYTHON_BIN}" --frozen --extra dev
fi

# Some VS Code Python discovery flows still probe /bin/python directly.
# Ensure that fallback path resolves to the project venv interpreter.
if [ -x "/opt/venv/bin/python" ] && ! /bin/python -m pytest --version >/dev/null 2>&1; then
  echo "Aligning /bin/python with /opt/venv/bin/python for VS Code pytest discovery..."
  PYTHON_WRAPPER="$(mktemp)"
  cat <<'EOF' > "${PYTHON_WRAPPER}"
#!/usr/bin/env bash
exec /opt/venv/bin/python "$@"
EOF
  chmod 0755 "${PYTHON_WRAPPER}"
  if [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1; then
    sudo install -m 0755 "${PYTHON_WRAPPER}" /bin/python
  else
    install -m 0755 "${PYTHON_WRAPPER}" /bin/python
  fi
  rm -f "${PYTHON_WRAPPER}"
fi

# Mirror the canonical venv under the workspace as .venv for editor auto-detection.
ln -sfn /opt/venv .venv

# Optional: install VNC/noVNC deps for headed Playwright inside the container.
if [ "${DEVCONTAINER_E2E_VNC:-0}" = "1" ]; then
  if ! bash ./scripts/setup-e2e-vnc.sh; then
    echo "Warning: VNC dependency setup failed; continuing without blocking devcontainer startup."
  fi
  if ! bash ./scripts/start-e2e-vnc.sh; then
    echo "Warning: VNC startup failed; continuing without blocking devcontainer startup."
  fi
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
    NPM_CONFIG_CACHE="${NPM_CACHE_DIR}" NPM_CONFIG_UPDATE_NOTIFIER=false ./scripts/npm-ci-frontend.sh
  fi
fi

bash .devcontainer/cleanup-shell.sh
