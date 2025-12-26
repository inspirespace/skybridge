#!/usr/bin/env bash
set -euo pipefail

ZSHRC="${HOME}/.zshrc"

if [[ -f "${ZSHRC}" ]]; then
  if ! grep -q "autoload -Uz compinit" "${ZSHRC}"; then
    {
      echo ""
      echo "autoload -Uz compinit"
      echo "compinit"
      echo "zstyle ':completion:*' menu select"
    } >> "${ZSHRC}"
  fi
fi
