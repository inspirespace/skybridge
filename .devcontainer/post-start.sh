#!/usr/bin/env bash
set -euo pipefail

bash .devcontainer/setup-history.sh
bash .devcontainer/setup-codex.sh
bash .devcontainer/setup-venv.sh
bash .devcontainer/setup-completion.sh
UV_CACHE_DIR=/tmp/uv-cache uv sync --frozen --extra dev
bash .devcontainer/cleanup-shell.sh
