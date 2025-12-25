#!/usr/bin/env bash
set -euo pipefail

ZSHRC="${HOME}/.zshrc"
if [[ -f "${ZSHRC}" ]]; then
  sed -i '/source \/opt\/venv\/bin\/activate/d' "${ZSHRC}" || true
fi
