#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

rm -rf \
  .venv \
  .uv \
  .uv-cache \
  .cache \
  .pytest_cache \
  .npm-cache \
  .playwright-mcp \
  .firebase-emulator \
  firebase-export-* \
  build \
  dist \
  htmlcov \
  .coverage \
  .coverage.* \
  *.egg-info \
  functions/venv \
  src/frontend/node_modules \
  src/frontend/dist \
  src/frontend/.vite \
  src/frontend/.npm-cache \
  src/frontend/.npm-cache-shadcn \
  src/frontend/coverage \
  src/frontend/test-results \
  src/frontend/playwright-report

find . -type d -name "__pycache__" -prune -exec rm -rf {} +
find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete
find . -type f -name "*.log" -delete
