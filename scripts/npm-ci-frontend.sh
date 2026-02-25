#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

FRONTEND_DIR="src/frontend"
NPM_CACHE_DIR="${NPM_CONFIG_CACHE:-${HOME}/.cache/npm}"
NPM_UPDATE_NOTIFIER="${NPM_CONFIG_UPDATE_NOTIFIER:-false}"

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required to install frontend dependencies." >&2
  exit 1
fi

if [ ! -d "$FRONTEND_DIR" ]; then
  echo "Frontend directory not found: $FRONTEND_DIR" >&2
  exit 1
fi

mkdir -p "$NPM_CACHE_DIR"

run_install() {
  NPM_CONFIG_CACHE="$NPM_CACHE_DIR" \
  NPM_CONFIG_UPDATE_NOTIFIER="$NPM_UPDATE_NOTIFIER" \
    npm --prefix "$FRONTEND_DIR" ci --install-strategy=nested --no-audit --fund=false
}

print_latest_npm_logs() {
  local found=0
  local log_dir
  for log_dir in "$NPM_CACHE_DIR/_logs" "$HOME/.npm/_logs"; do
    if [ -d "$log_dir" ]; then
      local latest_log
      latest_log="$(ls -1t "$log_dir"/*-debug-0.log 2>/dev/null | head -n 1 || true)"
      if [ -n "$latest_log" ]; then
        echo "Latest npm log: $latest_log" >&2
        found=1
      fi
    fi
  done
  if [ "$found" -eq 0 ]; then
    echo "No npm debug log found under '$NPM_CACHE_DIR/_logs' or '$HOME/.npm/_logs'." >&2
  fi
}

echo "Installing frontend dependencies (attempt 1/2)..."
if run_install; then
  exit 0
fi

echo "Frontend npm install failed on first attempt; cleaning cache and retrying..." >&2
rm -rf "$FRONTEND_DIR/node_modules"
NPM_CONFIG_CACHE="$NPM_CACHE_DIR" \
NPM_CONFIG_UPDATE_NOTIFIER="$NPM_UPDATE_NOTIFIER" \
  npm cache clean --force >/dev/null 2>&1 || true

echo "Installing frontend dependencies (attempt 2/2)..."
if run_install; then
  exit 0
fi

echo "Frontend npm install failed after retry." >&2
print_latest_npm_logs
exit 1
