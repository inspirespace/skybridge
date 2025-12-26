#!/usr/bin/env bash
set -euo pipefail

ZSHRC="${HOME}/.zshrc"
ZPROFILE="${HOME}/.zprofile"
ZPRE_OHMY="${HOME}/.zshrc.pre-oh-my-zsh"
if [[ -f "${ZSHRC}" ]]; then
  sed -i '/source \/opt\/venv\/bin\/activate/d' "${ZSHRC}" || true
fi
if [[ -f "${ZPROFILE}" ]]; then
  sed -i '/source \/opt\/venv\/bin\/activate/d' "${ZPROFILE}" || true
fi
if [[ -f "${ZPRE_OHMY}" ]]; then
  sed -i '/source \/opt\/venv\/bin\/activate/d' "${ZPRE_OHMY}" || true
fi
