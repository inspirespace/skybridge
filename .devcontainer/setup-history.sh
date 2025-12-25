#!/usr/bin/env bash
set -euo pipefail

HIST_DIR="/var/devcontainer/history"
HIST_FILE="${HIST_DIR}/.zsh_history"

mkdir -p "${HIST_DIR}"

# Ensure ownership for the current user (devcontainer runs as vscode)
if command -v id >/dev/null 2>&1; then
  chown -R "$(id -u):$(id -g)" "${HIST_DIR}" || true
fi

if [[ ! -f "${HIST_FILE}" ]]; then
  touch "${HIST_FILE}" || true
fi

ZSHRC="${HOME}/.zshrc"
LOCAL_RC="${HOME}/.zshrc.local"

if [[ ! -f "${LOCAL_RC}" ]]; then
  cat <<'EOF' > "${LOCAL_RC}"
export HISTFILE=/var/devcontainer/history/.zsh_history
export HISTSIZE=10000
export SAVEHIST=10000
setopt append_history
setopt inc_append_history
setopt share_history
setopt hist_ignore_dups
setopt hist_reduce_blanks
EOF
else
  if ! grep -q "HISTFILE=/var/devcontainer/history/.zsh_history" "${LOCAL_RC}"; then
    printf '\nexport HISTFILE=/var/devcontainer/history/.zsh_history\n' >> "${LOCAL_RC}"
  fi
fi

if [[ -f "${ZSHRC}" ]]; then
  if ! grep -q "source ${LOCAL_RC}" "${ZSHRC}"; then
    printf '\nsource %s\n' "${LOCAL_RC}" >> "${ZSHRC}"
  fi
fi
