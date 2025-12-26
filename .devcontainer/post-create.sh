#!/usr/bin/env bash
set -euo pipefail

ZSHRC="${HOME}/.zshrc"

if [[ -f "${ZSHRC}" ]]; then
  if ! grep -qxF 'eval "$(starship init zsh)"' "${ZSHRC}"; then
    echo 'eval "$(starship init zsh)"' >> "${ZSHRC}"
  fi
fi
