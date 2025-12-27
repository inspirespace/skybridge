#!/usr/bin/env bash
set -euo pipefail

CODEX_DIR="/home/vscode/.codex"
mkdir -p "${CODEX_DIR}"

# Ensure the devcontainer's Node toolchain is available for the Codex CLI.
export PATH="/usr/local/share/nvm/current/bin:${PATH}"

if command -v id >/dev/null 2>&1; then
  chown -R "$(id -u):$(id -g)" "${CODEX_DIR}" || true
  chmod -R u+rwX "${CODEX_DIR}" || true
  chmod 700 "${CODEX_DIR}" || true
fi

# If the volume is still owned by root, try sudo.
if [[ ! -w "${CODEX_DIR}" ]] && command -v sudo >/dev/null 2>&1; then
  sudo chown -R "$(id -u):$(id -g)" "${CODEX_DIR}" || true
  sudo chmod -R u+rwX "${CODEX_DIR}" || true
  sudo chmod 700 "${CODEX_DIR}" || true
fi

touch "${CODEX_DIR}/.touch" 2>/dev/null || true

CODEX_BIN="/home/vscode/.npm-global/bin/codex"
if [[ ! -x "${CODEX_BIN}" ]]; then
  # Node is provided by the devcontainer feature; ensure its bin dir is on PATH.
  export PATH="/usr/local/share/nvm/current/bin:${PATH}"

  if command -v npm >/dev/null 2>&1; then
    mkdir -p /home/vscode/.npm-global
    NPM_CONFIG_PREFIX="/home/vscode/.npm-global" npm i -g @openai/codex || true
  fi
fi

# Clear any persisted prefix that would fight with nvm.
if [[ -f "${HOME}/.npmrc" ]]; then
  if grep -q '^prefix=' "${HOME}/.npmrc"; then
    tmpfile=$(mktemp)
    grep -v '^prefix=' "${HOME}/.npmrc" > "${tmpfile}" || true
    if [[ -s "${tmpfile}" ]]; then
      mv "${tmpfile}" "${HOME}/.npmrc"
    else
      rm -f "${HOME}/.npmrc"
    fi
  fi
fi

# Install Codex zsh completions for the devcontainer shell.
if command -v codex >/dev/null 2>&1; then
  completion_dir="${HOME}/.config/codex"
  completion_file="${completion_dir}/completion.zsh"
  mkdir -p "${completion_dir}"
  if codex completion zsh > "${completion_file}" 2>/dev/null; then
    zshrc="${HOME}/.zshrc"
    if [[ -f "${zshrc}" ]] && ! grep -q "codex/completion.zsh" "${zshrc}"; then
      {
        echo ""
        echo "# Codex CLI completions"
        echo "[[ -f \"${completion_file}\" ]] && source \"${completion_file}\""
      } >> "${zshrc}"
    fi
  fi
fi
