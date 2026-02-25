#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

had_permission_warnings=0
is_darwin=0
if [ "$(uname -s)" = "Darwin" ]; then
  is_darwin=1
fi

attempt_rm() {
  local target="$1"
  rm -rf -- "$target" 2>/dev/null
}

relax_delete_permissions() {
  local target="$1"

  chmod -R u+w -- "$target" 2>/dev/null || true

  if [ "$is_darwin" -eq 1 ]; then
    # Docker/macOS may add ACL entries like "deny delete"; clear them before retrying.
    chmod -RN -- "$target" 2>/dev/null || true
    chflags -R nouchg -- "$target" 2>/dev/null || true
  fi
}

safe_rm() {
  local target="$1"
  if [ ! -e "$target" ] && [ ! -L "$target" ]; then
    return 0
  fi

  if attempt_rm "$target"; then
    return 0
  fi

  relax_delete_permissions "$target"
  if attempt_rm "$target"; then
    return 0
  fi

  if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
    if sudo -n rm -rf -- "$target" 2>/dev/null; then
      return 0
    fi
  fi

  echo "Warning: unable to remove '$target' due to permissions." >&2
  had_permission_warnings=1
  return 0
}

static_targets=(
  ".venv"
  ".uv"
  ".uv-cache"
  ".cache"
  ".pytest_cache"
  ".npm-cache"
  ".playwright-mcp"
  ".firebase-emulator"
  "build"
  "dist"
  "htmlcov"
  ".coverage"
  "functions/venv"
  "src/frontend/node_modules"
  "src/frontend/dist"
  "src/frontend/.vite"
  "src/frontend/.npm-cache"
  "src/frontend/.npm-cache-shadcn"
  "src/frontend/coverage"
  "src/frontend/test-results"
  "src/frontend/playwright-report"
)

for target in "${static_targets[@]}"; do
  safe_rm "$target"
done

shopt -s nullglob
for target in firebase-export-* .coverage.* *.egg-info; do
  safe_rm "$target"
done
shopt -u nullglob

find . -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete 2>/dev/null || true
find . -type f -name "*.log" -delete 2>/dev/null || true

if [ "$had_permission_warnings" -eq 1 ]; then
  echo "Workspace clean completed with permission warnings." >&2
fi
