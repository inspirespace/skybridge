#!/usr/bin/env bash
set -euo pipefail

HIST_DIR="/var/devcontainer/history"
HIST_FILE="${HIST_DIR}/.zsh_history"

mkdir -p "${HIST_DIR}"

# Ensure ownership for the current user (devcontainer runs as vscode)
if command -v id >/dev/null 2>&1; then
  chown -R "$(id -u):$(id -g)" "${HIST_DIR}" 2>/dev/null || true
fi

if [[ ! -w "${HIST_DIR}" ]] && command -v sudo >/dev/null 2>&1; then
  sudo chown -R "$(id -u):$(id -g)" "${HIST_DIR}" 2>/dev/null || true
  sudo chmod -R u+rwX "${HIST_DIR}" 2>/dev/null || true
fi

if [[ ! -f "${HIST_FILE}" ]]; then
  touch "${HIST_FILE}" 2>/dev/null || true
  if [[ ! -f "${HIST_FILE}" ]] && command -v sudo >/dev/null 2>&1; then
    sudo touch "${HIST_FILE}" 2>/dev/null || true
    sudo chown "$(id -u):$(id -g)" "${HIST_FILE}" 2>/dev/null || true
  fi
fi

ZSHRC="${HOME}/.zshrc"
ZSHENV="${HOME}/.zshenv"
HIST_BLOCK_START="# skybridge-history-start"
HIST_BLOCK_END="# skybridge-history-end"
HIST_BLOCK="${HIST_BLOCK_START}\nexport HISTFILE=/var/devcontainer/history/.zsh_history\nexport HISTSIZE=10000\nexport SAVEHIST=10000\nsetopt append_history\nsetopt inc_append_history\nsetopt share_history\nsetopt hist_ignore_dups\nsetopt hist_reduce_blanks\nif [[ -f \"\$HISTFILE\" ]]; then\n  fc -R \"\$HISTFILE\"\nfi\n${HIST_BLOCK_END}"

if [[ -f "${ZSHRC}" ]]; then
  if ! grep -q "${HIST_BLOCK_START}" "${ZSHRC}"; then
    printf '\n%b\n' "${HIST_BLOCK}" >> "${ZSHRC}"
  fi
else
  printf '%b\n' "${HIST_BLOCK}" > "${ZSHRC}"
fi

chmod 600 "${HIST_FILE}" 2>/dev/null || true
if [[ ! -w "${HIST_FILE}" ]] && command -v sudo >/dev/null 2>&1; then
  sudo chmod 600 "${HIST_FILE}" 2>/dev/null || true
  sudo chown "$(id -u):$(id -g)" "${HIST_FILE}" 2>/dev/null || true
fi

# Ensure HISTFILE is set early for all shells.
if [[ -f "${ZSHENV}" ]]; then
  if ! grep -q "HISTFILE=/var/devcontainer/history/.zsh_history" "${ZSHENV}"; then
    printf '\nexport HISTFILE=/var/devcontainer/history/.zsh_history\n' >> "${ZSHENV}"
  fi
else
  printf 'export HISTFILE=/var/devcontainer/history/.zsh_history\n' > "${ZSHENV}"
fi
